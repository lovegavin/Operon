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
use operon_desktop_experimental::instance::InstanceGuard;
use operon_desktop_experimental::maintenance::StartupGuard;
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
    let startup_guard = match StartupGuard::acquire(&config.installation_id) {
        Ok(guard) => guard,
        Err(error) => fatal(&format!(
            "{} An experimental setup, update or uninstall may be active. Wait for maintenance to finish and try again.",
            error.message()
        )),
    };

    let instance = match InstanceGuard::acquire(&config.profile, &config.installation_id) {
        Ok(instance) => instance,
        Err(error) => fatal(&format!(
            "{} Another experimental instance may own this profile. Use its tray menu to exit it; activation IPC is not implemented.",
            error.message()
        )),
    };

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
