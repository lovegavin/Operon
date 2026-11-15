//! Tauri-facing host bridge for the experimental desktop shell.
//!
//! This module owns the only IPC commands, the runtime capability for the exact
//! owned backend origin, startup/drain orchestration, and the fixed native
//! window/tray policy. It never treats renderer arguments as authority: every
//! command re-checks the caller's window label and exact URL.
//!
//! No token is ever logged, embedded in a URL, or written to the smoke receipt.

use crate::backend::Backend;
use crate::config::HostConfig;
use crate::dialogs::SelectPathKind;
use crate::error::{HostError, HostNextAction};
use crate::instance::InstanceGuard;
use crate::lifecycle::{FlushOutcome, Lifecycle, LifecycleState};
use crate::navigation;
use serde::{Deserialize, Serialize};
use std::net::Ipv4Addr;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Mutex, MutexGuard, RwLock, RwLockReadGuard};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::ipc::CapabilityBuilder;
use tauri::menu::MenuBuilder;
use tauri::tray::TrayIconBuilder;
use tauri::webview::NewWindowResponse;
use tauri::{
    AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder, Window,
    WindowEvent,
};
use tokio::sync::Mutex as AsyncMutex;
use url::Url;

/// Label of the owned remote UI window. It is the only window granted host IPC.
pub const MAIN_LABEL: &str = "main";
/// Label of the static local startup/diagnostic window. It never receives a
/// runtime capability and therefore cannot invoke host commands.
pub const DIAGNOSTICS_LABEL: &str = "diagnostics";
/// Event emitted to the main webview exactly once per close request.
pub const PREPARE_CLOSE_EVENT: &str = "operon://prepare-close";
/// Deadline for the renderer draft-flush acknowledgement.
pub const DRAFT_FLUSH_TIMEOUT: Duration = Duration::from_secs(5);
/// Deadline for the owned backend to drain after a confirmed close.
pub const BACKEND_DRAIN_TIMEOUT: Duration = Duration::from_secs(8);
/// Bounded response accepted from the existing `/api/jobs` history endpoint.
const MAX_JOBS_BYTES: usize = 2 * 1024 * 1024;

/// Shared native host state. The instance guard is retained until the process
/// actually exits; the backend is retained until a confirmed shutdown.
pub struct HostState {
    pub config: HostConfig,
    pub backend: AsyncMutex<Option<Backend>>,
    pub lifecycle: Mutex<Lifecycle>,
    pub expected_origin: RwLock<Option<Url>>,
    pub smoke: bool,
    pub instance: InstanceGuard,
    startup_cancelled: AtomicBool,
    startup_finished: AtomicBool,
    drain_started: AtomicBool,
    confirming_exit: AtomicBool,
    smoke_close_started: AtomicBool,
    shell_failed: AtomicBool,
    smoke_events: Mutex<Vec<SmokeEvent>>,
}

impl HostState {
    pub fn new(config: HostConfig, instance: InstanceGuard, smoke: bool) -> Self {
        Self {
            config,
            backend: AsyncMutex::new(None),
            lifecycle: Mutex::new(Lifecycle::new()),
            expected_origin: RwLock::new(None),
            smoke,
            instance,
            startup_cancelled: AtomicBool::new(false),
            startup_finished: AtomicBool::new(false),
            drain_started: AtomicBool::new(false),
            confirming_exit: AtomicBool::new(false),
            smoke_close_started: AtomicBool::new(false),
            shell_failed: AtomicBool::new(false),
            smoke_events: Mutex::new(Vec::new()),
        }
    }
}

fn lifecycle_lock(state: &HostState) -> MutexGuard<'_, Lifecycle> {
    state
        .lifecycle
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn origin_read(state: &HostState) -> RwLockReadGuard<'_, Option<Url>> {
    state
        .expected_origin
        .read()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn smoke_lock(state: &HostState) -> MutexGuard<'_, Vec<SmokeEvent>> {
    state
        .smoke_events
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

/// Build the native menu, tray, static diagnostics window and start the owned
/// backend asynchronously. This function never blocks on the backend.
pub fn setup_native_shell(app: &AppHandle) {
    let state = app.state::<HostState>();
    if build_native_menu(app).is_err()
        || build_tray(app).is_err()
        || build_diagnostics_window(app).is_err()
    {
        // No backend has been started at this point. Mark the shell failure so
        // ExitRequested is allowed, then end without a panic or a hidden child.
        state.shell_failed.store(true, Ordering::SeqCst);
        show_shell_failure_dialog();
        app.exit(0);
        return;
    }

    app.on_menu_event(|app, event| handle_menu_event(app, event.id().0.as_str()));
    spawn_startup(app.clone());
}

fn build_native_menu(app: &AppHandle) -> tauri::Result<()> {
    let menu = MenuBuilder::new(app)
        .text("show", "Show Operon")
        .text("open-logs", "Open Logs")
        .text("documentation", "Documentation")
        .separator()
        .text("quit", "Quit Operon")
        .build()?;
    app.set_menu(menu)?;
    Ok(())
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let menu = MenuBuilder::new(app)
        .text("tray-show", "Show Operon")
        .separator()
        .text("tray-quit", "Quit Operon")
        .build()?;

    let mut builder = TrayIconBuilder::<tauri::Wry>::new()
        .menu(&menu)
        .tooltip("Operon Studio Experimental")
        .show_menu_on_left_click(true);
    if let Some(icon) = app.default_window_icon().cloned() {
        builder = builder.icon(icon);
    }
    // The tray icon is registered in the manager resource table, so the icon
    // (and its menu) remains alive after this local handle is dropped.
    let _tray = builder.build(app)?;
    Ok(())
}

fn build_diagnostics_window(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    WebviewWindowBuilder::new(app, DIAGNOSTICS_LABEL, WebviewUrl::App("index.html".into()))
        .title("Operon Studio Experimental - Starting")
        .inner_size(760.0, 560.0)
        .resizable(true)
        .visible(true)
        .build()
}

fn show_shell_failure_dialog() {
    let message =
        "The experimental native shell could not be created. No owned backend was started.";
    eprintln!("Operon Studio Experimental: {message}");
    let _ = rfd::MessageDialog::new()
        .set_level(rfd::MessageLevel::Error)
        .set_title("Operon Studio Experimental")
        .set_description(message)
        .set_buttons(rfd::MessageButtons::Ok)
        .show();
}

fn spawn_startup(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let state = app.state::<HostState>();
        let config = state.config.clone();
        let result = Backend::start(&config).await;
        state.startup_finished.store(true, Ordering::SeqCst);

        match result {
            Ok(backend) => on_backend_ready(app, backend).await,
            Err(error) => {
                if state.startup_cancelled.load(Ordering::SeqCst) {
                    // Backend::start cleaned its own child before returning this
                    // error; there is genuinely no owned child to drain.
                    app.exit(0);
                    return;
                }
                {
                    let mut lifecycle = lifecycle_lock(state.inner());
                    let _ = lifecycle.backend_failed();
                }
                let message = format!(
                    "The owned backend did not become ready: {}. No automatic restart will be attempted.",
                    error.message()
                );
                show_diagnostics_message(&app, &message, &state.config.logs_dir());
            }
        }
    });
}

async fn on_backend_ready(app: AppHandle, backend: Backend) {
    let state = app.state::<HostState>();
    let origin = backend.origin().clone();
    {
        let mut guard = state.backend.lock().await;
        *guard = Some(backend);
    }
    *state
        .expected_origin
        .write()
        .unwrap_or_else(|poisoned| poisoned.into_inner()) = Some(origin.clone());

    if state.startup_cancelled.load(Ordering::SeqCst) {
        start_drain(app);
        return;
    }

    if let Err(_) = app.add_capability(runtime_capability(&origin)) {
        startup_failure(
            &app,
            state.inner(),
            "The owned UI capability could not be installed.",
        );
        return;
    }
    if state.startup_cancelled.load(Ordering::SeqCst) {
        start_drain(app);
        return;
    }

    let window = match build_main_window(&app, state.inner(), &origin) {
        Ok(window) => window,
        Err(_) => {
            startup_failure(
                &app,
                state.inner(),
                "The main window could not be created. The owned backend is retained for an explicit quit.",
            );
            return;
        }
    };

    if state.startup_cancelled.load(Ordering::SeqCst) {
        let _ = window.destroy();
        start_drain(app);
        return;
    }

    spawn_monitor(app);
}

fn runtime_capability(origin: &Url) -> impl tauri::ipc::RuntimeCapability {
    CapabilityBuilder::new("owned-ui")
        .local(false)
        .window(MAIN_LABEL)
        .webview(MAIN_LABEL)
        .remote(origin.to_string())
        .permission("host")
        .permission("core:event:allow-listen")
        .permission("core:event:allow-unlisten")
}

fn build_main_window(
    app: &AppHandle,
    state: &HostState,
    origin: &Url,
) -> tauri::Result<WebviewWindow> {
    let data_directory = state.config.profile.join("webview");
    let _ = std::fs::create_dir_all(&data_directory);
    let navigation_origin = origin.clone();
    let figure_origin = origin.clone();

    WebviewWindowBuilder::new(app, MAIN_LABEL, WebviewUrl::External(origin.clone()))
        .title("Operon Studio Experimental")
        .inner_size(1280.0, 860.0)
        .data_directory(data_directory)
        .visible(true)
        .on_navigation(move |url| navigation::allow_owned_navigation(url, &navigation_origin))
        .on_new_window(move |url, _| {
            if navigation::allow_owned_figure(&url, &figure_origin) {
                let origin = figure_origin.clone();
                tauri::async_runtime::spawn_blocking(move || {
                    let _ = navigation::open_owned_figure(&url, &origin);
                });
            }
            NewWindowResponse::Deny
        })
        .build()
}

fn startup_failure(app: &AppHandle, state: &HostState, message: &str) {
    {
        let mut lifecycle = lifecycle_lock(state);
        let _ = lifecycle.backend_failed();
    }
    show_diagnostics_message(app, message, &state.config.logs_dir());
}

fn spawn_monitor(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        loop {
            tokio::time::sleep(Duration::from_secs(1)).await;
            let state = app.state::<HostState>();
            {
                let lifecycle = lifecycle_lock(state.inner());
                if matches!(
                    lifecycle.state(),
                    LifecycleState::Draining
                        | LifecycleState::Recovery
                        | LifecycleState::Closed
                        | LifecycleState::BackendFailed
                ) {
                    if matches!(lifecycle.state(), LifecycleState::Closed) {
                        break;
                    }
                    continue;
                }
            }

            let exited = {
                let mut guard = state.backend.lock().await;
                match guard.as_mut() {
                    Some(backend) => backend.try_exited().unwrap_or(false),
                    None => false,
                }
            };
            if !exited {
                continue;
            }

            let transitioned = {
                let mut lifecycle = lifecycle_lock(state.inner());
                lifecycle.backend_failed().is_ok()
            };
            if transitioned {
                show_diagnostics_or_create(
                    &app,
                    "The owned backend stopped unexpectedly. It will not be restarted and jobs will not be replayed. Use Quit Operon to finish closing.",
                    &state.config.logs_dir(),
                );
            }
        }
    });
}

/// Native menu and tray menu handler. The same exit flow is used for the window
/// menu, tray menu and IPC command.
pub fn handle_menu_event(app: &AppHandle, id: &str) {
    match id {
        "show" | "tray-show" => show_main_or_diagnostics(app),
        "open-logs" => open_logs_dir(app),
        "documentation" => {
            if navigation::open_default_documentation().is_err() {
                eprintln!(
                    "Operon Studio Experimental: the documentation URL is not approved or could not be opened."
                );
            }
        }
        "quit" | "tray-quit" => request_exit(app.clone()),
        _ => {}
    }
}

fn open_logs_dir(app: &AppHandle) {
    let state = app.state::<HostState>();
    let logs = state.config.logs_dir();
    tauri::async_runtime::spawn_blocking(move || {
        if std::fs::create_dir_all(&logs).is_ok() {
            let _ = open::that(&logs);
        }
    });
}

/// Request a full exit. Pending local/remote jobs are checked before the renderer
/// close handshake; the jobs are never cancelled by this host.
pub fn request_exit(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let state = app.state::<HostState>();
        if state.confirming_exit.swap(true, Ordering::SeqCst) {
            return;
        }

        let needs_confirmation = {
            let lifecycle = lifecycle_lock(state.inner());
            matches!(
                lifecycle.state(),
                LifecycleState::ReadyVisible | LifecycleState::ReadyHidden
            )
        };

        let proceed = if needs_confirmation {
            confirm_pending_jobs(&app, state.inner()).await
        } else {
            true
        };
        state.confirming_exit.store(false, Ordering::SeqCst);
        if proceed {
            begin_exit_after_confirmation(&app).await;
        }
    });
}

enum ExitDecision {
    None,
    CancelStartup,
    Emit(String),
    Drain,
    DrainOrExit,
    Exit,
}

async fn begin_exit_after_confirmation(app: &AppHandle) {
    let state = app.state::<HostState>();

    let decision = {
        let mut lifecycle = lifecycle_lock(state.inner());
        match lifecycle.state().clone() {
            LifecycleState::Starting => {
                state.startup_cancelled.store(true, Ordering::SeqCst);
                ExitDecision::CancelStartup
            }
            LifecycleState::ReadyVisible | LifecycleState::ReadyHidden => {
                match lifecycle.begin_close() {
                    Ok(request) if !request.coalesced => ExitDecision::Emit(request.request_id),
                    Ok(_) => ExitDecision::None,
                    Err(_) => ExitDecision::None,
                }
            }
            LifecycleState::Flushing { .. } | LifecycleState::Draining => ExitDecision::None,
            LifecycleState::Recovery => ExitDecision::Drain,
            LifecycleState::BackendFailed => ExitDecision::DrainOrExit,
            LifecycleState::Closed => ExitDecision::Exit,
        }
    };

    match decision {
        ExitDecision::None => {}
        ExitDecision::CancelStartup => {
            show_diagnostics_message(
                app,
                "Startup cancellation requested. The owned process will be stopped if it becomes ready.",
                &state.config.logs_dir(),
            );
            let backend_exists = match state.backend.try_lock() {
                Ok(guard) => guard.is_some(),
                Err(_) => true,
            };
            if backend_exists {
                start_drain(app.clone());
            }
        }
        ExitDecision::Emit(request_id) => {
            let payload = serde_json::json!({ "request_id": request_id.clone() });
            if app
                .emit_to(MAIN_LABEL, PREPARE_CLOSE_EVENT, payload)
                .is_err()
            {
                {
                    let mut lifecycle = lifecycle_lock(state.inner());
                    let _ = lifecycle.draft_flush_timed_out(&request_id);
                }
                show_main(app);
                show_diagnostics_or_create(
                    app,
                    "The close request could not be delivered to the main UI. Full exit was cancelled and the window was restored.",
                    &state.config.logs_dir(),
                );
            } else {
                spawn_draft_timeout(app.clone(), request_id);
            }
        }
        ExitDecision::Drain => start_drain(app.clone()),
        ExitDecision::DrainOrExit => {
            let backend_exists = match state.backend.try_lock() {
                Ok(guard) => guard.is_some(),
                Err(_) => true,
            };
            if backend_exists {
                start_drain(app.clone());
            } else {
                app.exit(0);
            }
        }
        ExitDecision::Exit => app.exit(0),
    }
}

fn spawn_draft_timeout(app: AppHandle, request_id: String) {
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(DRAFT_FLUSH_TIMEOUT).await;
        let state = app.state::<HostState>();
        let timed_out = {
            let mut lifecycle = lifecycle_lock(state.inner());
            lifecycle.draft_flush_timed_out(&request_id).is_ok()
        };
        if timed_out {
            show_main(&app);
            show_diagnostics_or_create(
                &app,
                "The renderer did not finish saving drafts within 5 seconds. Full exit was cancelled and the main window was restored.",
                &state.config.logs_dir(),
            );
        }
    });
}

fn start_drain(app: AppHandle) {
    if app
        .state::<HostState>()
        .drain_started
        .swap(true, Ordering::SeqCst)
    {
        return;
    }
    tauri::async_runtime::spawn(async move {
        drain_owned_backend(app).await;
    });
}

async fn drain_owned_backend(app: AppHandle) {
    let state = app.state::<HostState>();

    // Starting cannot enter Draining directly. Record the backend failure, then
    // confirm the actual child stop before adopting Closed.
    {
        let mut lifecycle = lifecycle_lock(state.inner());
        if matches!(lifecycle.state(), LifecycleState::Starting) {
            let _ = lifecycle.backend_failed();
        }
    }

    let result = {
        let mut guard = state.backend.lock().await;
        match guard.as_mut() {
            Some(backend) => backend.shutdown(BACKEND_DRAIN_TIMEOUT).await,
            None => Ok(()),
        }
    };

    match result {
        Ok(()) => {
            let closed = {
                let mut lifecycle = lifecycle_lock(state.inner());
                lifecycle.backend_stopped().is_ok()
            };
            if closed {
                record_smoke_event(state.inner(), "exit", None);
                app.exit(0);
            } else {
                state.drain_started.store(false, Ordering::SeqCst);
                show_diagnostics_or_create(
                    &app,
                    "The owned process stopped, but the close state was no longer valid. The application remains open.",
                    &state.config.logs_dir(),
                );
            }
        }
        Err(_) => {
            let failed_and_stopped = {
                let mut guard = state.backend.lock().await;
                guard
                    .as_mut()
                    .is_some_and(|backend| backend.failed_tree_stopped().unwrap_or(false))
            };
            if failed_and_stopped {
                let _ = lifecycle_lock(state.inner()).backend_stopped();
                record_smoke_event(state.inner(), "failed_exit", None);
                app.exit(1);
                return;
            }
            state.drain_started.store(false, Ordering::SeqCst);
            {
                let mut lifecycle = lifecycle_lock(state.inner());
                let _ = lifecycle.drain_timed_out();
            }
            show_main(&app);
            show_diagnostics_or_create(
                &app,
                "The owned backend did not stop within 8 seconds. The application remains open. Retry Quit Operon to stop the same owned process; no new backend will be started.",
                &state.config.logs_dir(),
            );
        }
    }
}

fn show_main(app: &AppHandle) {
    {
        let state = app.state::<HostState>();
        let mut lifecycle = lifecycle_lock(state.inner());
        if matches!(lifecycle.state(), LifecycleState::ReadyHidden) {
            let _ = lifecycle.show();
        }
    }
    if let Some(window) = app.get_webview_window(MAIN_LABEL) {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn show_main_or_diagnostics(app: &AppHandle) {
    if app.get_webview_window(MAIN_LABEL).is_some() {
        show_main(app);
        return;
    }
    if let Some(window) = app.get_webview_window(DIAGNOSTICS_LABEL) {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn show_diagnostics_message(app: &AppHandle, message: &str, logs_dir: &Path) {
    let Some(window) = app.get_webview_window(DIAGNOSTICS_LABEL) else {
        eprintln!(
            "Operon Studio Experimental: {message} (logs: {})",
            logs_dir.display()
        );
        return;
    };

    let title = format!(
        "Operon Studio Experimental - {message} - Logs: {}",
        logs_dir.display()
    );
    let _ = window.set_title(&title);
    let status = json_string(message);
    let logs = json_string(&logs_dir.display().to_string());
    let script = format!(
        "(() => {{ \
         const apply = () => {{ \
           const status = document.getElementById('status'); \
           if (status) status.textContent = {status}; \
           const detail = document.getElementById('detail'); \
           if (detail) detail.textContent = 'The application remains open. Use the native menu or tray to quit or open logs.'; \
           const logs = document.getElementById('logs'); \
           if (logs) logs.textContent = 'Logs: ' + {logs}; \
         }}; \
         if (document.readyState === 'loading') {{ \
           document.addEventListener('DOMContentLoaded', apply, {{ once: true }}); \
         }} else {{ \
           apply(); \
         }} \
         }})();"
    );
    let _ = window.eval(script);
    let _ = window.show();
    let _ = window.set_focus();
}

fn show_diagnostics_or_create(app: &AppHandle, message: &str, logs_dir: &Path) {
    if app.get_webview_window(DIAGNOSTICS_LABEL).is_none() {
        let _ =
            WebviewWindowBuilder::new(app, DIAGNOSTICS_LABEL, WebviewUrl::App("index.html".into()))
                .title("Operon Studio Experimental - Diagnostics")
                .inner_size(760.0, 560.0)
                .visible(true)
                .build();
    }
    show_diagnostics_message(app, message, logs_dir);
}

fn json_string(value: &str) -> String {
    serde_json::to_string(value).unwrap_or_else(|_| "\"\"".to_owned())
}

/// Handle the top-level window close button. Only the ready main window hides;
/// every close during startup, flushing, draining or failure enters the same
/// explicit exit/retry flow instead of pretending the app closed.
pub fn handle_window_event(window: &Window, event: &WindowEvent) {
    let WindowEvent::CloseRequested { api, .. } = event else {
        return;
    };
    let app = window.app_handle();

    match window.label() {
        MAIN_LABEL => {
            let state = app.state::<HostState>();
            let action = {
                let mut lifecycle = lifecycle_lock(state.inner());
                match lifecycle.state() {
                    LifecycleState::ReadyVisible | LifecycleState::ReadyHidden => {
                        let hidden = lifecycle.hide().is_ok();
                        Some((true, hidden))
                    }
                    LifecycleState::Starting
                    | LifecycleState::Flushing { .. }
                    | LifecycleState::Draining
                    | LifecycleState::Recovery
                    | LifecycleState::BackendFailed => Some((true, false)),
                    LifecycleState::Closed => None,
                }
            };
            if let Some((prevent, hide)) = action {
                if prevent {
                    api.prevent_close();
                }
                if hide {
                    let _ = window.hide();
                } else {
                    request_exit(app.clone());
                }
            }
        }
        DIAGNOSTICS_LABEL => {
            api.prevent_close();
            request_exit(app.clone());
        }
        _ => api.prevent_close(),
    }
}

/// RunEvent::ExitRequested gate. Exit is allowed only after a confirmed owned
/// child stop, or when there is genuinely no child. An unknown OS session end is
/// prevented rather than claimed as graceful.
pub fn exit_is_verified(app: &AppHandle) -> bool {
    let state = app.state::<HostState>();
    if state.shell_failed.load(Ordering::SeqCst) {
        return true;
    }
    {
        let lifecycle = lifecycle_lock(state.inner());
        if matches!(lifecycle.state(), LifecycleState::Closed) {
            return true;
        }
    }
    if !state.startup_finished.load(Ordering::SeqCst) {
        return false;
    }
    let verified = match state.backend.try_lock() {
        Ok(guard) => guard.is_none(),
        Err(_) => false,
    };
    verified
}

// ---------------------------------------------------------------------------
// IPC commands
// ---------------------------------------------------------------------------

/// The renderer has registered its close listener and loaded the owned UI.
#[tauri::command]
pub async fn ready(
    app: AppHandle,
    webview: WebviewWindow,
    state: State<'_, HostState>,
) -> Result<(), HostError> {
    verify_main_caller(&webview, state.inner())?;
    {
        let guard = state.backend.lock().await;
        if guard.is_none() {
            return Err(HostError::bridge_unavailable());
        }
    }

    let transitioned = {
        let mut lifecycle = lifecycle_lock(state.inner());
        let was_starting = matches!(lifecycle.state(), LifecycleState::Starting);
        lifecycle.mark_ready()?;
        was_starting
    };

    if transitioned && state.smoke {
        record_smoke_event(state.inner(), "ready", None);
    }
    if let Some(window) = app.get_webview_window(DIAGNOSTICS_LABEL) {
        let _ = window.destroy();
    }

    if state.smoke && transitioned && !state.smoke_close_started.swap(true, Ordering::SeqCst) {
        let app = app.clone();
        tauri::async_runtime::spawn(async move {
            // The React listener is registered before it calls `ready`; this
            // delay only lets the ready command settle. The close then uses the
            // real prepare-close event and the real renderer ACK.
            tokio::time::sleep(Duration::from_millis(750)).await;
            request_exit(app);
        });
    }
    Ok(())
}

/// Apply the renderer draft-flush acknowledgement.
#[tauri::command]
pub async fn acknowledge_draft_flush(
    app: AppHandle,
    webview: WebviewWindow,
    state: State<'_, HostState>,
    request_id: String,
    saved: bool,
) -> Result<(), HostError> {
    verify_main_caller(&webview, state.inner())?;
    let outcome = {
        let mut lifecycle = lifecycle_lock(state.inner());
        lifecycle.acknowledge_draft_flush(&request_id, saved)
    }?;

    match outcome {
        FlushOutcome::Draining => {
            record_smoke_event(state.inner(), "draft_saved", Some(&request_id));
            start_drain(app);
        }
        FlushOutcome::Visible => {
            record_smoke_event(state.inner(), "draft_cancelled", Some(&request_id));
            show_main(&app);
        }
    }
    Ok(())
}

/// Open only the configured profile's fixed `logs` directory with the OS shell.
#[tauri::command]
pub async fn show_diagnostics(
    webview: WebviewWindow,
    state: State<'_, HostState>,
) -> Result<(), HostError> {
    verify_main_caller(&webview, state.inner())?;
    let logs = state.config.logs_dir();
    let opened = tokio::task::spawn_blocking(move || {
        std::fs::create_dir_all(&logs).map_err(|_| ())?;
        open::that(&logs).map_err(|_| ())
    })
    .await;
    match opened {
        Ok(Ok(())) => Ok(()),
        _ => Err(HostError::capability_unavailable(
            HostNextAction::OpenHostLogs,
            None,
        )),
    }
}

/// Request the shared native full-exit flow.
#[tauri::command]
pub async fn request_full_exit(
    app: AppHandle,
    webview: WebviewWindow,
    state: State<'_, HostState>,
) -> Result<(), HostError> {
    verify_main_caller(&webview, state.inner())?;
    request_exit(app);
    Ok(())
}

/// Open a committed artifact through the authenticated owned backend. The token
/// is copied transiently and the backend mutex is released before the download.
#[tauri::command]
pub async fn open_committed_artifact(
    webview: WebviewWindow,
    state: State<'_, HostState>,
    run_id: String,
    artifact_id: String,
    file_id: String,
) -> Result<(), HostError> {
    verify_main_caller(&webview, state.inner())?;

    let (origin, token) = {
        let guard = state.backend.lock().await;
        match guard.as_ref() {
            Some(backend) => (backend.origin().clone(), backend.studio_token().to_owned()),
            None => return Err(HostError::bridge_unavailable()),
        }
    };
    let profile = state.config.profile.clone();

    crate::artifacts::open_committed_artifact(
        &origin,
        &token,
        &profile,
        &run_id,
        &artifact_id,
        &file_id,
    )
    .await
}

/// Show only the fixed native picker for the requested enum kind.
#[tauri::command]
pub async fn select_path(
    webview: WebviewWindow,
    state: State<'_, HostState>,
    kind: SelectPathKind,
) -> Result<Option<PathBuf>, HostError> {
    verify_main_caller(&webview, state.inner())?;
    crate::dialogs::select_path(kind).await
}

// ---------------------------------------------------------------------------
// Caller origin policy (pure, unit-testable)
// ---------------------------------------------------------------------------

fn verify_main_caller(webview: &WebviewWindow, state: &HostState) -> Result<(), HostError> {
    let origin = {
        let guard = origin_read(state);
        match guard.as_ref() {
            Some(origin) => origin.clone(),
            None => return Err(HostError::bridge_unavailable()),
        }
    };
    let url = webview.url().map_err(|_| HostError::bridge_unavailable())?;
    if caller_url_is_authorized(webview.label(), &url, &origin) {
        Ok(())
    } else {
        Err(HostError::unsupported(None))
    }
}

/// True only for the exact main label and exact owned root URL.
pub fn caller_url_is_authorized(label: &str, url: &Url, origin: &Url) -> bool {
    label == MAIN_LABEL && valid_owned_origin(origin) && exact_owned_root(url, origin)
}

fn exact_owned_root(url: &Url, origin: &Url) -> bool {
    valid_owned_origin(url)
        && url.scheme() == origin.scheme()
        && url.host() == origin.host()
        && url.port() == origin.port()
        && url.username().is_empty()
        && url.password().is_none()
        && url.path() == "/"
        && url.query().is_none()
        && url.fragment().is_none()
}

fn valid_owned_origin(url: &Url) -> bool {
    if url.scheme() != "http"
        || !url.username().is_empty()
        || url.password().is_some()
        || url.path() != "/"
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return false;
    }
    match url.host() {
        Some(url::Host::Ipv4(address)) if address == Ipv4Addr::LOCALHOST => {}
        _ => return false,
    }
    url.port().is_some_and(|port| port != 0)
}

// ---------------------------------------------------------------------------
// Pending job confirmation
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct JobEntry {
    #[serde(default)]
    status: Option<String>,
    #[serde(default)]
    remote: Option<serde_json::Value>,
}

struct PendingJobs {
    local: usize,
    remote: usize,
}

impl PendingJobs {
    fn total(&self) -> usize {
        self.local + self.remote
    }
}

enum JobQuery {
    Known(PendingJobs),
    Unknown,
}

async fn confirm_pending_jobs(_app: &AppHandle, state: &HostState) -> bool {
    let credentials = {
        let guard = state.backend.lock().await;
        match guard.as_ref() {
            Some(backend) => Some((backend.origin().clone(), backend.studio_token().to_owned())),
            None => None,
        }
    };

    let Some((origin, token)) = credentials else {
        return true;
    };

    let query = query_pending_jobs(&origin, &token).await;
    match query {
        JobQuery::Known(pending) if pending.total() == 0 => true,
        JobQuery::Known(pending) => {
            let description = format!(
                "{} local and {} remote experiment job(s) are still queued or running. Operon will not cancel them. Quit Operon and stop the owned backend?",
                pending.local, pending.remote
            );
            confirm_dialog(&description).await
        }
        JobQuery::Unknown => {
            confirm_dialog(
                "Operon could not verify whether experiment jobs are still running. Quit Operon and stop the owned backend?",
            )
            .await
        }
    }
}

async fn confirm_dialog(description: &str) -> bool {
    matches!(
        rfd::AsyncMessageDialog::new()
            .set_level(rfd::MessageLevel::Warning)
            .set_title("Quit Operon Studio Experimental?")
            .set_description(description)
            .set_buttons(rfd::MessageButtons::OkCancel)
            .show()
            .await,
        rfd::MessageDialogResult::Ok
    )
}

async fn query_pending_jobs(origin: &Url, token: &str) -> JobQuery {
    let client = match reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .no_proxy()
        .connect_timeout(Duration::from_secs(2))
        .timeout(Duration::from_secs(5))
        .build()
    {
        Ok(client) => client,
        Err(_) => return JobQuery::Unknown,
    };

    let mut url = origin.clone();
    url.set_path("/api/jobs");
    url.set_query(None);
    url.set_fragment(None);

    let mut response = match client.get(url).header("x-studio-token", token).send().await {
        Ok(response) if response.status().is_success() => response,
        _ => return JobQuery::Unknown,
    };
    if response
        .content_length()
        .is_some_and(|length| length > MAX_JOBS_BYTES as u64)
    {
        return JobQuery::Unknown;
    }

    let mut body = Vec::new();
    loop {
        match response.chunk().await {
            Ok(Some(chunk)) => {
                if body.len().saturating_add(chunk.len()) > MAX_JOBS_BYTES {
                    return JobQuery::Unknown;
                }
                body.extend_from_slice(&chunk);
            }
            Ok(None) => break,
            Err(_) => return JobQuery::Unknown,
        }
    }

    let jobs: Vec<JobEntry> = match serde_json::from_slice(&body) {
        Ok(jobs) => jobs,
        Err(_) => return JobQuery::Unknown,
    };

    let mut pending = PendingJobs {
        local: 0,
        remote: 0,
    };
    for job in jobs {
        if is_pending(job.status.as_deref()) {
            if job.remote.is_some() {
                pending.remote += 1;
            } else {
                pending.local += 1;
            }
        }
    }
    JobQuery::Known(pending)
}

fn is_pending(status: Option<&str>) -> bool {
    let Some(status) = status else {
        return true;
    };
    !matches!(
        status.to_ascii_lowercase().as_str(),
        "complete"
            | "completed"
            | "succeeded"
            | "success"
            | "failed"
            | "error"
            | "cancelled"
            | "canceled"
            | "interrupted"
            | "stopped"
            | "skipped"
    )
}

// ---------------------------------------------------------------------------
// Optional smoke receipt
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone)]
struct SmokeEvent {
    event: &'static str,
    unix_ms: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    request_id: Option<String>,
}

fn record_smoke_event(state: &HostState, event: &'static str, request_id: Option<&str>) {
    if !state.smoke {
        return;
    }

    let mut events = smoke_lock(state);
    events.push(SmokeEvent {
        event,
        unix_ms: SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|value| value.as_millis() as u64)
            .unwrap_or(0),
        request_id: request_id.map(str::to_owned),
    });

    let body = serde_json::json!({
        "schema_version": 1,
        "smoke_test": true,
        "events": events.as_slice(),
    });
    let Ok(mut bytes) = serde_json::to_vec_pretty(&body) else {
        return;
    };
    bytes.push(b'\n');

    let logs = state.config.logs_dir();
    if std::fs::create_dir_all(&logs).is_err() {
        return;
    }
    let path = logs.join("native-smoke.json");
    let temporary = logs.join("native-smoke.json.tmp");
    if std::fs::write(&temporary, bytes).is_ok() {
        let _ = std::fs::remove_file(&path);
        let _ = std::fs::rename(&temporary, &path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn origin() -> Url {
        Url::parse("http://127.0.0.1:43123/").unwrap()
    }

    #[test]
    fn accepts_only_the_exact_main_root() {
        assert!(caller_url_is_authorized("main", &origin(), &origin()));
        assert!(!caller_url_is_authorized(
            "diagnostics",
            &origin(),
            &origin()
        ));
    }

    #[test]
    fn rejects_a_wrong_port() {
        let other = Url::parse("http://127.0.0.1:43124/").unwrap();
        assert!(!caller_url_is_authorized("main", &other, &origin()));
        assert!(!caller_url_is_authorized("main", &origin(), &other));
    }

    #[test]
    fn rejects_api_result_urls() {
        let results =
            Url::parse("http://127.0.0.1:43123/api/jobs/run/artifacts/artifact/file").unwrap();
        assert!(!caller_url_is_authorized("main", &results, &origin()));
    }

    #[test]
    fn rejects_query_fragment_and_userinfo() {
        let query = Url::parse("http://127.0.0.1:43123/?token=secret").unwrap();
        let fragment = Url::parse("http://127.0.0.1:43123/#main").unwrap();
        let userinfo = Url::parse("http://user@127.0.0.1:43123/").unwrap();
        assert!(!caller_url_is_authorized("main", &query, &origin()));
        assert!(!caller_url_is_authorized("main", &fragment, &origin()));
        assert!(!caller_url_is_authorized("main", &userinfo, &origin()));
    }

    #[test]
    fn rejects_non_loopback_https_and_bare_origins() {
        let localhost = Url::parse("http://localhost:43123/").unwrap();
        let ipv6 = Url::parse("http://[::1]:43123/").unwrap();
        let https = Url::parse("https://127.0.0.1:43123/").unwrap();
        let path = Url::parse("http://127.0.0.1:43123/ui").unwrap();
        assert!(!caller_url_is_authorized("main", &localhost, &origin()));
        assert!(!caller_url_is_authorized("main", &ipv6, &origin()));
        assert!(!caller_url_is_authorized("main", &https, &origin()));
        assert!(!caller_url_is_authorized("main", &path, &origin()));
    }

    #[test]
    fn pending_status_is_conservative() {
        assert!(is_pending(Some("running")));
        assert!(is_pending(Some("queued")));
        assert!(is_pending(None));
        assert!(!is_pending(Some("complete")));
        assert!(!is_pending(Some("cancelled")));
    }
}
