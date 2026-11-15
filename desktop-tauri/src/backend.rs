//! Owned desktop management-service process and authenticated readiness.
//!
//! Exactly one Tokio child is spawned from the configured interpreter with the
//! frozen management-service arguments. On Windows it is attached to the owned
//! Job Object before the `start\n` handshake is written. Nothing here searches
//! `PATH` at runtime, attaches to an arbitrary service, or kills processes by
//! name. Startup failure cleans only this child and this job. A shutdown timeout
//! returns a retryable failure and retains ownership instead of claiming success.

use crate::config::HostConfig;
use crate::error::{HostError, HostNextAction};
use crate::logging::Diagnostics;
use crate::windows::JobObject;
use serde::Deserialize;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::process::{ExitStatus, Stdio};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::io::{AsyncBufRead, AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, ChildStdout, Command};
use tokio::sync::mpsc;
use tokio::task::JoinHandle;
use url::Url;

/// Management service version accepted by this host integration.
pub const EXPECTED_STUDIO_VERSION: &str = "5.3.0";
/// Full startup budget, including readiness, receipt publication and auth.
pub const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);
/// Maximum accepted management-service stdout line.
pub const MAX_STDOUT_LINE_BYTES: usize = 64 * 1024;

const MAX_STDERR_LINE_BYTES: usize = 64 * 1024;
const MAX_RECEIPT_BYTES: u64 = 64 * 1024;
const MAX_RECEIPT_SECRET_BYTES: usize = 512;
const MAX_IDENTITY_BYTES: usize = 64 * 1024;
const MAX_READY_BYTES: usize = 64 * 1024;
const MAX_BOOTSTRAP_BYTES: usize = 32 * 1024 * 1024;
const MAX_TOKEN_BYTES: usize = 4096;
const RECEIPT_POLL: Duration = Duration::from_millis(50);
const CHILD_POLL: Duration = Duration::from_millis(100);
const HTTP_DEADLINE: Duration = Duration::from_secs(5);

/// An owned management service with retained child identity, Job Object,
/// authenticated origin and the bootstrap studio token.
///
/// Deliberately no `Debug` implementation: `studio_token` must never be printed
/// or embedded in a diagnostic URL.
pub struct Backend {
    child: Child,
    stdin: Option<ChildStdin>,
    _job: JobObject,
    pid: u32,
    origin: Url,
    token: String,
    diagnostics: Arc<Diagnostics>,
    stdout_task: Option<JoinHandle<()>>,
    stderr_task: Option<JoinHandle<()>>,
    exit_status: Option<ExitStatus>,
    exit_failure: Option<HostError>,
    shutdown_succeeded: bool,
}

impl Backend {
    /// Spawn and authenticate the owned service. All failures are safe
    /// `HostError`s; arbitrary child/HTTP text never reaches the message.
    pub async fn start(config: &HostConfig) -> Result<Self, HostError> {
        let deadline = Instant::now() + STARTUP_TIMEOUT;
        Self::start_until(config, deadline).await
    }

    async fn start_until(config: &HostConfig, deadline: Instant) -> Result<Self, HostError> {
        let script = config.backend_root.join("scripts/desktop_server.py");
        if !config.python.is_absolute()
            || !config.backend_root.is_absolute()
            || !config.frontend.is_absolute()
            || !config.profile.is_absolute()
            || !config.python.is_file()
            || !script.is_file()
            || !config.frontend.join("index.html").is_file()
        {
            return Err(HostError::bridge_unavailable());
        }

        config
            .ensure_experimental_profile()
            .map_err(|_| HostError::bridge_unavailable())?;

        let diagnostics = Arc::new(
            Diagnostics::open(&config.logs_dir()).map_err(|_| HostError::bridge_unavailable())?,
        );
        diagnostics.host("starting owned management service");

        let client = build_http_client()?;
        let job = JobObject::create().map_err(|_| {
            diagnostics.host("cannot create the owned Windows job");
            HostError::bridge_unavailable()
        })?;

        let mut command = Command::new(&config.python);
        command
            .arg("-I")
            .arg("-X")
            .arg("utf8")
            .arg("-B")
            .arg("-u")
            .arg(&script)
            .arg("--profile-dir")
            .arg(&config.profile)
            .arg("--frontend")
            .arg(&config.frontend)
            .arg("--port")
            .arg("0")
            .arg("--wait-for-host");
        command.current_dir(&config.backend_root);
        command.env_clear();
        configure_environment(&mut command, config);
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        command.kill_on_drop(false);
        #[cfg(windows)]
        {
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }

        let mut child = command.spawn().map_err(|error| {
            diagnostics.host(&format!("cannot spawn the configured interpreter: {error}"));
            HostError::bridge_unavailable()
        })?;
        let pid = child.id().ok_or_else(|| {
            diagnostics.host("spawned child has no retained process identity");
            HostError::bridge_unavailable()
        })?;

        if let Err(error) = job.assign(&child) {
            diagnostics.host("cannot attach the child to the owned job");
            cleanup_owned(&mut child, &job, None, None, &diagnostics).await;
            return Err(error);
        }

        let (mut stdin, stdout, stderr) = match (
            child.stdin.take(),
            child.stdout.take(),
            child.stderr.take(),
        ) {
            (Some(stdin), Some(stdout), Some(stderr)) => (stdin, stdout, stderr),
            _ => {
                diagnostics.host("child pipes are unavailable");
                cleanup_owned(&mut child, &job, None, None, &diagnostics).await;
                return Err(HostError::bridge_unavailable());
            }
        };

        let (startup_tx, mut startup_rx) = mpsc::channel(8);
        let stdout_task = tokio::spawn(read_stdout(stdout, startup_tx, Arc::clone(&diagnostics)));
        let stderr_task = tokio::spawn(read_stderr(stderr, Arc::clone(&diagnostics)));

        // Job attachment is complete before this handshake is written.
        if stdin.write_all(b"start\n").await.is_err() || stdin.flush().await.is_err() {
            diagnostics.host("cannot write the start handshake to the owned child");
            cleanup_owned(
                &mut child,
                &job,
                Some(stdout_task),
                Some(stderr_task),
                &diagnostics,
            )
            .await;
            return Err(HostError::bridge_unavailable());
        }

        let proof = match wait_for_startup(
            &mut child,
            &mut startup_rx,
            deadline,
            config,
            &client,
            &diagnostics,
            pid,
        )
        .await
        {
            Ok(proof) => proof,
            Err(error) => {
                cleanup_owned(
                    &mut child,
                    &job,
                    Some(stdout_task),
                    Some(stderr_task),
                    &diagnostics,
                )
                .await;
                return Err(error);
            }
        };

        if child
            .try_wait()
            .map_err(|_| HostError::bridge_unavailable())?
            .is_some()
        {
            diagnostics.host("owned child exited during final startup verification");
            cleanup_owned(
                &mut child,
                &job,
                Some(stdout_task),
                Some(stderr_task),
                &diagnostics,
            )
            .await;
            return Err(HostError::bridge_unavailable());
        }

        diagnostics.host("owned management service is ready and authenticated");
        Ok(Self {
            child,
            stdin: Some(stdin),
            _job: job,
            pid,
            origin: proof.origin,
            token: proof.token,
            diagnostics,
            stdout_task: Some(stdout_task),
            stderr_task: Some(stderr_task),
            exit_status: None,
            exit_failure: None,
            shutdown_succeeded: false,
        })
    }

    pub fn pid(&self) -> u32 {
        self.pid
    }

    pub fn origin(&self) -> &Url {
        &self.origin
    }

    pub fn studio_token(&self) -> &str {
        &self.token
    }

    /// The actual parent exit status, once observed by `try_exited` or
    /// `shutdown`. The status is retained rather than reduced to a bool.
    pub fn exit_status(&self) -> Option<ExitStatus> {
        self.exit_status
    }

    /// Non-blocking check for parent-process exit.
    ///
    /// `true` means the parent has exited; it does not mean the whole owned job
    /// is empty. A monitor must call `shutdown` (or otherwise query the job
    /// tree) before treating the service as drained.
    pub fn try_exited(&mut self) -> Result<bool, HostError> {
        if self.exit_status.is_some() {
            return Ok(true);
        }
        match self.child.try_wait() {
            Ok(Some(status)) => {
                self.observe_exit(status);
                Ok(true)
            }
            Ok(None) => Ok(false),
            Err(_) => Err(HostError::bridge_unavailable()),
        }
    }

    /// Ask the parent to exit and wait for the entire owned job tree.
    ///
    /// Success requires a normal parent exit status **and** zero active
    /// processes in the owned Job Object. A parent exit with a nonzero status
    /// is a sticky failure: repeated calls return the same error, never success.
    /// If the parent exits normally but a non-breakaway helper remains, this
    /// waits within the caller's deadline and then returns a retryable failure
    /// while retaining child/job ownership. No forced kill is reported as a
    /// successful graceful shutdown.
    pub async fn shutdown(&mut self, timeout: Duration) -> Result<(), HostError> {
        if self.shutdown_succeeded {
            return Ok(());
        }
        if let Some(error) = &self.exit_failure {
            return Err(error.clone());
        }

        // A parent that already exited must not be sent another handshake.
        if self.exit_status.is_none() {
            if let Some(mut stdin) = self.stdin.take() {
                let write = async {
                    let _ = stdin.write_all(b"shutdown\n").await;
                    let _ = stdin.flush().await;
                };
                let write_bound = timeout.min(Duration::from_secs(1));
                let _ = tokio::time::timeout(write_bound, write).await;
                // Dropping stdin also gives the existing service EOF, which it
                // already treats as a host exit request.
            }
        } else {
            // The parent is already gone; close our write end rather than
            // leaving an unused pipe handle open for the rest of host life.
            drop(self.stdin.take());
        }

        let deadline = Instant::now() + timeout;
        loop {
            if self.exit_status.is_none() {
                match self.child.try_wait() {
                    Ok(Some(status)) => self.observe_exit(status),
                    Ok(None) => {}
                    Err(_) => return Err(HostError::bridge_unavailable()),
                }
            }

            // A nonzero parent exit is a permanent failure, even when the job
            // has no remaining processes. Preserve it across repeated calls.
            if let Some(error) = &self.exit_failure {
                return Err(error.clone());
            }

            if self
                .exit_status
                .as_ref()
                .is_some_and(|status| status.success())
            {
                let active = self._job.active_processes()?;
                if active == 0 {
                    self.shutdown_succeeded = true;
                    self.finish_logging().await;
                    return Ok(());
                }
            }

            let now = Instant::now();
            if now >= deadline {
                self.diagnostics
                    .host("owned management tree did not stop before the drain deadline");
                return Err(HostError::capability_unavailable(
                    HostNextAction::Retry,
                    None,
                ));
            }
            let remaining = deadline.saturating_duration_since(now);
            tokio::time::sleep(remaining.min(Duration::from_millis(25))).await;
        }
    }

    fn observe_exit(&mut self, status: ExitStatus) {
        if self.exit_status.is_some() {
            return;
        }
        self.exit_status = Some(status);
        if !status.success() {
            self.exit_failure = Some(HostError::bridge_unavailable());
        }
    }

    async fn finish_logging(&mut self) {
        for task in [self.stdout_task.take(), self.stderr_task.take()]
            .into_iter()
            .flatten()
        {
            let abort = task.abort_handle();
            if tokio::time::timeout(Duration::from_secs(2), task)
                .await
                .is_err()
            {
                abort.abort();
            }
        }
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        // The Job Object field is closed after this body runs. KILL_ON_JOB_CLOSE
        // is the fail-safe for host death; this is not a process-name cleanup.
        if let Some(task) = self.stdout_task.take() {
            task.abort();
        }
        if let Some(task) = self.stderr_task.take() {
            task.abort();
        }
    }
}

struct StartupProof {
    origin: Url,
    token: String,
}

enum StartupEvent {
    Ready(ReadyLine),
    StartupError,
    Protocol,
}

#[derive(Deserialize)]
struct ReadyLine {
    url: String,
    pid: u32,
}

#[derive(Deserialize)]
struct Receipt {
    instance_id: String,
    url: String,
    pid: u32,
    secret: String,
    #[serde(default)]
    api_version: u32,
}

#[derive(Deserialize)]
struct IdentityResponse {
    instance_id: String,
}

#[derive(Deserialize)]
struct ReadyResponse {
    status: String,
    studio: String,
}

#[derive(Deserialize)]
struct BootstrapResponse {
    token: String,
    storage: StorageResponse,
}

#[derive(Deserialize)]
struct StorageResponse {
    #[serde(default)]
    profile_dir: Option<PathBuf>,
    workspace: PathBuf,
    #[serde(default)]
    data_dir: Option<PathBuf>,
}

async fn wait_for_startup(
    child: &mut Child,
    startup_rx: &mut mpsc::Receiver<StartupEvent>,
    deadline: Instant,
    config: &HostConfig,
    client: &reqwest::Client,
    diagnostics: &Diagnostics,
    expected_pid: u32,
) -> Result<StartupProof, HostError> {
    let ready = loop {
        if child
            .try_wait()
            .map_err(|_| HostError::bridge_unavailable())?
            .is_some()
        {
            diagnostics.host("owned child exited before readiness");
            return Err(HostError::bridge_unavailable());
        }

        let remaining = match deadline_remaining(deadline) {
            Some(remaining) => remaining,
            None => return Err(startup_timeout()),
        };

        tokio::select! {
            event = startup_rx.recv() => {
                match event {
                    Some(StartupEvent::Ready(ready)) => break ready,
                    Some(StartupEvent::StartupError) => {
                        diagnostics.host("owned child reported a startup error");
                        return Err(HostError::bridge_unavailable());
                    }
                    Some(StartupEvent::Protocol) => {
                        diagnostics.host("owned child violated the readiness line protocol");
                        return Err(HostError::bridge_unavailable());
                    }
                    None => {
                        diagnostics.host("owned child closed stdout before readiness");
                        return Err(HostError::bridge_unavailable());
                    }
                }
            }
            _ = tokio::time::sleep(remaining.min(CHILD_POLL)) => {}
        }
    };

    let origin = validate_loopback_origin(&ready.url).ok_or_else(|| {
        diagnostics.host("readiness URL is not the expected loopback origin");
        HostError::bridge_unavailable()
    })?;
    if ready.pid != expected_pid {
        diagnostics.host("readiness pid does not match the retained child pid");
        return Err(HostError::bridge_unavailable());
    }

    let receipt_directory = config
        .profile
        .join("workspace")
        .join(".studio")
        .join("agent")
        .join("servers");
    let receipt = loop {
        if child
            .try_wait()
            .map_err(|_| HostError::bridge_unavailable())?
            .is_some()
        {
            diagnostics.host("owned child exited before publishing its instance receipt");
            return Err(HostError::bridge_unavailable());
        }
        if let Some(receipt) = match scan_receipts(&receipt_directory, expected_pid, &origin) {
            Ok(receipt) => receipt,
            Err(error) => {
                diagnostics.host("cannot read the owned profile instance receipts");
                return Err(error);
            }
        } {
            break receipt;
        }

        let remaining = match deadline_remaining(deadline) {
            Some(remaining) => remaining,
            None => return Err(startup_timeout()),
        };
        tokio::time::sleep(remaining.min(RECEIPT_POLL)).await;
    };
    diagnostics.add_secret(&receipt.secret);
    diagnostics.host("owned instance receipt matched the child identity");

    let identity_timeout = request_timeout(deadline)?;
    let identity_body = get_limited(
        client,
        &origin,
        "/api/agent/identity",
        Some(&receipt.secret),
        MAX_IDENTITY_BYTES,
        identity_timeout,
    )
    .await?;
    let identity: IdentityResponse = serde_json::from_slice(&identity_body).map_err(|_| {
        diagnostics.host("identity response is not valid JSON");
        HostError::bridge_unavailable()
    })?;
    if identity.instance_id != receipt.instance_id {
        diagnostics.host("identity response does not match the receipt instance");
        return Err(HostError::bridge_unavailable());
    }

    let ready_timeout = request_timeout(deadline)?;
    let ready_body = get_limited(
        client,
        &origin,
        "/ready",
        None,
        MAX_READY_BYTES,
        ready_timeout,
    )
    .await?;
    let ready_response: ReadyResponse = serde_json::from_slice(&ready_body).map_err(|_| {
        diagnostics.host("ready response is not valid JSON");
        HostError::bridge_unavailable()
    })?;
    if ready_response.status != "ok" || ready_response.studio != EXPECTED_STUDIO_VERSION {
        diagnostics.host("ready response has an unexpected status or studio version");
        return Err(HostError::bridge_unavailable());
    }

    let bootstrap_timeout = request_timeout(deadline)?;
    let bootstrap_body = get_limited(
        client,
        &origin,
        "/api/bootstrap",
        None,
        MAX_BOOTSTRAP_BYTES,
        bootstrap_timeout,
    )
    .await?;
    let bootstrap: BootstrapResponse = serde_json::from_slice(&bootstrap_body).map_err(|_| {
        diagnostics.host("bootstrap response is not valid JSON");
        HostError::bridge_unavailable()
    })?;
    if !valid_token(&bootstrap.token) {
        diagnostics.host("bootstrap token is empty or malformed");
        return Err(HostError::bridge_unavailable());
    }
    verify_storage(config, &bootstrap.storage).map_err(|error| {
        diagnostics.host("bootstrap storage does not match the configured profile");
        error
    })?;

    if child
        .try_wait()
        .map_err(|_| HostError::bridge_unavailable())?
        .is_some()
    {
        diagnostics.host("owned child exited during authentication");
        return Err(HostError::bridge_unavailable());
    }

    diagnostics.add_secret(&bootstrap.token);
    Ok(StartupProof {
        origin,
        token: bootstrap.token,
    })
}

fn verify_storage(config: &HostConfig, storage: &StorageResponse) -> Result<(), HostError> {
    let expected_profile =
        fs::canonicalize(&config.profile).map_err(|_| HostError::bridge_unavailable())?;
    let expected_workspace = fs::canonicalize(config.profile.join("workspace"))
        .map_err(|_| HostError::bridge_unavailable())?;
    let expected_data =
        fs::canonicalize(config.profile.join("workspace").join(".studio"))
            .map_err(|_| HostError::bridge_unavailable())?;

    let reported_profile = storage
        .profile_dir
        .as_ref()
        .and_then(|path| fs::canonicalize(path).ok());
    let reported_workspace = fs::canonicalize(&storage.workspace).ok();
    let reported_data = storage
        .data_dir
        .as_ref()
        .and_then(|path| fs::canonicalize(path).ok());

    if reported_profile.as_deref() != Some(expected_profile.as_path())
        || reported_workspace.as_deref() != Some(expected_workspace.as_path())
        || reported_data.as_deref() != Some(expected_data.as_path())
    {
        return Err(HostError::bridge_unavailable());
    }
    Ok(())
}

fn scan_receipts(
    directory: &Path,
    expected_pid: u32,
    expected_origin: &Url,
) -> Result<Option<Receipt>, HostError> {
    let entries = match fs::read_dir(directory) {
        Ok(entries) => entries,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err(HostError::bridge_unavailable()),
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        let metadata = match fs::metadata(&path) {
            Ok(metadata) => metadata,
            Err(_) => continue,
        };
        if !metadata.is_file() || metadata.len() > MAX_RECEIPT_BYTES {
            continue;
        }
        let bytes = match fs::read(&path) {
            Ok(bytes) => bytes,
            Err(_) => continue,
        };
        let receipt: Receipt = match serde_json::from_slice(&bytes) {
            Ok(receipt) => receipt,
            Err(_) => continue,
        };
        if receipt.pid != expected_pid
            || receipt.api_version != 1
            || !valid_instance_id(&receipt.instance_id)
            || !valid_receipt_secret(&receipt.secret)
        {
            continue;
        }
        let receipt_origin = match validate_loopback_origin(&receipt.url) {
            Some(origin) => origin,
            None => continue,
        };
        if same_origin(&receipt_origin, expected_origin) {
            return Ok(Some(receipt));
        }
    }
    Ok(None)
}

fn validate_loopback_origin(value: &str) -> Option<Url> {
    let url = Url::parse(value).ok()?;
    if url.scheme() != "http"
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || url.path() != "/"
    {
        return None;
    }
    match url.host() {
        Some(url::Host::Ipv4(address)) if address == std::net::Ipv4Addr::LOCALHOST => {}
        _ => return None,
    }
    if url.port()? == 0 {
        return None;
    }
    Some(url)
}

fn same_origin(left: &Url, right: &Url) -> bool {
    left.scheme() == right.scheme()
        && left.host() == right.host()
        && left.port_or_known_default() == right.port_or_known_default()
}

fn valid_instance_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value.chars().all(|character| character.is_ascii_graphic())
}

fn valid_receipt_secret(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_RECEIPT_SECRET_BYTES
        && value.is_ascii()
        && !value.chars().any(char::is_control)
}

fn valid_token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_TOKEN_BYTES
        && value.chars().all(|character| character.is_ascii_graphic())
}

fn build_http_client() -> Result<reqwest::Client, HostError> {
    reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .no_proxy()
        .connect_timeout(Duration::from_secs(2))
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|_| HostError::bridge_unavailable())
}

async fn get_limited(
    client: &reqwest::Client,
    origin: &Url,
    path: &str,
    secret: Option<&str>,
    maximum: usize,
    request_timeout: Duration,
) -> Result<Vec<u8>, HostError> {
    let mut url = origin.clone();
    url.set_path(path);
    url.set_query(None);
    url.set_fragment(None);

    let mut request = client.get(url).timeout(request_timeout);
    if let Some(secret) = secret {
        request = request.header("x-operon-bridge", secret);
    }
    let mut response = request.send().await.map_err(|_| HostError::bridge_unavailable())?;
    if !response.status().is_success() {
        return Err(HostError::bridge_unavailable());
    }
    if response
        .content_length()
        .is_some_and(|length| length > maximum as u64)
    {
        return Err(HostError::bridge_unavailable());
    }

    let capacity = response
        .content_length()
        .map(|length| length.min(maximum as u64) as usize)
        .unwrap_or(0);
    let mut body = Vec::with_capacity(capacity);
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| HostError::bridge_unavailable())?
    {
        if body.len().saturating_add(chunk.len()) > maximum {
            return Err(HostError::bridge_unavailable());
        }
        body.extend_from_slice(&chunk);
    }
    Ok(body)
}

fn request_timeout(deadline: Instant) -> Result<Duration, HostError> {
    let remaining = deadline_remaining(deadline).ok_or_else(startup_timeout)?;
    Ok(remaining.min(HTTP_DEADLINE))
}

fn deadline_remaining(deadline: Instant) -> Option<Duration> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|remaining| !remaining.is_zero())
}

fn startup_timeout() -> HostError {
    HostError::capability_unavailable(HostNextAction::Retry, None)
}

fn configure_environment(command: &mut Command, config: &HostConfig) {
    let mut path_entries: Vec<PathBuf> = Vec::new();
    if let Some(parent) = config.python.parent() {
        path_entries.push(parent.to_path_buf());
    }
    path_entries.push(config.backend_root.clone());

    #[cfg(windows)]
    {
        use std::path::PathBuf as WindowsPath;
        if let Some(system_root) = std::env::var_os("SystemRoot") {
            let system_root = WindowsPath::from(system_root);
            path_entries.push(system_root.join("System32"));
            path_entries.push(system_root.join("System32").join("Wbem"));
            path_entries.push(system_root.clone());
            command.env("SystemRoot", &system_root);
            command.env("WINDIR", &system_root);
        }
        for variable in [
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMDATA",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "COMMONPROGRAMFILES",
            "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE",
            "OS",
        ] {
            if let Some(value) = std::env::var_os(variable) {
                command.env(variable, value);
            }
        }
        for variable in ["TEMP", "TMP"] {
            if let Some(value) = std::env::var_os(variable) {
                command.env(variable, value);
            } else {
                command.env(variable, std::env::temp_dir());
            }
        }
    }

    if let Ok(path) = std::env::join_paths(path_entries) {
        command.env("PATH", path);
    }

    // Proxy configuration is optional and only inherited from the explicit
    // proxy variables, never from a production profile/runtime override.
    for variable in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "all_proxy",
    ] {
        if let Some(value) = std::env::var_os(variable) {
            command.env(variable, value);
        }
    }

    command.env("OPERON_RUNTIME_CONFIG", config.runtime_config_path());
    command.env("OPERON_STUDIO_HOME", &config.profile);
    command.env("PYTHONIOENCODING", "utf-8");
}

async fn cleanup_owned(
    child: &mut Child,
    job: &JobObject,
    stdout_task: Option<JoinHandle<()>>,
    stderr_task: Option<JoinHandle<()>>,
    diagnostics: &Diagnostics,
) {
    diagnostics.host("startup failed; cleaning only the owned child/job");
    job.terminate();
    let _ = child.start_kill();
    let _ = tokio::time::timeout(Duration::from_secs(5), child.wait()).await;
    if let Some(task) = stdout_task {
        task.abort();
    }
    if let Some(task) = stderr_task {
        task.abort();
    }
}

enum BoundedLine {
    Eof,
    Oversized,
    Text(Vec<u8>),
}

async fn read_bounded_line<R>(reader: &mut R, maximum: usize) -> io::Result<BoundedLine>
where
    R: AsyncBufRead + Unpin,
{
    let mut output = Vec::new();
    let mut oversized = false;

    loop {
        let (consumed, newline) = {
            let buffer = reader.fill_buf().await?;
            if buffer.is_empty() {
                if oversized {
                    return Ok(BoundedLine::Oversized);
                }
                if output.is_empty() {
                    return Ok(BoundedLine::Eof);
                }
                return Ok(BoundedLine::Text(output));
            }

            if let Some(position) = buffer.iter().position(|byte| *byte == b'\n') {
                let piece = &buffer[..position];
                if !oversized {
                    if output.len().saturating_add(piece.len()) > maximum {
                        oversized = true;
                        output.clear();
                    } else {
                        output.extend_from_slice(piece);
                    }
                }
                (position + 1, true)
            } else {
                if !oversized {
                    if output.len().saturating_add(buffer.len()) > maximum {
                        oversized = true;
                        output.clear();
                    } else {
                        output.extend_from_slice(buffer);
                    }
                }
                (buffer.len(), false)
            }
        };
        reader.consume(consumed);

        if newline {
            if oversized {
                return Ok(BoundedLine::Oversized);
            }
            if output.last() == Some(&b'\r') {
                output.pop();
            }
            return Ok(BoundedLine::Text(output));
        }
    }
}

async fn read_stdout(
    stdout: ChildStdout,
    startup_tx: mpsc::Sender<StartupEvent>,
    diagnostics: Arc<Diagnostics>,
) {
    let mut reader = BufReader::new(stdout);
    let mut ready_seen = false;
    loop {
        match read_bounded_line(&mut reader, MAX_STDOUT_LINE_BYTES).await {
            Ok(BoundedLine::Eof) => break,
            Ok(BoundedLine::Oversized) => {
                diagnostics.host("owned stdout line exceeded 64 KiB and was discarded");
                if !ready_seen {
                    ready_seen = true;
                    let _ = startup_tx.send(StartupEvent::Protocol).await;
                }
            }
            Ok(BoundedLine::Text(bytes)) => {
                let line = String::from_utf8_lossy(&bytes);
                if let Some(payload) = line.strip_prefix("OPERON_READY ") {
                    if ready_seen {
                        diagnostics.host("duplicate OPERON_READY line ignored");
                        continue;
                    }
                    ready_seen = true;
                    match serde_json::from_str::<ReadyLine>(payload) {
                        Ok(ready) => {
                            diagnostics.host("owned child announced readiness");
                            let _ = startup_tx.send(StartupEvent::Ready(ready)).await;
                        }
                        Err(_) => {
                            diagnostics.host("malformed OPERON_READY line");
                            let _ = startup_tx.send(StartupEvent::Protocol).await;
                        }
                    }
                } else if line.starts_with("OPERON_STARTUP_ERROR") {
                    diagnostics.host("owned child reported OPERON_STARTUP_ERROR");
                    let _ = startup_tx.send(StartupEvent::StartupError).await;
                } else {
                    diagnostics.stdout_line(&line);
                }
            }
            Err(_) => {
                diagnostics.host("owned stdout read failed");
                break;
            }
        }
    }
}

async fn read_stderr(stderr: tokio::process::ChildStderr, diagnostics: Arc<Diagnostics>) {
    let mut reader = BufReader::new(stderr);
    loop {
        match read_bounded_line(&mut reader, MAX_STDERR_LINE_BYTES).await {
            Ok(BoundedLine::Eof) => break,
            Ok(BoundedLine::Oversized) => {
                diagnostics.host("owned stderr line exceeded 64 KiB and was discarded");
            }
            Ok(BoundedLine::Text(bytes)) => {
                diagnostics.stderr_line(&String::from_utf8_lossy(&bytes));
            }
            Err(_) => {
                diagnostics.host("owned stderr read failed");
                break;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn loopback_origin_accepts_only_clean_ipv4_http() {
        assert!(validate_loopback_origin("http://127.0.0.1:43123/").is_some());
        assert!(validate_loopback_origin("http://127.0.0.1:43123").is_some());
        assert!(validate_loopback_origin("http://localhost:43123/").is_none());
        assert!(validate_loopback_origin("http://[::1]:43123/").is_none());
        assert!(validate_loopback_origin("https://127.0.0.1:43123/").is_none());
        assert!(validate_loopback_origin("http://127.0.0.1:0/").is_none());
        assert!(validate_loopback_origin("http://127.0.0.1:43123/?token=1").is_none());
        assert!(validate_loopback_origin("http://user@127.0.0.1:43123/").is_none());
        assert!(validate_loopback_origin("http://127.0.0.1:43123/api").is_none());
    }

    #[test]
    fn receipt_secret_validation_is_bounded() {
        assert!(valid_receipt_secret("abc_DEF-123"));
        assert!(!valid_receipt_secret(""));
        assert!(!valid_receipt_secret("with space"));
        assert!(!valid_receipt_secret(&"x".repeat(MAX_RECEIPT_SECRET_BYTES + 1)));
    }

    #[test]
    fn receipt_scan_requires_exact_pid_and_origin() {
        let directory = tempfile::tempdir().unwrap();
        let origin = validate_loopback_origin("http://127.0.0.1:45000/").unwrap();
        fs::write(
            directory.path().join("a.json"),
            br#"{"protocol_version":1,"instance_id":"abc","url":"http://127.0.0.1:45000","pid":7,"created":1.0,"secret":"s","headless":false,"api_version":1}"#,
        )
        .unwrap();
        assert!(scan_receipts(directory.path(), 7, &origin).unwrap().is_some());
        assert!(scan_receipts(directory.path(), 8, &origin).unwrap().is_none());
        let other = validate_loopback_origin("http://127.0.0.1:45001/").unwrap();
        assert!(scan_receipts(directory.path(), 7, &other).unwrap().is_none());
    }
}
