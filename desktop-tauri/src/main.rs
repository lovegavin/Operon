#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! Experimental native host entry point.
//!
//! The only accepted invocation is:
//!
//! `operon-desktop-experimental --config <path> [--smoke-test]`
//!
//! Configuration is explicit and canonical. The experimental profile is claimed
//! before any log or instance lock is created. No managed runtime, implicit
//! profile or production installation is used as a fallback.

use operon_desktop_experimental::bridge::{self, HostState};
use operon_desktop_experimental::config::HostConfig;
use operon_desktop_experimental::error::{HostErrorCode, HostNextAction};
use operon_desktop_experimental::instance::{self, InstanceGuard};
use operon_desktop_experimental::maintenance::{self, StartupGuard};
use std::path::PathBuf;

struct ParsedArgs {
    config: PathBuf,
    smoke_test: bool,
}

fn main() {
    let args = match parse_args() {
        Ok(args) => args,
        Err(message) => fatal(&message),
    };

    let config = match HostConfig::load(&args.config) {
        Ok(config) => config,
        Err(error) => fatal(&format!(
            "The experimental host configuration is invalid: {error}"
        )),
    };
    if let Err(error) = config.ensure_experimental_profile() {
        fatal(&format!(
            "The experimental profile cannot be claimed: {error}"
        ));
    }
    // The installation-scoped gate must be held before the profile instance lock
    // or backend spawn. A setup/update holding the active event fails closed.
    // A busy gate with a live instance lock is the first-launch race: a second
    // shortcut may still activate that host, but this process never spawns.
    let startup_guard = match StartupGuard::acquire(&config.installation_id) {
        Ok(guard) => Some(guard),
        Err(error) if error.code() == HostErrorCode::HostCapabilityUnavailable => {
            match maintenance::is_active(&config.installation_id) {
                Ok(false) => {}
                Ok(true) => fatal(&format!(
                    "{} An experimental setup, update or uninstall is active. Wait for maintenance to finish and try again.",
                    error.message()
                )),
                Err(_) => fatal(
                    "The installation maintenance state could not be verified. No experimental backend was started.",
                ),
            }
            match instance::lock_is_held(&config.profile) {
                Ok(true) => {}
                Ok(false) => fatal(&format!(
                    "{} Another experimental instance may own this profile. Use its tray menu to exit it.",
                    error.message()
                )),
                Err(_) => fatal(
                    "The experimental profile instance state could not be verified. No backend was started.",
                ),
            }
            None
        }
        Err(error) => fatal(&format!(
            "{} The experimental installation gate is unavailable. No backend was started.",
            error.message()
        )),
    };

    if startup_guard.is_none() {
        activate_or_exit(&config, args.smoke_test);
    }

    let instance = match InstanceGuard::acquire(&config.profile, &config.installation_id) {
        Ok(instance) => instance,
        Err(error)
            if error.code() == HostErrorCode::HostCapabilityUnavailable
                && error.next_actions() == [HostNextAction::UseTrayMenuExit].as_slice() =>
        {
            activate_or_exit(&config, args.smoke_test);
        }
        Err(error) => fatal(&format!(
            "{} Another experimental instance may own this profile. Use its tray menu to exit it.",
            error.message()
        )),
    };

    let startup_guard = startup_guard.expect("the startup guard is retained on the spawning path");
    let state = HostState::new(config, instance, args.smoke_test, startup_guard);

    let app = match tauri::Builder::default()
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            bridge::ready,
            bridge::acknowledge_draft_flush,
            bridge::show_diagnostics,
            bridge::request_full_exit,
            bridge::open_committed_artifact,
            bridge::select_path,
        ])
        .setup(|app| {
            bridge::setup_native_shell(app.handle());
            Ok(())
        })
        .on_window_event(|window, event| bridge::handle_window_event(window, event))
        .build(tauri::generate_context!())
    {
        Ok(app) => app,
        Err(error) => fatal(&format!(
            "The experimental desktop host could not be built: {error}"
        )),
    };

    app.run(|app, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            // Never claim a graceful close for an unknown OS session end, a
            // failed drain or a still-running owned child.
            if !bridge::exit_is_verified(app) {
                api.prevent_exit();
            }
        }
    });
}

#[cfg(windows)]
fn activate_or_exit(config: &HostConfig, smoke_test: bool) -> ! {
    if smoke_test {
        fatal(
            "A smoke test cannot reuse another experimental instance. Exit it from the tray first.",
        );
    }
    match operon_desktop_experimental::activation::request_show(config) {
        Ok(()) => std::process::exit(0),
        Err(error) => fatal(error.message()),
    }
}

#[cfg(not(windows))]
fn activate_or_exit(_config: &HostConfig, _smoke_test: bool) -> ! {
    fatal("Shortcut activation is supported only on Windows x64.");
}

fn parse_args() -> Result<ParsedArgs, String> {
    let mut config: Option<PathBuf> = None;
    let mut smoke_test = false;
    let mut args = std::env::args_os().skip(1);

    while let Some(argument) = args.next() {
        match argument.to_str() {
            Some("--config") => {
                if config.is_some() {
                    return Err("--config may be supplied only once.".to_owned());
                }
                let value = args
                    .next()
                    .ok_or_else(|| "--config requires a configuration file path.".to_owned())?;
                config = Some(PathBuf::from(value));
            }
            Some("--smoke-test") => {
                if smoke_test {
                    return Err("--smoke-test may be supplied only once.".to_owned());
                }
                smoke_test = true;
            }
            _ => {
                return Err(format!(
                    "Unexpected argument: {}. Only --config <path> and --smoke-test are accepted.",
                    argument.to_string_lossy()
                ));
            }
        }
    }

    let config = config.ok_or_else(|| "--config <path> is required.".to_owned())?;
    Ok(ParsedArgs { config, smoke_test })
}

fn fatal(message: &str) -> ! {
    eprintln!("Operon Studio Experimental: {message}");
    let _ = rfd::MessageDialog::new()
        .set_level(rfd::MessageLevel::Error)
        .set_title("Operon Studio Experimental")
        .set_description(message)
        .set_buttons(rfd::MessageButtons::Ok)
        .show();
    std::process::exit(2);
}
