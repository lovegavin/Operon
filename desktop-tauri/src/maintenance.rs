//! Installation-scoped maintenance channel for the experimental Windows host.
//!
//! Authenticated requests are the graceful `quit` and the shortcut `show`.
//! A ready request replies `accepted` and then requires a matching receipt `ack`
//! on the same authenticated connection within the frame deadline before it
//! takes effect. `show` additionally returns a final `shown`/`rejected` status;
//! a `not_ready` reply is the only retryable status and never bypasses
//! maintenance or shutdown. `quit` remains byte-for-byte compatible and has no
//! post-ack frame.
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
    use crate::bridge::{ActivationVerdict, HostState};
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
    use windows_sys::Win32::Foundation::{
        CloseHandle, GetLastError, ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND, FILETIME,
        WAIT_ABANDONED, WAIT_OBJECT_0, WAIT_TIMEOUT,
    };
    use windows_sys::Win32::System::Threading::{
        CreateEventW, CreateMutexW, GetCurrentProcess, GetProcessTimes, OpenEventW, ReleaseMutex,
        ResetEvent, SetEvent, WaitForSingleObject,
    };

    pub const RECEIPT_FILE: &str = ".operon-maintenance-host.json";
    pub const MAX_FRAME_BYTES: usize = 4096;
    pub const READ_DEADLINE: Duration = Duration::from_secs(3);
    const MAX_RECENT_REQUESTS: usize = 8;
    const MUTEX_PREFIX: &str = "Local\\OperonExperimentalMaintenance-";
    const EVENT_SUFFIX: &str = "-active";
    // SYNCHRONIZE is not exported by the enabled windows-sys features.
    const SYNCHRONIZE_ACCESS: u32 = 0x0010_0000;

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

    /// Read-only check of the installation-scoped maintenance-active event.
    ///
    /// A missing event means no installation transaction is active. Any other
    /// handle/wait failure is returned as an error so callers fail closed.
    pub fn is_active(installation_id: &str) -> Result<bool, HostError> {
        let hash = installation_hash(installation_id);
        let event_name = wide(&format!("{MUTEX_PREFIX}{hash}{EVENT_SUFFIX}"));
        let event = unsafe { OpenEventW(SYNCHRONIZE_ACCESS, 0, event_name.as_ptr()) };
        if event.is_null() {
            let error = unsafe { GetLastError() };
            return if error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND {
                Ok(false)
            } else {
                Err(HostError::bridge_unavailable())
            };
        }
        let wait = unsafe { WaitForSingleObject(event, 0) };
        unsafe {
            CloseHandle(event);
        }
        match wait {
            WAIT_OBJECT_0 => Ok(true),
            WAIT_TIMEOUT => Ok(false),
            _ => Err(HostError::bridge_unavailable()),
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

    #[derive(Clone, Copy, PartialEq, Eq, Deserialize)]
    #[serde(rename_all = "lowercase")]
    enum Action {
        Quit,
        Show,
    }

    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Request {
        schema: u32,
        installation_id: String,
        token: String,
        action: Action,
        request_id: String,
    }

    /// The peer's proof that it consumed the `accepted` frame. This is only
    /// valid on the same already-authenticated connection as the request, so
    /// it intentionally carries no installation id or token.
    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Ack {
        schema: u32,
        request_id: String,
        action: String,
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
        let app = app.clone();
        let app_quit = app.clone();
        let app_show = app.clone();
        serve_connection(
            &mut server,
            installation_id,
            token,
            recent,
            move || show_precheck(&app),
            move || crate::bridge::request_exit(app_quit),
            move || async move { crate::bridge::activate_main_window(&app_show).await },
        )
        .await;
    }

    fn show_precheck(app: &AppHandle) -> ActivationVerdict {
        let state = app.state::<HostState>();
        match is_active(&state.config.installation_id) {
            Ok(false) => {}
            _ => return ActivationVerdict::Rejected,
        }
        let lifecycle = state
            .lifecycle
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        crate::bridge::activation_verdict(lifecycle.state())
    }

    /// Complete one authenticated request on the connection that carried it.
    /// `accepted` is withheld for `not_ready`/`rejected` show requests. The quit
    /// callback runs only after the peer returns the exact request id as an
    /// `ack`; a dropped connection or any other frame leaves the request
    /// unrecorded so a retry with the same id can still deliver the quit.
    async fn serve_connection<Q, S, Fut>(
        server: &mut NamedPipeServer,
        installation_id: &str,
        token: &str,
        recent: Arc<Mutex<VecDeque<String>>>,
        show_verdict: impl FnOnce() -> ActivationVerdict,
        on_quit: Q,
        on_show: S,
    ) where
        Q: FnOnce(),
        S: FnOnce() -> Fut,
        Fut: std::future::Future<Output = bool>,
    {
        let frame = match read_frame(server).await {
            Ok(frame) => frame,
            Err(_) => return,
        };
        let request = match validate_request(&frame, installation_id, token) {
            Ok(request) => request,
            Err(_) => return,
        };

        if request.action == Action::Show {
            match show_verdict() {
                ActivationVerdict::NotReady => {
                    let reply = Response {
                        schema: 1,
                        request_id: &request.request_id,
                        status: "not_ready",
                    };
                    let _ = write_frame(server, &reply).await;
                    let _ = read_frame(server).await; // Keep reply alive until consumed.
                    return;
                }
                ActivationVerdict::Rejected => {
                    let reply = Response {
                        schema: 1,
                        request_id: &request.request_id,
                        status: "rejected",
                    };
                    let _ = write_frame(server, &reply).await;
                    let _ = read_frame(server).await;
                    return;
                }
                ActivationVerdict::Ready => {}
            }
        }

        let reply = Response {
            schema: 1,
            request_id: &request.request_id,
            status: "accepted",
        };
        if write_frame(server, &reply).await.is_err() {
            // Do not record a request that was never accepted: a retry with the
            // same request_id must still be able to deliver the quit.
            return;
        }

        // A flush only drains this server's async buffer; it does not prove the
        // peer consumed the reply. Hold the accepted frame behind this bounded
        // receipt acknowledgement so the connection cannot close first.
        let ack = match read_frame(server).await {
            Ok(ack) => ack,
            Err(_) => return,
        };
        if !validate_ack(&ack, &request.request_id) {
            return;
        }

        match request.action {
            Action::Quit => {
                let newly_recorded = {
                    let mut ids = recent
                        .lock()
                        .unwrap_or_else(|poisoned| poisoned.into_inner());
                    if ids.iter().any(|value| value == &request.request_id) {
                        false
                    } else {
                        if ids.len() == MAX_RECENT_REQUESTS {
                            ids.pop_front();
                        }
                        ids.push_back(request.request_id.clone());
                        true
                    }
                };
                if newly_recorded {
                    // The existing close flow owns draft save, pending-job
                    // confirmation, drain and exit status. This channel never
                    // invokes process control.
                    on_quit();
                }
            }
            Action::Show => {
                let shown = on_show().await;
                let reply = Response {
                    schema: 1,
                    request_id: &request.request_id,
                    status: if shown { "shown" } else { "rejected" },
                };
                let _ = write_frame(server, &reply).await;
                // Flush alone cannot prove Windows pipe peer consumption. Keep
                // the final result alive until acknowledgement (or deadline).
                let _ = read_frame(server).await;
            }
        }
    }

    fn validate_ack(frame: &[u8], request_id: &str) -> bool {
        if frame.is_empty() || frame.len() > MAX_FRAME_BYTES {
            return false;
        }
        let Ok(ack) = serde_json::from_slice::<Ack>(frame) else {
            return false;
        };
        ack.schema == 1
            && ack.action == "ack"
            && ack.request_id == request_id
            && Uuid::parse_str(&ack.request_id).is_ok()
    }

    fn validate_request(frame: &[u8], installation_id: &str, token: &str) -> Result<Request, ()> {
        if frame.is_empty() || frame.len() > MAX_FRAME_BYTES {
            return Err(());
        }
        let request: Request = serde_json::from_slice(frame).map_err(|_| ())?;
        if request.schema != 1
            || request.installation_id != installation_id
            || request.token != token
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

    pub(crate) fn valid_token(value: &str) -> bool {
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
        use std::sync::atomic::{AtomicUsize, Ordering};
        use tokio::net::windows::named_pipe::ClientOptions;

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

        fn frame(value: serde_json::Value) -> Vec<u8> {
            let mut body = serde_json::to_vec(&value).unwrap();
            body.push(b'\n');
            body
        }

        fn request_frame(
            installation_id: &str,
            token: &str,
            request_id: &str,
            action: &str,
        ) -> Vec<u8> {
            frame(serde_json::json!({
                "schema": 1,
                "installation_id": installation_id,
                "token": token,
                "action": action,
                "request_id": request_id,
            }))
        }

        fn ack_frame(request_id: &str, action: &str) -> Vec<u8> {
            frame(serde_json::json!({
                "schema": 1,
                "request_id": request_id,
                "action": action,
            }))
        }

        async fn read_delayed_bytewise(
            client: &mut tokio::net::windows::named_pipe::NamedPipeClient,
        ) -> Vec<u8> {
            let mut output = Vec::new();
            let mut one = [0u8; 1];
            loop {
                let read = tokio::time::timeout(READ_DEADLINE, client.read(&mut one))
                    .await
                    .expect("accepted frame read deadline")
                    .expect("read accepted frame");
                if read == 0 {
                    panic!("maintenance pipe closed before the accepted frame ended");
                }
                if one[0] == b'\n' {
                    return output;
                }
                output.push(one[0]);
                // Deliberately slower than the server's reply write so a
                // server that closes immediately after `accepted` is caught.
                tokio::time::sleep(Duration::from_millis(2)).await;
            }
        }

        #[derive(Clone, Copy)]
        enum AckReply {
            Matching,
            Wrong,
            Missing,
        }

        async fn maintenance_round_trip(reply: AckReply) -> (usize, bool) {
            let pipe_name = format!(r"\\.\pipe\OperonMaintenanceTest-{}", Uuid::new_v4());
            let mut server = ServerOptions::new()
                .pipe_mode(PipeMode::Byte)
                .first_pipe_instance(true)
                .create(&pipe_name)
                .expect("create maintenance test server");
            let installation_id = "installation-a".to_owned();
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            let request_id = Uuid::new_v4().to_string();
            let recent = Arc::new(Mutex::new(VecDeque::new()));
            let quit_calls = Arc::new(AtomicUsize::new(0));
            let raw_request = request_frame(&installation_id, &token, &request_id, "quit");

            let server_recent = Arc::clone(&recent);
            let server_calls = Arc::clone(&quit_calls);
            let server_id = installation_id.clone();
            let server_token = token.clone();
            let server_task = tokio::spawn(async move {
                server
                    .connect()
                    .await
                    .expect("connect maintenance test client");
                serve_connection(
                    &mut server,
                    &server_id,
                    &server_token,
                    server_recent,
                    || ActivationVerdict::Ready,
                    move || {
                        server_calls.fetch_add(1, Ordering::SeqCst);
                    },
                    || async { false },
                )
                .await;
            });

            let mut client = ClientOptions::new()
                .open(&pipe_name)
                .expect("open maintenance test client");
            client
                .write_all(&raw_request)
                .await
                .expect("write quit request");
            client.flush().await.expect("flush quit request");

            let accepted = read_delayed_bytewise(&mut client).await;
            let accepted: serde_json::Value =
                serde_json::from_slice(&accepted).expect("accepted frame json");
            assert_eq!(accepted["schema"].as_u64(), Some(1));
            assert_eq!(accepted["request_id"].as_str(), Some(request_id.as_str()));
            assert_eq!(accepted["status"].as_str(), Some("accepted"));

            match reply {
                AckReply::Matching => {
                    client
                        .write_all(&ack_frame(&request_id, "ack"))
                        .await
                        .expect("write matching ack");
                    client.flush().await.expect("flush matching ack");
                }
                AckReply::Wrong => {
                    client
                        .write_all(&ack_frame(&Uuid::new_v4().to_string(), "ack"))
                        .await
                        .expect("write wrong ack");
                    client.flush().await.expect("flush wrong ack");
                }
                AckReply::Missing => {
                    // Consume accepted, then vanish without acknowledging it.
                    drop(client);
                }
            }

            tokio::time::timeout(READ_DEADLINE + Duration::from_secs(1), server_task)
                .await
                .expect("maintenance test server timed out")
                .expect("maintenance test server panicked");

            let recorded = recent
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .iter()
                .any(|value| value == &request_id);
            (quit_calls.load(Ordering::SeqCst), recorded)
        }

        #[test]
        fn accepts_only_the_exact_quit_and_show_actions() {
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            assert!(validate_request(&request("quit", &token), "installation-a", &token).is_ok());
            assert!(validate_request(&request("show", &token), "installation-a", &token).is_ok());
            assert!(validate_request(&request("run", &token), "installation-a", &token).is_err());
            assert!(validate_request(&request("SHOW", &token), "installation-a", &token).is_err());
            assert!(validate_request(&request("show", &token), "installation-b", &token).is_err());
        }

        #[test]
        fn maintenance_active_event_is_readable() {
            let id = format!("active-test-{}", Uuid::new_v4());
            assert!(!is_active(&id).unwrap());
            let lease = MaintenanceLease::acquire(&id).unwrap();
            assert!(is_active(&id).unwrap());
            drop(lease);
            assert!(!is_active(&id).unwrap());
        }

        async fn read_optional_frame(
            client: &mut tokio::net::windows::named_pipe::NamedPipeClient,
        ) -> Option<Vec<u8>> {
            let mut output = Vec::new();
            let mut one = [0u8; 1];
            loop {
                let read = tokio::time::timeout(READ_DEADLINE, client.read(&mut one))
                    .await
                    .ok()?
                    .ok()?;
                if read == 0 {
                    return None;
                }
                if one[0] == b'\n' {
                    return Some(output);
                }
                output.push(one[0]);
            }
        }

        async fn show_round_trip(
            verdict: ActivationVerdict,
            reply: AckReply,
        ) -> (String, Option<String>, usize) {
            let pipe_name = format!(r"\\.\pipe\OperonShowTest-{}", Uuid::new_v4());
            let mut server = ServerOptions::new()
                .pipe_mode(PipeMode::Byte)
                .first_pipe_instance(true)
                .create(&pipe_name)
                .expect("create show test server");
            let installation_id = "installation-a".to_owned();
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            let request_id = Uuid::new_v4().to_string();
            let show_calls = Arc::new(AtomicUsize::new(0));
            let raw_request = request_frame(&installation_id, &token, &request_id, "show");

            let server_calls = Arc::clone(&show_calls);
            let server_id = installation_id.clone();
            let server_token = token.clone();
            let server_task = tokio::spawn(async move {
                server.connect().await.expect("connect show client");
                serve_connection(
                    &mut server,
                    &server_id,
                    &server_token,
                    Arc::new(Mutex::new(VecDeque::new())),
                    move || verdict,
                    || {},
                    move || async move {
                        server_calls.fetch_add(1, Ordering::SeqCst);
                        true
                    },
                )
                .await;
            });

            let mut client = ClientOptions::new()
                .open(&pipe_name)
                .expect("open show test client");
            client.write_all(&raw_request).await.unwrap();
            client.flush().await.unwrap();
            let first = read_optional_frame(&mut client)
                .await
                .expect("first show reply");
            let first: serde_json::Value = serde_json::from_slice(&first).unwrap();
            let first_status = first["status"].as_str().unwrap().to_owned();
            assert_eq!(first["request_id"].as_str(), Some(request_id.as_str()));

            let mut final_status = None;
            if first_status == "accepted" {
                match reply {
                    AckReply::Matching => {
                        client
                            .write_all(&ack_frame(&request_id, "ack"))
                            .await
                            .unwrap();
                        client.flush().await.unwrap();
                        tokio::time::sleep(Duration::from_millis(80)).await;
                        let final_frame = read_optional_frame(&mut client)
                            .await
                            .expect("final show reply");
                        let final_frame: serde_json::Value =
                            serde_json::from_slice(&final_frame).unwrap();
                        final_status = final_frame["status"].as_str().map(str::to_owned);
                        assert_eq!(
                            final_frame["request_id"].as_str(),
                            Some(request_id.as_str())
                        );
                        client
                            .write_all(&ack_frame(&request_id, "ack"))
                            .await
                            .unwrap();
                        client.flush().await.unwrap();
                    }
                    AckReply::Wrong => {
                        client
                            .write_all(&ack_frame(&Uuid::new_v4().to_string(), "ack"))
                            .await
                            .unwrap();
                        client.flush().await.unwrap();
                    }
                    AckReply::Missing => {
                        drop(client);
                    }
                }
            } else {
                client
                    .write_all(&ack_frame(&request_id, "ack"))
                    .await
                    .unwrap();
                client.flush().await.unwrap();
            }

            tokio::time::timeout(READ_DEADLINE + Duration::from_secs(1), server_task)
                .await
                .expect("show test server timed out")
                .expect("show test server panicked");
            (
                first_status,
                final_status,
                show_calls.load(Ordering::SeqCst),
            )
        }

        #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
        async fn show_requires_ack_and_shown_before_effect() {
            let (first, final_status, calls) =
                show_round_trip(ActivationVerdict::Ready, AckReply::Matching).await;
            assert_eq!(first, "accepted");
            assert_eq!(final_status.as_deref(), Some("shown"));
            assert_eq!(calls, 1);

            let (first, final_status, calls) =
                show_round_trip(ActivationVerdict::Ready, AckReply::Wrong).await;
            assert_eq!(first, "accepted");
            assert_eq!(final_status, None);
            assert_eq!(calls, 0);

            let (first, final_status, calls) =
                show_round_trip(ActivationVerdict::Ready, AckReply::Missing).await;
            assert_eq!(first, "accepted");
            assert_eq!(final_status, None);
            assert_eq!(calls, 0);
        }

        #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
        async fn show_not_ready_and_rejected_do_not_accept_or_show() {
            let (first, final_status, calls) =
                show_round_trip(ActivationVerdict::NotReady, AckReply::Missing).await;
            assert_eq!(first, "not_ready");
            assert_eq!(final_status, None);
            assert_eq!(calls, 0);

            let (first, final_status, calls) =
                show_round_trip(ActivationVerdict::Rejected, AckReply::Missing).await;
            assert_eq!(first, "rejected");
            assert_eq!(final_status, None);
            assert_eq!(calls, 0);
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
        fn accepts_only_the_strict_matching_ack() {
            let id = Uuid::new_v4().to_string();
            assert!(validate_ack(&ack_frame(&id, "ack"), &id));
            assert!(!validate_ack(&ack_frame(&id, "quit"), &id));
            assert!(!validate_ack(
                &ack_frame(&Uuid::new_v4().to_string(), "ack"),
                &id
            ));
            assert!(!validate_ack(&ack_frame("not-a-uuid", "ack"), "not-a-uuid"));

            let mut wrong_schema: serde_json::Value =
                serde_json::from_slice(&ack_frame(&id, "ack")).unwrap();
            wrong_schema["schema"] = serde_json::json!(2);
            assert!(!validate_ack(&frame(wrong_schema), &id));
        }

        #[test]
        fn rejects_ack_frames_with_extra_fields_or_oversized_bodies() {
            let id = Uuid::new_v4().to_string();
            let mut extra: serde_json::Value =
                serde_json::from_slice(&ack_frame(&id, "ack")).unwrap();
            extra["token"] = serde_json::json!("must-not-be-accepted");
            assert!(!validate_ack(&frame(extra), &id));
            assert!(!validate_ack(b"not-json", &id));
            assert!(!validate_ack(&vec![b'{'; MAX_FRAME_BYTES + 1], &id));
            assert!(!validate_ack(&[], &id));
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

        #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
        async fn named_pipe_round_trip_requires_matching_ack_before_exit() {
            let (calls, recorded) = maintenance_round_trip(AckReply::Matching).await;
            assert_eq!(calls, 1, "matching ack did not become quit-eligible");
            assert!(recorded, "matching ack did not record the request");

            let (calls, recorded) = maintenance_round_trip(AckReply::Wrong).await;
            assert_eq!(calls, 0, "wrong ack became quit-eligible");
            assert!(!recorded, "wrong ack recorded the request");

            let (calls, recorded) = maintenance_round_trip(AckReply::Missing).await;
            assert_eq!(calls, 0, "missing ack became quit-eligible");
            assert!(!recorded, "missing ack recorded the request");
        }
    }
}

#[cfg(windows)]
pub(crate) use windows_impl::valid_token;
#[cfg(windows)]
pub use windows_impl::{
    is_active, start, MaintenanceLease, MaintenanceService, StartupGuard, RECEIPT_FILE,
};

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
pub fn is_active(_installation_id: &str) -> Result<bool, HostError> {
    Ok(false)
}
#[cfg(not(windows))]
pub const RECEIPT_FILE: &str = ".operon-maintenance-host.json";
