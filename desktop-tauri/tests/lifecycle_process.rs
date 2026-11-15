//! Real-process lifecycle tests.
//!
//! These tests are intentionally skipped, with a clear message, unless
//! `OPERON_TEST_PYTHON` names an explicit CPython >= 3.11 interpreter. They use
//! test-only loopback fixtures and never claim scientific execution.

use operon_desktop_experimental::backend::{Backend, EXPECTED_STUDIO_VERSION};
use operon_desktop_experimental::config::HostConfig;
use operon_desktop_experimental::error::{HostError, HostErrorCode, HostNextAction};
use std::fs;
use std::net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};

struct Fixture {
    root: tempfile::TempDir,
    config: HostConfig,
    backend_root: PathBuf,
}

impl Fixture {
    fn build(mode: &str, python: &Path) -> Self {
        let root = tempfile::tempdir().expect("temporary test root");
        let backend_root = root.path().join("backend");
        let scripts = backend_root.join("scripts");
        fs::create_dir_all(&scripts).expect("backend scripts directory");
        fs::copy(fixture_path("fake_studio.py"), scripts.join("desktop_server.py"))
            .expect("copy management fixture");
        fs::copy(
            fixture_path("unrelated_server.py"),
            scripts.join("unrelated_server.py"),
        )
        .expect("copy unrelated fixture");
        fs::write(scripts.join("mode.txt"), mode).expect("fixture mode");

        let frontend = root.path().join("frontend");
        fs::create_dir_all(&frontend).expect("frontend directory");
        fs::write(frontend.join("index.html"), b"<!doctype html>").expect("frontend index");
        let profile = root.path().join("profile");
        fs::create_dir_all(&profile).expect("profile directory");

        let config = HostConfig {
            installation_id: "lifecycle-test-installation".to_owned(),
            backend_root: fs::canonicalize(&backend_root).expect("canonical backend"),
            python: fs::canonicalize(python).expect("canonical test python"),
            frontend: fs::canonicalize(&frontend).expect("canonical frontend"),
            profile: fs::canonicalize(&profile).expect("canonical profile"),
        };
        Self {
            root,
            config,
            backend_root,
        }
    }
}

struct ChildGuard(Option<tokio::process::Child>);

impl ChildGuard {
    fn new(child: tokio::process::Child) -> Self {
        Self(Some(child))
    }
}

impl Drop for ChildGuard {
    fn drop(&mut self) {
        if let Some(mut child) = self.0.take() {
            let _ = child.start_kill();
        }
    }
}

fn fixture_path(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join(name)
}

fn test_python() -> Option<PathBuf> {
    let raw = std::env::var_os("OPERON_TEST_PYTHON")?;
    let path = PathBuf::from(raw);
    match fs::canonicalize(&path) {
        Ok(path) if path.is_file() => Some(path),
        _ => {
            eprintln!(
                "SKIP: OPERON_TEST_PYTHON is not an existing file: {}",
                path.display()
            );
            None
        }
    }
}

fn runtime() -> tokio::runtime::Runtime {
    tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .expect("tokio runtime")
}

fn http_client() -> reqwest::Client {
    reqwest::Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(2))
        .build()
        .expect("test HTTP client")
}

async fn expect_start_failure(config: &HostConfig) -> HostError {
    match Backend::start(config).await {
        Ok(backend) => {
            drop(backend);
            panic!("backend unexpectedly started for a failure fixture");
        }
        Err(error) => error,
    }
}

async fn wait_for_file(path: &Path, timeout: Duration) -> String {
    let deadline = Instant::now() + timeout;
    loop {
        if let Ok(value) = fs::read_to_string(path) {
            let value = value.trim();
            if !value.is_empty() {
                return value.to_owned();
            }
        }
        assert!(
            Instant::now() < deadline,
            "timed out waiting for fixture file {}",
            path.display()
        );
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}

async fn http_ok(client: &reqwest::Client, url: &str) -> bool {
    match client.get(url).send().await {
        Ok(response) => response.status().is_success(),
        Err(_) => false,
    }
}

async fn wait_http(client: &reqwest::Client, url: &str, timeout: Duration) {
    let deadline = Instant::now() + timeout;
    loop {
        if http_ok(client, url).await {
            return;
        }
        assert!(
            Instant::now() < deadline,
            "timed out waiting for loopback fixture {url}"
        );
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}

async fn wait_port_closed(port: u16, timeout: Duration) {
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let deadline = Instant::now() + timeout;
    loop {
        let connected = TcpStream::connect_timeout(&address, Duration::from_millis(100)).is_ok();
        if !connected {
            return;
        }
        assert!(
            Instant::now() < deadline,
            "timed out waiting for port {port} to close"
        );
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}

#[test]
fn delayed_ready_authenticates_and_stops() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("delayed", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let mut backend = Backend::start(&fixture.config)
            .await
            .expect("delayed fixture should become ready");
        assert!(backend.pid() > 0);
        assert_eq!(backend.origin().scheme(), "http");
        assert!(backend.origin().port().unwrap_or(0) > 0);
        assert!(backend.origin().username().is_empty());
        assert!(backend.origin().query().is_none());
        assert!(!backend.studio_token().is_empty());
        assert!(!backend.try_exited().expect("exit probe"));
        backend
            .shutdown(Duration::from_secs(5))
            .await
            .expect("delayed fixture should stop");
        assert!(backend.try_exited().expect("exit probe"));
    });
}

#[test]
fn crash_before_ready_is_a_typed_failure() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("crash", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let error = expect_start_failure(&fixture.config).await;
        assert_eq!(error.code(), HostErrorCode::HostBridgeUnavailable);
    });
}

#[test]
fn missing_runtime_fails_without_spawning() {
    let Some(python) = test_python() else {
        return;
    };
    let mut fixture = Fixture::build("normal", &python);
    fixture.config.python = fixture.root.path().join("missing-runtime").join("python.exe");
    let runtime = runtime();
    runtime.block_on(async {
        let error = expect_start_failure(&fixture.config).await;
        assert_eq!(error.code(), HostErrorCode::HostBridgeUnavailable);
    });
}

#[test]
fn occupied_unrelated_port_is_not_used() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("normal", &python);
    let occupied = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).expect("occupied port");
    let occupied_port = occupied.local_addr().expect("occupied address").port();
    let runtime = runtime();
    runtime.block_on(async {
        let mut backend = Backend::start(&fixture.config)
            .await
            .expect("fixture should start beside an occupied port");
        assert_ne!(backend.origin().port(), Some(occupied_port));
        backend.shutdown(Duration::from_secs(5)).await.expect("stop");
    });
    drop(occupied);
}

#[test]
fn unrelated_python_survives_backend_shutdown() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("normal", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let port_file = fixture.root.path().join("unrelated-port.txt");
        let child = tokio::process::Command::new(&python)
            .arg(fixture_path("unrelated_server.py"))
            .arg("--port-file")
            .arg(&port_file)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("start unrelated fixture");
        let _guard = ChildGuard::new(child);
        let port = wait_for_file(&port_file, Duration::from_secs(5)).await;
        let unrelated_url = format!("http://127.0.0.1:{port}/");
        let client = http_client();
        wait_http(&client, &unrelated_url, Duration::from_secs(5)).await;

        let mut backend = Backend::start(&fixture.config)
            .await
            .expect("backend should start");
        assert_ne!(
            backend.origin().port(),
            port.parse::<u16>().ok(),
            "owned backend must not reuse the unrelated port"
        );
        assert!(http_ok(&client, &unrelated_url).await);
        backend.shutdown(Duration::from_secs(5)).await.expect("stop");
        assert!(
            http_ok(&client, &unrelated_url).await,
            "unrelated Python process must survive backend shutdown"
        );

        let _ = client
            .get(format!("http://127.0.0.1:{port}/stop"))
            .send()
            .await;
        wait_port_closed(port.parse().expect("fixture port"), Duration::from_secs(5)).await;
    });
}

#[test]
fn breakaway_helper_survives_backend_shutdown() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("breakaway", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let mut backend = Backend::start(&fixture.config)
            .await
            .expect("breakaway fixture should start");
        let port_file = fixture.backend_root.join("scripts").join("breakaway_port.txt");
        let port = wait_for_file(&port_file, Duration::from_secs(5)).await;
        let helper_url = format!("http://127.0.0.1:{port}/");
        let client = http_client();
        wait_http(&client, &helper_url, Duration::from_secs(5)).await;

        backend.shutdown(Duration::from_secs(5)).await.expect("stop");
        assert!(
            http_ok(&client, &helper_url).await,
            "a child that explicitly broke away from the job must survive host shutdown"
        );

        let _ = client
            .get(format!("http://127.0.0.1:{port}/stop"))
            .send()
            .await;
        wait_port_closed(port.parse().expect("helper port"), Duration::from_secs(5)).await;
    });
}

#[test]
fn shutdown_timeout_is_not_reported_as_success() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("shutdown_ignore", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let mut backend = Backend::start(&fixture.config)
            .await
            .expect("fixture should start");
        let port = backend.origin().port().expect("origin port");
        let error = backend
            .shutdown(Duration::from_millis(400))
            .await
            .expect_err("ignored shutdown must not be reported as success");
        assert_eq!(error.code(), HostErrorCode::HostCapabilityUnavailable);
        assert_eq!(error.next_actions(), [HostNextAction::Retry].as_slice());
        assert!(error.retryable());
        assert!(
            !backend.try_exited().expect("exit probe"),
            "ownership must remain pending after a drain timeout"
        );

        // Dropping the Backend closes its owned job handle. That fail-safe is
        // allowed to terminate only the job-attached fixture.
        drop(backend);
        wait_port_closed(port, Duration::from_secs(5)).await;
    });
}

#[test]
fn nonzero_shutdown_exit_is_a_sticky_failure() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("exit_nonzero_on_shutdown", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let mut backend = Backend::start(&fixture.config)
            .await
            .expect("fixture should start");
        let first = backend
            .shutdown(Duration::from_secs(5))
            .await
            .expect_err("exit status 5 must not be reported as graceful shutdown");
        assert_eq!(first.code(), HostErrorCode::HostBridgeUnavailable);
        assert_eq!(
            backend.exit_status().and_then(|status| status.code()),
            Some(5),
            "the actual exit status must be retained"
        );
        assert!(backend.try_exited().expect("exit probe"));

        let second = backend
            .shutdown(Duration::from_secs(2))
            .await
            .expect_err("a repeated shutdown must preserve the failed outcome");
        assert_eq!(second.code(), first.code());
        assert_eq!(second.message(), first.message());
    });
}

#[test]
fn parent_exit_does_not_count_as_tree_drain() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("parent_exits_child_lives", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let mut backend = Backend::start(&fixture.config)
            .await
            .expect("fixture should start");

        // The parent exits normally after spawning a non-breakaway helper that
        // inherits stdout/stderr. Parent exit alone must not be accepted.
        let error = backend
            .shutdown(Duration::from_secs(3))
            .await
            .expect_err("a live job-attached helper must keep the drain pending");
        assert_eq!(error.code(), HostErrorCode::HostCapabilityUnavailable);
        assert_eq!(error.next_actions(), [HostNextAction::Retry].as_slice());
        assert!(backend.try_exited().expect("parent exit probe"));
        assert!(
            backend
                .exit_status()
                .is_some_and(|status| status.success()),
            "the parent exit itself was normal"
        );

        let port_file = fixture
            .backend_root
            .join("scripts")
            .join("parent_exit_child_port.txt");
        let port = wait_for_file(&port_file, Duration::from_secs(5)).await;
        let helper_url = format!("http://127.0.0.1:{port}/");
        let client = http_client();
        wait_http(&client, &helper_url, Duration::from_secs(5)).await;

        // Ending the helper empties the job; a retried shutdown can now succeed.
        let _ = client
            .get(format!("http://127.0.0.1:{port}/stop"))
            .send()
            .await;
        wait_port_closed(port.parse().expect("helper port"), Duration::from_secs(5)).await;
        backend
            .shutdown(Duration::from_secs(5))
            .await
            .expect("shutdown should succeed after the owned tree drains");
    });
}

#[test]
fn identity_mismatch_fails_startup() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("wrong_identity", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let error = expect_start_failure(&fixture.config).await;
        assert_eq!(error.code(), HostErrorCode::HostBridgeUnavailable);
    });
}

#[test]
fn ready_pid_mismatch_fails_startup() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("wrong_pid", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let error = expect_start_failure(&fixture.config).await;
        assert_eq!(error.code(), HostErrorCode::HostBridgeUnavailable);
    });
}

#[test]
fn studio_version_mismatch_fails_startup() {
    let Some(python) = test_python() else {
        return;
    };
    let fixture = Fixture::build("wrong_version", &python);
    let runtime = runtime();
    runtime.block_on(async {
        let error = expect_start_failure(&fixture.config).await;
        assert_eq!(error.code(), HostErrorCode::HostBridgeUnavailable);
        assert_eq!(EXPECTED_STUDIO_VERSION, "5.3.0");
    });
}
