//! Installation-scoped maintenance channel for the experimental Windows host.
//!
//! The only accepted action is a bearer-authenticated graceful `quit` request.
//! The channel never exposes a renderer command, caller paths, process control,
//! or arbitrary IPC. A local named pipe is published together with a private
//! profile receipt before the startup gate is released; the receipt is removed
//! only by the session that still owns it.
//!
//! The startup gate is a named mutex plus a manual-reset active event. The host
//! takes the mutex before the profile instance lock or backend spawn and checks
//! that maintenance is not active. An installer holds the same mutex and sets
//! the event for the whole drain/commit transaction.

use crate::error::HostError;

#[cfg(windows)]
mod windows_impl {
    use super::HostError;
    use crate::bridge::HostState;
    use serde::{Deserialize, Serialize};
    use sha2::{Digest, Sha256};
    use std::collections::VecDeque;
    use std::ffi::OsStr;
    use std::fs;
    use std::io;
    use std::os::windows::ffi::OsStrExt;
    use std::path::{Path, PathBuf};
    use std::sync::{Arc, Mutex};
    use std::time::{Duration, Instant};
    use tauri::{AppHandle, Manager};
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::windows::named_pipe::{NamedPipeServer, PipeMode, ServerOptions};
    use uuid::Uuid;
    use windows_sys::Win32::Foundation::{CloseHandle, FILETIME, WAIT_ABANDONED, WAIT_OBJECT_0};
    use windows_sys::Win32::System::Threading::{
        CreateEventW, CreateMutexW, GetCurrentProcess, GetProcessTimes, ReleaseMutex, ResetEvent,
        SetEvent, WaitForSingleObject,
    };

    pub const RECEIPT_FILE: &str = ".operon-maintenance-host.json";
    pub const MAX_FRAME_BYTES: usize = 4096;
    pub const READ_DEADLINE: Duration = Duration::from_secs(3);
    const MAX_RECENT_REQUESTS: usize = 8;
    const MUTEX_PREFIX: &str = "Local\\OperonExperimentalMaintenance-";
    const EVENT_SUFFIX: &str = "-active";

    /// A held named mutex proving that host startup is still in the pre-spawn
    /// phase. Windows mutex ownership is thread-specific, so a dedicated owner
    /// thread acquires it once and releases it on that same thread when this
    /// Send guard is dropped.
    pub struct StartupGuard {
        release: Option<std::sync::mpsc::Sender<()>>,
        thread: Option<std::thread::JoinHandle<()>>,
    }

    impl StartupGuard {
        pub fn acquire(installation_id: &str) -> Result<Self, HostError> {
            let (release, thread) = spawn_gate_owner(installation_id, false)?;
            Ok(Self {
                release: Some(release),
                thread: Some(thread),
            })
        }
    }

    impl Drop for StartupGuard {
        fn drop(&mut self) {
            if let Some(release) = self.release.take() {
                let _ = release.send(());
            }
            if let Some(thread) = self.thread.take() {
                let _ = thread.join();
            }
        }
    }

    /// Installer-side maintenance ownership. It holds the installation mutex and
    /// sets the active event until the transaction guard is dropped.
    pub struct MaintenanceLease {
        release: Option<std::sync::mpsc::Sender<()>>,
        thread: Option<std::thread::JoinHandle<()>>,
    }

    impl MaintenanceLease {
        pub fn acquire(installation_id: &str) -> Result<Self, HostError> {
            let (release, thread) = spawn_gate_owner(installation_id, true)?;
            Ok(Self {
                release: Some(release),
                thread: Some(thread),
            })
        }
    }

    impl Drop for MaintenanceLease {
        fn drop(&mut self) {
            if let Some(release) = self.release.take() {
                let _ = release.send(());
            }
            if let Some(thread) = self.thread.take() {
                let _ = thread.join();
            }
        }
    }

    #[derive(Clone, Copy)]
    enum GateError {
        Unavailable,
        Busy,
    }

    /// Handles owned by the dedicated gate thread. Drop order is fixed so the
    /// event is cleared before the mutex is released, all on the owner thread.
    struct OwnedGate {
        mutex: usize,
        event: usize,
        maintenance: bool,
    }

    impl Drop for OwnedGate {
        fn drop(&mut self) {
            unsafe {
                if self.maintenance && self.event != 0 {
                    ResetEvent(self.event as *mut std::ffi::c_void);
                }
                if self.mutex != 0 {
                    ReleaseMutex(self.mutex as *mut std::ffi::c_void);
                    CloseHandle(self.mutex as *mut std::ffi::c_void);
                }
                if self.event != 0 {
                    CloseHandle(self.event as *mut std::ffi::c_void);
                }
            }
        }
    }

    fn spawn_gate_owner(
        installation_id: &str,
        maintenance_owner: bool,
    ) -> Result<(std::sync::mpsc::Sender<()>, std::thread::JoinHandle<()>), HostError> {
        let (ready_tx, ready_rx) = std::sync::mpsc::channel::<Result<(), GateError>>();
        let (release_tx, release_rx) = std::sync::mpsc::channel::<()>();
        let id = installation_id.to_owned();
        let thread = std::thread::Builder::new()
            .name("operon-maintenance-gate".to_owned())
            .spawn(move || {
                let gate = match acquire_gate(&id, maintenance_owner) {
                    Ok(gate) => gate,
                    Err(error) => {
                        let _ = ready_tx.send(Err(error));
                        return;
                    }
                };
                if ready_tx.send(Ok(())).is_err() {
                    // The caller disappeared before it could take ownership;
                    // OwnedGate still releases on this thread as it goes out of
                    // scope.
                    return;
                }
                let _ = release_rx.recv();
                drop(gate);
            })
            .map_err(|_| HostError::bridge_unavailable())?;

        match ready_rx.recv() {
            Ok(Ok(())) => Ok((release_tx, thread)),
            Ok(Err(error)) => {
                let _ = thread.join();
                Err(match error {
                    GateError::Busy => {
                        HostError::capability_unavailable(crate::error::HostNextAction::Retry, None)
                    }
                    GateError::Unavailable => HostError::bridge_unavailable(),
                })
            }
            Err(_) => {
                let _ = thread.join();
                Err(HostError::bridge_unavailable())
            }
        }
    }

    fn acquire_gate(
        installation_id: &str,
        maintenance_owner: bool,
    ) -> Result<OwnedGate, GateError> {
        let hash = installation_hash(installation_id);
        let mutex_name = wide(&format!("{MUTEX_PREFIX}{hash}"));
        let event_name = wide(&format!("{MUTEX_PREFIX}{hash}{EVENT_SUFFIX}"));
        let mutex = unsafe { CreateMutexW(std::ptr::null(), 0, mutex_name.as_ptr()) };
        if mutex.is_null() {
            return Err(GateError::Unavailable);
        }
        let wait = unsafe { WaitForSingleObject(mutex, 0) };
        if wait != WAIT_OBJECT_0 && wait != WAIT_ABANDONED {
            unsafe {
                CloseHandle(mutex);
            }
            return Err(GateError::Busy);
        }

        let event = unsafe { CreateEventW(std::ptr::null(), 1, 0, event_name.as_ptr()) };
        if event.is_null() {
            unsafe {
                ReleaseMutex(mutex);
                CloseHandle(mutex);
            }
            return Err(GateError::Unavailable);
        }

        let gate = OwnedGate {
            mutex: mutex as usize,
            event: event as usize,
            maintenance: maintenance_owner,
        };
        let active = unsafe { WaitForSingleObject(event, 0) } == WAIT_OBJECT_0;
        if maintenance_owner {
            if active {
                // OwnedGate releases/ closes on this same owner thread.
                return Err(GateError::Busy);
            }
            if unsafe { SetEvent(event) } == 0 {
                return Err(GateError::Unavailable);
            }
        } else if active {
            return Err(GateError::Busy);
        }

        Ok(gate)
    }

    struct ReceiptGuard {
        path: PathBuf,
        token: String,
    }

    impl Drop for ReceiptGuard {
        fn drop(&mut self) {
            let Ok(bytes) = fs::read(&self.path) else {
                return;
            };
            let Ok(receipt) = serde_json::from_slice::<Receipt>(&bytes) else {
                return;
            };
            if receipt.token == self.token {
                let _ = fs::remove_file(&self.path);
            }
        }
    }

    /// Retained for the host lifetime so the receipt is removed only when this
    /// process still owns it.
    pub struct MaintenanceService {
        task: tauri::async_runtime::JoinHandle<()>,
        _receipt: ReceiptGuard,
    }

    impl Drop for MaintenanceService {
        fn drop(&mut self) {
            self.task.abort();
        }
    }

    #[derive(Serialize, Deserialize)]
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
    struct Request {
        schema: u32,
        installation_id: String,
        token: String,
        action: String,
        request_id: String,
    }

    #[derive(Serialize)]
    struct Response<'a> {
        schema: u32,
        request_id: &'a str,
        status: &'static str,
    }

    /// Publish the pipe and receipt, then release the startup gate. This must be
    /// called before the backend starts.
    pub fn start(app: &AppHandle) -> Result<(), HostError> {
        let state = app.state::<HostState>();
        {
            let existing = state
                .maintenance
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            if existing.is_some() {
                return Ok(());
            }
        }

        let guard = state
            .maintenance_start
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .take();
        let profile = state.config.profile.clone();
        let installation_id = state.config.installation_id.clone();
        let service = start_service(app.clone(), profile, installation_id)?;
        {
            let mut slot = state
                .maintenance
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            *slot = Some(service);
        }
        drop(guard);
        Ok(())
    }

    fn start_service(
        app: AppHandle,
        profile: PathBuf,
        installation_id: String,
    ) -> Result<MaintenanceService, HostError> {
        let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
        if !valid_token(&token) {
            return Err(HostError::bridge_unavailable());
        }
        let pipe_name = format!(
            r"\\.\pipe\OperonExperimentalMaintenance-{}-{}",
            &installation_hash(&installation_id)[..16],
            Uuid::new_v4()
        );
        // This runs from synchronous Tauri setup; creating the first pipe
        // registers it with the reactor, so enter the Tauri Tokio runtime
        // explicitly instead of panicking with "no reactor running".
        let first = tauri::async_runtime::block_on(async {
            ServerOptions::new()
                .pipe_mode(PipeMode::Byte)
                .first_pipe_instance(true)
                .reject_remote_clients(true)
                .create(&pipe_name)
        })
        .map_err(|_| HostError::bridge_unavailable())?;

        let exe = std::env::current_exe().map_err(|_| HostError::bridge_unavailable())?;
        let exe = fs::canonicalize(exe).map_err(|_| HostError::bridge_unavailable())?;
        let receipt = Receipt {
            schema: 1,
            installation_id: installation_id.clone(),
            pid: std::process::id(),
            created_filetime: process_creation_filetime()?.to_string(),
            exe: exe.to_string_lossy().to_string(),
            pipe_name: pipe_name.clone(),
            token: token.clone(),
        };
        let receipt_path = profile.join(RECEIPT_FILE);
        write_receipt(&receipt_path, &receipt)?;

        let receipt_guard = ReceiptGuard {
            path: receipt_path,
            token,
        };
        let recent = Arc::new(Mutex::new(VecDeque::new()));
        let task = tauri::async_runtime::spawn(accept_loop(
            app,
            pipe_name,
            installation_id,
            receipt.token,
            first,
            recent,
        ));
        Ok(MaintenanceService {
            task,
            _receipt: receipt_guard,
        })
    }

    async fn accept_loop(
        app: AppHandle,
        pipe_name: String,
        installation_id: String,
        token: String,
        first: NamedPipeServer,
        recent: Arc<Mutex<VecDeque<String>>>,
    ) {
        let mut next = Some(first);
        loop {
            let server = match next.take() {
                Some(server) => server,
                None => match ServerOptions::new()
                    .pipe_mode(PipeMode::Byte)
                    .first_pipe_instance(false)
                    .reject_remote_clients(true)
                    .create(&pipe_name)
                {
                    Ok(server) => server,
                    Err(_) => break,
                },
            };
            if server.connect().await.is_err() {
                break;
            }
            handle_connection(&app, server, &installation_id, &token, Arc::clone(&recent)).await;
        }
    }

    async fn handle_connection(
        app: &AppHandle,
        mut server: NamedPipeServer,
        installation_id: &str,
        token: &str,
        recent: Arc<Mutex<VecDeque<String>>>,
    ) {
        let frame = match read_frame(&mut server).await {
            Ok(frame) => frame,
            Err(_) => return,
        };
        let request = match validate_request(&frame, installation_id, token) {
            Ok(request) => request,
            Err(_) => return,
        };

        let duplicate = {
            let ids = recent
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            ids.iter().any(|value| value == &request.request_id)
        };

        let reply = Response {
            schema: 1,
            request_id: &request.request_id,
            status: "accepted",
        };
        if write_frame(&mut server, &reply).await.is_err() {
            // Do not record a request that was never accepted: a retry with the
            // same request_id must still be able to deliver the quit.
            return;
        }
        if !duplicate {
            let mut ids = recent
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            if !ids.iter().any(|value| value == &request.request_id) {
                if ids.len() == MAX_RECENT_REQUESTS {
                    ids.pop_front();
                }
                ids.push_back(request.request_id.clone());
            }
            // The existing close flow owns draft save, pending-job confirmation,
            // drain and exit status. This channel never invokes process control.
            crate::bridge::request_exit(app.clone());
        }
    }

    fn validate_request(frame: &[u8], installation_id: &str, token: &str) -> Result<Request, ()> {
        if frame.is_empty() || frame.len() > MAX_FRAME_BYTES {
            return Err(());
        }
        let request: Request = serde_json::from_slice(frame).map_err(|_| ())?;
        if request.schema != 1
            || request.installation_id != installation_id
            || request.token != token
            || request.action != "quit"
            || !valid_token(&request.token)
            || Uuid::parse_str(&request.request_id).is_err()
        {
            return Err(());
        }
        Ok(request)
    }

    async fn read_frame(server: &mut NamedPipeServer) -> io::Result<Vec<u8>> {
        let deadline = Instant::now() + READ_DEADLINE;
        let mut output = Vec::new();
        let mut buffer = [0u8; 512];
        loop {
            let remaining = deadline
                .checked_duration_since(Instant::now())
                .filter(|value| !value.is_zero())
                .ok_or_else(|| io::Error::new(io::ErrorKind::TimedOut, "deadline"))?;
            let count = tokio::time::timeout(remaining, server.read(&mut buffer))
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

    async fn write_frame(server: &mut NamedPipeServer, value: &impl Serialize) -> io::Result<()> {
        let mut body = serde_json::to_vec(value)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "json"))?;
        if body.len() >= MAX_FRAME_BYTES {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "oversized"));
        }
        body.push(b'\n');
        tokio::time::timeout(READ_DEADLINE, server.write_all(&body))
            .await
            .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "deadline"))??;
        tokio::time::timeout(READ_DEADLINE, server.flush())
            .await
            .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "deadline"))??;
        Ok(())
    }

    fn write_receipt(path: &Path, receipt: &Receipt) -> Result<(), HostError> {
        let mut body =
            serde_json::to_vec_pretty(receipt).map_err(|_| HostError::bridge_unavailable())?;
        body.push(b'\n');
        let temporary = path.with_file_name(format!("{}.tmp-{}", RECEIPT_FILE, Uuid::new_v4()));
        fs::write(&temporary, body).map_err(|_| HostError::bridge_unavailable())?;
        match fs::remove_file(path) {
            Ok(()) => {}
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(_) => {
                let _ = fs::remove_file(&temporary);
                return Err(HostError::bridge_unavailable());
            }
        }
        fs::rename(&temporary, path).map_err(|_| {
            let _ = fs::remove_file(&temporary);
            HostError::bridge_unavailable()
        })
    }

    fn process_creation_filetime() -> Result<u64, HostError> {
        let mut created: FILETIME = unsafe { std::mem::zeroed() };
        let mut exited: FILETIME = unsafe { std::mem::zeroed() };
        let mut kernel: FILETIME = unsafe { std::mem::zeroed() };
        let mut user: FILETIME = unsafe { std::mem::zeroed() };
        let ok = unsafe {
            GetProcessTimes(
                GetCurrentProcess(),
                &mut created,
                &mut exited,
                &mut kernel,
                &mut user,
            )
        };
        if ok == 0 {
            return Err(HostError::bridge_unavailable());
        }
        Ok(((created.dwHighDateTime as u64) << 32) | created.dwLowDateTime as u64)
    }

    fn valid_token(value: &str) -> bool {
        if value.len() != 72 {
            return false;
        }
        let (first, second) = value.split_at(36);
        let valid = |part: &str| {
            Uuid::parse_str(part)
                .map(|id| id.get_version_num() == 4)
                .unwrap_or(false)
        };
        valid(first) && valid(second)
    }

    fn installation_hash(value: &str) -> String {
        let digest = Sha256::digest(value.as_bytes());
        let mut output = String::with_capacity(64);
        for byte in digest {
            output.push_str(&format!("{byte:02x}"));
        }
        output
    }

    fn wide(value: &str) -> Vec<u16> {
        OsStr::new(value)
            .encode_wide()
            .chain(std::iter::once(0))
            .collect()
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        fn request(action: &str, token: &str) -> Vec<u8> {
            serde_json::to_vec(&serde_json::json!({
                "schema": 1,
                "installation_id": "installation-a",
                "token": token,
                "action": action,
                "request_id": Uuid::new_v4().to_string(),
            }))
            .unwrap()
        }

        #[test]
        fn accepts_only_the_exact_quit_action() {
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            assert!(validate_request(&request("quit", &token), "installation-a", &token).is_ok());
            assert!(validate_request(&request("run", &token), "installation-a", &token).is_err());
            assert!(validate_request(&request("quit", &token), "installation-b", &token).is_err());
        }

        #[test]
        fn rejects_malformed_tokens_and_extra_fields() {
            assert!(!valid_token(""));
            assert!(!valid_token("not-a-token"));
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            let mut value: serde_json::Value =
                serde_json::from_slice(&request("quit", &token)).unwrap();
            value["path"] = serde_json::json!("C:\\Windows");
            assert!(validate_request(
                &serde_json::to_vec(&value).unwrap(),
                "installation-a",
                &token
            )
            .is_err());
        }

        #[test]
        fn gate_names_are_installation_scoped() {
            let hash = installation_hash("installation-a");
            assert_eq!(hash.len(), 64);
            assert_ne!(hash, installation_hash("installation-b"));
            assert!(format!("{MUTEX_PREFIX}{hash}").starts_with("Local\\"));
            assert!(format!("{MUTEX_PREFIX}{hash}{EVENT_SUFFIX}").ends_with("-active"));
        }

        #[test]
        fn rejects_oversized_frames_before_parsing() {
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            let frame = vec![b'{'; MAX_FRAME_BYTES + 1];
            assert!(validate_request(&frame, "installation-a", &token).is_err());
        }

        #[test]
        fn gate_is_exclusive_and_released_from_another_thread() {
            let id = format!("gate-test-{}", Uuid::new_v4());
            let guard = StartupGuard::acquire(&id).unwrap();
            assert!(StartupGuard::acquire(&id).is_err());
            std::thread::spawn(move || drop(guard)).join().unwrap();
            drop(StartupGuard::acquire(&id).unwrap());
        }

        #[test]
        fn lease_is_exclusive_and_clears_the_active_event() {
            let id = format!("lease-test-{}", Uuid::new_v4());
            let lease = MaintenanceLease::acquire(&id).unwrap();
            assert!(StartupGuard::acquire(&id).is_err());
            std::thread::spawn(move || drop(lease)).join().unwrap();
            drop(StartupGuard::acquire(&id).unwrap());
        }
    }
}

#[cfg(windows)]
pub use windows_impl::{start, MaintenanceLease, MaintenanceService, StartupGuard, RECEIPT_FILE};

#[cfg(not(windows))]
pub struct StartupGuard;
#[cfg(not(windows))]
impl StartupGuard {
    pub fn acquire(_installation_id: &str) -> Result<Self, HostError> {
        Err(HostError::unsupported(None))
    }
}
#[cfg(not(windows))]
pub struct MaintenanceLease;
#[cfg(not(windows))]
impl MaintenanceLease {
    pub fn acquire(_installation_id: &str) -> Result<Self, HostError> {
        Err(HostError::unsupported(None))
    }
}
#[cfg(not(windows))]
pub struct MaintenanceService;
#[cfg(not(windows))]
pub fn start(_app: &tauri::AppHandle) -> Result<(), HostError> {
    Err(HostError::unsupported(None))
}
#[cfg(not(windows))]
pub const RECEIPT_FILE: &str = ".operon-maintenance-host.json";
