//! Second-launch activation client for the experimental Windows host.
//!
//! A shortcut that finds a live owned instance sends authenticated `show`
//! requests over the already-published maintenance pipe. The receipt, process
//! identity, pipe name and pipe server PID are proved before the bearer token is
//! written. Only an explicit `shown` reply is success. A `not_ready` reply is
//! retried with a fresh request id within one bounded deadline; maintenance and
//! shutdown replies are terminal. No command, path or Python interpreter from
//! the receipt is executed.

use crate::config::HostConfig;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::io;
use std::os::windows::io::AsRawHandle;
use std::path::Path;
use std::time::{Duration, Instant};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::windows::named_pipe::{ClientOptions, NamedPipeClient};
use uuid::Uuid;
use windows_sys::Win32::Foundation::{CloseHandle, FILETIME, HANDLE, WAIT_TIMEOUT};
use windows_sys::Win32::System::Pipes::GetNamedPipeServerProcessId;
use windows_sys::Win32::System::Threading::{
    GetProcessTimes, OpenProcess, QueryFullProcessImageNameW, PROCESS_QUERY_LIMITED_INFORMATION,
};

const ACTIVATION_DEADLINE: Duration = Duration::from_secs(5);
const RETRY_INTERVAL: Duration = Duration::from_millis(50);
const MAX_FRAME_BYTES: usize = 4096;
const RECEIPT_LIMIT: u64 = 16 * 1024;
const PIPE_PREFIX: &str = r"\\.\pipe\OperonExperimentalMaintenance-";
// SYNCHRONIZE is not exported by the enabled windows-sys features.
const SYNCHRONIZE_ACCESS: u32 = 0x0010_0000;

/// Stable activation failures. Messages never contain the token or a caller path.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActivationError {
    MaintenanceActive,
    ReceiptInvalid,
    Unavailable,
    Rejected,
    Protocol,
}

impl ActivationError {
    pub fn message(self) -> &'static str {
        match self {
            Self::MaintenanceActive => {
                "The installation is being maintained. Wait for maintenance to finish and try again."
            }
            Self::ReceiptInvalid => {
                "The running experimental instance could not be verified. Use its tray menu to show or exit it."
            }
            Self::Unavailable => {
                "The running experimental instance did not accept activation in time. Use its tray menu to show or exit it."
            }
            Self::Rejected => {
                "The running experimental instance is not ready to be shown. Use its tray menu to show or exit it."
            }
            Self::Protocol => {
                "The running experimental instance returned an unexpected activation response."
            }
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Receipt {
    schema: u32,
    installation_id: String,
    pid: u32,
    created_filetime: String,
    exe: String,
    pipe_name: String,
    token: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Response {
    schema: u32,
    request_id: String,
    status: String,
}

struct OwnedProcess {
    handle: HANDLE,
}

impl Drop for OwnedProcess {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.handle);
        }
    }
}

impl OwnedProcess {
    fn open(receipt: &Receipt, expected_exe: &Path) -> Option<Self> {
        let handle = unsafe {
            OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE_ACCESS,
                0,
                receipt.pid,
            )
        };
        if handle.is_null() {
            return None;
        }
        let process = Self { handle };
        let expected_created = receipt.created_filetime.parse::<u64>().ok()?;
        if expected_created == 0 || process.creation_filetime()? != expected_created {
            return None;
        }
        let image = process.image()?;
        if normalize_path(Path::new(&image)) != normalize_path(expected_exe) {
            return None;
        }
        if unsafe { windows_sys::Win32::System::Threading::WaitForSingleObject(handle, 0) }
            != WAIT_TIMEOUT
        {
            return None;
        }
        Some(process)
    }

    fn creation_filetime(&self) -> Option<u64> {
        let mut created: FILETIME = unsafe { std::mem::zeroed() };
        let mut exited: FILETIME = unsafe { std::mem::zeroed() };
        let mut kernel: FILETIME = unsafe { std::mem::zeroed() };
        let mut user: FILETIME = unsafe { std::mem::zeroed() };
        let ok = unsafe {
            GetProcessTimes(
                self.handle,
                &mut created,
                &mut exited,
                &mut kernel,
                &mut user,
            )
        };
        if ok == 0 {
            return None;
        }
        Some(((created.dwHighDateTime as u64) << 32) | created.dwLowDateTime as u64)
    }

    fn image(&self) -> Option<String> {
        let mut buffer = vec![0u16; 32_768];
        let mut size = buffer.len() as u32;
        let ok =
            unsafe { QueryFullProcessImageNameW(self.handle, 0, buffer.as_mut_ptr(), &mut size) };
        if ok == 0 || size == 0 {
            return None;
        }
        Some(String::from_utf16_lossy(&buffer[..size as usize]))
    }
}

struct ValidatedHost {
    receipt: Receipt,
    _process: OwnedProcess,
}

enum Exchange {
    Shown,
    NotReady,
    ConnectFailed,
    Fatal(ActivationError),
}

enum ReceiptFailure {
    WrongInstallation,
    Retry,
}

/// Ask the already-running owned host to show its main window.
///
/// Success is returned only after the host reports `shown`. The whole operation
/// is bounded to five seconds including receipt publication retries.
pub fn request_show(config: &HostConfig) -> Result<(), ActivationError> {
    let expected_exe =
        fs::canonicalize(std::env::current_exe().map_err(|_| ActivationError::Unavailable)?)
            .map_err(|_| ActivationError::Unavailable)?;
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|_| ActivationError::Unavailable)?;
    runtime.block_on(request_show_until(
        config,
        &expected_exe,
        Instant::now() + ACTIVATION_DEADLINE,
    ))
}

async fn request_show_until(
    config: &HostConfig,
    expected_exe: &Path,
    deadline: Instant,
) -> Result<(), ActivationError> {
    loop {
        if Instant::now() >= deadline {
            return Err(ActivationError::Unavailable);
        }
        match crate::maintenance::is_active(&config.installation_id) {
            Ok(false) => {}
            Ok(true) => return Err(ActivationError::MaintenanceActive),
            Err(_) => return Err(ActivationError::Unavailable),
        }

        let host = wait_for_host(config, expected_exe, deadline).await?;
        match exchange(&host, deadline).await {
            Exchange::Shown => return Ok(()),
            Exchange::NotReady => retry_pause(deadline).await,
            Exchange::ConnectFailed => retry_pause(deadline).await,
            Exchange::Fatal(error) => return Err(error),
        }
    }
}

async fn wait_for_host(
    config: &HostConfig,
    expected_exe: &Path,
    deadline: Instant,
) -> Result<ValidatedHost, ActivationError> {
    loop {
        if Instant::now() >= deadline {
            return Err(ActivationError::ReceiptInvalid);
        }
        match crate::maintenance::is_active(&config.installation_id) {
            Ok(false) => {}
            Ok(true) => return Err(ActivationError::MaintenanceActive),
            Err(_) => return Err(ActivationError::Unavailable),
        }

        match read_receipt(config, expected_exe) {
            Ok(receipt) => {
                if let Some(process) = OwnedProcess::open(&receipt, expected_exe) {
                    return Ok(ValidatedHost {
                        receipt,
                        _process: process,
                    });
                }
            }
            Err(ReceiptFailure::WrongInstallation) => {
                return Err(ActivationError::ReceiptInvalid);
            }
            Err(ReceiptFailure::Retry) => {}
        }
        retry_pause(deadline).await;
    }
}

fn read_receipt(config: &HostConfig, expected_exe: &Path) -> Result<Receipt, ReceiptFailure> {
    let path = config.profile.join(crate::maintenance::RECEIPT_FILE);
    let metadata = fs::metadata(&path).map_err(|_| ReceiptFailure::Retry)?;
    if metadata.len() > RECEIPT_LIMIT {
        return Err(ReceiptFailure::Retry);
    }
    let bytes = fs::read(&path).map_err(|_| ReceiptFailure::Retry)?;
    if bytes.len() as u64 > RECEIPT_LIMIT {
        return Err(ReceiptFailure::Retry);
    }
    let receipt: Receipt = serde_json::from_slice(&bytes).map_err(|_| ReceiptFailure::Retry)?;
    if receipt.schema != 1 {
        return Err(ReceiptFailure::Retry);
    }
    if receipt.installation_id != config.installation_id {
        return Err(ReceiptFailure::WrongInstallation);
    }
    if receipt.pid == 0
        || receipt
            .created_filetime
            .parse::<u64>()
            .map(|value| value == 0)
            .unwrap_or(true)
        || !crate::maintenance::valid_token(&receipt.token)
        || !valid_pipe_name(&receipt.pipe_name, &receipt.installation_id)
    {
        return Err(ReceiptFailure::Retry);
    }
    let receipt_exe = fs::canonicalize(&receipt.exe).map_err(|_| ReceiptFailure::Retry)?;
    if normalize_path(&receipt_exe) != normalize_path(expected_exe) {
        return Err(ReceiptFailure::Retry);
    }
    Ok(receipt)
}

fn valid_pipe_name(value: &str, installation_id: &str) -> bool {
    let Some(tail) = value.strip_prefix(PIPE_PREFIX) else {
        return false;
    };
    let Some((hash, unique)) = tail.split_once('-') else {
        return false;
    };
    if hash.len() != 16
        || !hash.chars().all(|value| value.is_ascii_hexdigit())
        || Uuid::parse_str(unique).is_err()
    {
        return false;
    }
    let digest = Sha256::digest(installation_id.as_bytes());
    let expected: String = digest.iter().map(|byte| format!("{byte:02x}")).collect();
    hash.eq_ignore_ascii_case(&expected[..16])
}

fn normalize_path(value: &Path) -> String {
    let text = value.to_string_lossy();
    let text = if let Some(rest) = text.strip_prefix(r"\\?\UNC\") {
        format!(r"\\{rest}")
    } else if let Some(rest) = text.strip_prefix(r"\\?\") {
        rest.to_owned()
    } else {
        text.into_owned()
    };
    text.replace('/', "\\").to_ascii_lowercase()
}

async fn exchange(host: &ValidatedHost, deadline: Instant) -> Exchange {
    let mut client = match connect(&host.receipt.pipe_name, deadline).await {
        Ok(client) => client,
        Err(()) => return Exchange::ConnectFailed,
    };
    if !server_matches(&client, host.receipt.pid) {
        return Exchange::Fatal(ActivationError::ReceiptInvalid);
    }

    let request_id = Uuid::new_v4().to_string();
    let request = serde_json::json!({
        "schema": 1,
        "installation_id": host.receipt.installation_id,
        "token": host.receipt.token,
        "action": "show",
        "request_id": request_id,
    });
    if write_frame(&mut client, &request, deadline).await.is_err() {
        return Exchange::Fatal(ActivationError::Unavailable);
    }
    let response = match read_response(&mut client, deadline).await {
        Ok(response) => response,
        Err(_) => return Exchange::Fatal(ActivationError::Unavailable),
    };
    if response.schema != 1 || response.request_id != request_id {
        return Exchange::Fatal(ActivationError::Protocol);
    }
    let ack = serde_json::json!({
        "schema": 1,
        "request_id": request_id,
        "action": "ack",
    });
    if write_frame(&mut client, &ack, deadline).await.is_err() {
        return Exchange::Fatal(ActivationError::Unavailable);
    }
    match response.status.as_str() {
        "not_ready" => return Exchange::NotReady,
        "rejected" => return Exchange::Fatal(ActivationError::Rejected),
        "accepted" => {}
        _ => return Exchange::Fatal(ActivationError::Protocol),
    }
    let shown = match read_response(&mut client, deadline).await {
        Ok(response) => response,
        Err(_) => return Exchange::Fatal(ActivationError::Unavailable),
    };
    if shown.schema != 1 || shown.request_id != request_id {
        return Exchange::Fatal(ActivationError::Protocol);
    }
    if write_frame(&mut client, &ack, deadline).await.is_err() {
        return Exchange::Fatal(ActivationError::Unavailable);
    }
    match shown.status.as_str() {
        "shown" => Exchange::Shown,
        "rejected" => Exchange::Fatal(ActivationError::Rejected),
        _ => Exchange::Fatal(ActivationError::Protocol),
    }
}

fn server_matches(client: &NamedPipeClient, expected: u32) -> bool {
    let mut pid = 0u32;
    let ok = unsafe { GetNamedPipeServerProcessId(client.as_raw_handle() as HANDLE, &mut pid) };
    ok != 0 && pid == expected
}

async fn connect(pipe_name: &str, deadline: Instant) -> Result<NamedPipeClient, ()> {
    loop {
        remaining(deadline).map_err(|_| ())?;
        match ClientOptions::new().open(pipe_name) {
            Ok(client) => return Ok(client),
            Err(_) => {
                let wait = remaining(deadline).map_err(|_| ())?;
                tokio::time::sleep(wait.min(Duration::from_millis(25))).await;
            }
        }
    }
}

async fn read_response(client: &mut NamedPipeClient, deadline: Instant) -> io::Result<Response> {
    let frame = read_frame(client, deadline).await?;
    serde_json::from_slice(&frame)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "response json"))
}

async fn read_frame(client: &mut NamedPipeClient, deadline: Instant) -> io::Result<Vec<u8>> {
    let mut output = Vec::new();
    let mut buffer = [0u8; 512];
    loop {
        let remaining =
            remaining(deadline).map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "deadline"))?;
        let count = tokio::time::timeout(remaining, client.read(&mut buffer))
            .await
            .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "deadline"))??;
        if count == 0 {
            return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "closed"));
        }
        for byte in &buffer[..count] {
            if *byte == b'\n' {
                return Ok(output);
            }
            if output.len() >= MAX_FRAME_BYTES {
                return Err(io::Error::new(io::ErrorKind::InvalidData, "oversized"));
            }
            output.push(*byte);
        }
    }
}

async fn write_frame(
    client: &mut NamedPipeClient,
    value: &impl Serialize,
    deadline: Instant,
) -> io::Result<()> {
    let mut body = serde_json::to_vec(value)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "json"))?;
    if body.len() >= MAX_FRAME_BYTES {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "oversized"));
    }
    body.push(b'\n');
    let remaining =
        remaining(deadline).map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "deadline"))?;
    tokio::time::timeout(remaining, async {
        client.write_all(&body).await?;
        client.flush().await
    })
    .await
    .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "deadline"))??;
    Ok(())
}

fn remaining(deadline: Instant) -> Result<Duration, ActivationError> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|value| !value.is_zero())
        .ok_or(ActivationError::Unavailable)
}

async fn retry_pause(deadline: Instant) {
    let remaining = deadline.saturating_duration_since(Instant::now());
    if !remaining.is_zero() {
        tokio::time::sleep(remaining.min(RETRY_INTERVAL)).await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use tokio::net::windows::named_pipe::{PipeMode, ServerOptions};
    use tokio::sync::oneshot;

    struct Fixture {
        _root: tempfile::TempDir,
        config: HostConfig,
        receipt_path: PathBuf,
        installation_id: String,
        pipe_name: String,
        token: String,
        expected_exe: PathBuf,
    }

    impl Fixture {
        fn new() -> Self {
            let root = tempfile::tempdir().unwrap();
            let installation_id = format!("activation-test-{}", Uuid::new_v4());
            let profile = root.path().join("profile");
            fs::create_dir_all(&profile).unwrap();
            let expected_exe = fs::canonicalize(std::env::current_exe().unwrap()).unwrap();
            let digest = Sha256::digest(installation_id.as_bytes());
            let hash: String = digest.iter().map(|byte| format!("{byte:02x}")).collect();
            let pipe_name = format!(
                r"\\.\pipe\OperonExperimentalMaintenance-{}-{}",
                &hash[..16],
                Uuid::new_v4()
            );
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            let receipt_path = profile.join(crate::maintenance::RECEIPT_FILE);
            let config = HostConfig {
                installation_id: installation_id.clone(),
                backend_root: PathBuf::new(),
                python: PathBuf::new(),
                frontend: PathBuf::new(),
                profile,
            };
            Self {
                _root: root,
                config,
                receipt_path,
                installation_id,
                pipe_name,
                token,
                expected_exe,
            }
        }

        fn write_receipt(&self, pid: u32, created: u64, installation_id: &str) {
            let receipt = serde_json::json!({
                "schema": 1,
                "installation_id": installation_id,
                "pid": pid,
                "created_filetime": created.to_string(),
                "exe": self.expected_exe.to_string_lossy(),
                "pipe_name": self.pipe_name,
                "token": self.token,
            });
            fs::write(&self.receipt_path, serde_json::to_vec(&receipt).unwrap()).unwrap();
        }

        fn write_current_receipt(&self) {
            self.write_receipt(
                std::process::id(),
                current_creation_filetime(),
                &self.installation_id,
            );
        }
    }

    fn current_creation_filetime() -> u64 {
        let mut created: FILETIME = unsafe { std::mem::zeroed() };
        let mut exited: FILETIME = unsafe { std::mem::zeroed() };
        let mut kernel: FILETIME = unsafe { std::mem::zeroed() };
        let mut user: FILETIME = unsafe { std::mem::zeroed() };
        let ok = unsafe {
            GetProcessTimes(
                windows_sys::Win32::System::Threading::GetCurrentProcess(),
                &mut created,
                &mut exited,
                &mut kernel,
                &mut user,
            )
        };
        assert_ne!(ok, 0);
        ((created.dwHighDateTime as u64) << 32) | created.dwLowDateTime as u64
    }

    async fn start_server(
        pipe_name: String,
        installation_id: String,
        token: String,
        script: Vec<&'static str>,
    ) -> tokio::task::JoinHandle<()> {
        let (ready_tx, ready_rx) = oneshot::channel();
        let handle = tokio::spawn(async move {
            let mut next = Some(
                ServerOptions::new()
                    .pipe_mode(PipeMode::Byte)
                    .first_pipe_instance(true)
                    .create(&pipe_name)
                    .unwrap(),
            );
            ready_tx.send(()).unwrap();
            for status in script {
                let mut server = match next.take() {
                    Some(server) => server,
                    None => ServerOptions::new()
                        .pipe_mode(PipeMode::Byte)
                        .first_pipe_instance(false)
                        .create(&pipe_name)
                        .unwrap(),
                };
                server.connect().await.unwrap();
                let frame = read_test_frame(&mut server).await;
                let request: serde_json::Value = serde_json::from_slice(&frame).unwrap();
                assert_eq!(request["schema"], 1);
                assert_eq!(request["installation_id"], installation_id);
                assert_eq!(request["token"], token);
                assert_eq!(request["action"], "show");
                let request_id = request["request_id"].as_str().unwrap().to_owned();
                if status == "not_ready" {
                    write_test_frame(
                        &mut server,
                        &serde_json::json!({
                            "schema": 1,
                            "request_id": request_id,
                            "status": "not_ready",
                        }),
                    )
                    .await;
                    let _ = read_test_frame(&mut server).await;
                    continue;
                }
                write_test_frame(
                    &mut server,
                    &serde_json::json!({
                        "schema": 1,
                        "request_id": request_id,
                        "status": "accepted",
                    }),
                )
                .await;
                let ack = read_test_frame(&mut server).await;
                let ack: serde_json::Value = serde_json::from_slice(&ack).unwrap();
                assert_eq!(ack["request_id"], request_id);
                assert_eq!(ack["action"], "ack");
                match status {
                    "shown" => {
                        write_test_frame(
                            &mut server,
                            &serde_json::json!({
                                "schema": 1,
                                "request_id": request_id,
                                "status": "shown",
                            }),
                        )
                        .await;
                    }
                    "rejected" => {
                        write_test_frame(
                            &mut server,
                            &serde_json::json!({
                                "schema": 1,
                                "request_id": request_id,
                                "status": "rejected",
                            }),
                        )
                        .await;
                    }
                    "close_after_ack" => {}
                    _ => panic!("unknown test server status"),
                }
                if status != "close_after_ack" {
                    let final_ack: serde_json::Value =
                        serde_json::from_slice(&read_test_frame(&mut server).await).unwrap();
                    assert_eq!(final_ack["request_id"], request_id);
                    assert_eq!(final_ack["action"], "ack");
                }
            }
        });
        ready_rx.await.unwrap();
        handle
    }

    async fn read_test_frame(
        server: &mut tokio::net::windows::named_pipe::NamedPipeServer,
    ) -> Vec<u8> {
        let mut output = Vec::new();
        let mut one = [0u8; 1];
        loop {
            let read = server.read(&mut one).await.unwrap();
            assert_ne!(read, 0);
            if one[0] == b'\n' {
                return output;
            }
            output.push(one[0]);
        }
    }

    async fn write_test_frame(
        server: &mut tokio::net::windows::named_pipe::NamedPipeServer,
        value: &serde_json::Value,
    ) {
        let mut body = serde_json::to_vec(value).unwrap();
        body.push(b'\n');
        server.write_all(&body).await.unwrap();
        server.flush().await.unwrap();
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn retries_not_ready_then_requires_shown() {
        let fixture = Fixture::new();
        fixture.write_current_receipt();
        let server = start_server(
            fixture.pipe_name.clone(),
            fixture.installation_id.clone(),
            fixture.token.clone(),
            vec!["not_ready", "shown"],
        )
        .await;
        request_show_until(
            &fixture.config,
            &fixture.expected_exe,
            Instant::now() + Duration::from_secs(3),
        )
        .await
        .unwrap();
        server.await.unwrap();
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn accepted_without_shown_is_not_success() {
        let fixture = Fixture::new();
        fixture.write_current_receipt();
        let server = start_server(
            fixture.pipe_name.clone(),
            fixture.installation_id.clone(),
            fixture.token.clone(),
            vec!["close_after_ack"],
        )
        .await;
        let error = request_show_until(
            &fixture.config,
            &fixture.expected_exe,
            Instant::now() + Duration::from_secs(3),
        )
        .await
        .unwrap_err();
        assert_eq!(error, ActivationError::Unavailable);
        server.await.unwrap();
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn rejected_is_terminal_and_not_retried() {
        let fixture = Fixture::new();
        fixture.write_current_receipt();
        let server = start_server(
            fixture.pipe_name.clone(),
            fixture.installation_id.clone(),
            fixture.token.clone(),
            vec!["rejected"],
        )
        .await;
        let error = request_show_until(
            &fixture.config,
            &fixture.expected_exe,
            Instant::now() + Duration::from_secs(3),
        )
        .await
        .unwrap_err();
        assert_eq!(error, ActivationError::Rejected);
        server.await.unwrap();
    }

    #[tokio::test]
    async fn maintenance_active_is_terminal_for_activation() {
        let fixture = Fixture::new();
        let _lease = crate::maintenance::MaintenanceLease::acquire(&fixture.installation_id)
            .expect("hold maintenance lease");
        let error = request_show_until(
            &fixture.config,
            &fixture.expected_exe,
            Instant::now() + Duration::from_secs(2),
        )
        .await
        .unwrap_err();
        assert_eq!(error, ActivationError::MaintenanceActive);
    }

    #[tokio::test]
    async fn wrong_installation_receipt_fails_closed() {
        let fixture = Fixture::new();
        fixture.write_current_receipt();
        fixture.write_receipt(
            std::process::id(),
            current_creation_filetime(),
            "another-installation",
        );
        let error = request_show_until(
            &fixture.config,
            &fixture.expected_exe,
            Instant::now() + Duration::from_millis(5_000),
        )
        .await
        .unwrap_err();
        assert_eq!(error, ActivationError::ReceiptInvalid);
    }

    #[tokio::test]
    async fn missing_or_stale_receipt_retry_is_bounded() {
        let fixture = Fixture::new();
        let started = Instant::now();
        let error = request_show_until(
            &fixture.config,
            &fixture.expected_exe,
            Instant::now() + Duration::from_millis(300),
        )
        .await
        .unwrap_err();
        assert_eq!(error, ActivationError::ReceiptInvalid);
        assert!(started.elapsed() < Duration::from_secs(2));
    }

    #[test]
    fn pipe_name_and_token_validation_bind_to_installation() {
        let fixture = Fixture::new();
        assert!(valid_pipe_name(
            &fixture.pipe_name,
            &fixture.installation_id
        ));
        assert!(!valid_pipe_name(&fixture.pipe_name, "another-installation"));
        assert!(crate::maintenance::valid_token(&fixture.token));
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn server_pid_mismatch_is_detected() {
        let pipe_name = format!(r"\\.\pipe\OperonActivationTest-{}", Uuid::new_v4());
        let server_pipe = pipe_name.clone();
        let server = tokio::spawn(async move {
            let server = ServerOptions::new()
                .pipe_mode(PipeMode::Byte)
                .first_pipe_instance(true)
                .create(&server_pipe)
                .unwrap();
            server.connect().await.unwrap();
            server
        });
        let client = loop {
            match ClientOptions::new().open(&pipe_name) {
                Ok(client) => break client,
                Err(_) => tokio::task::yield_now().await,
            }
        };
        let pid = std::process::id();
        assert!(server_matches(&client, pid));
        assert!(!server_matches(&client, pid.wrapping_add(1)));
        drop(server.await.unwrap());
    }
}
