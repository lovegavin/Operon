//! Build-time Tauri manifest and app-command permission generation.
//!
//! The command allowlist is intentionally fixed here. Renderer IPC is still
//! disabled because `tauri.conf.json` declares no static capabilities; the root
//! integration adds one runtime capability for the exact owned backend origin
//! and the main window only.

const COMMANDS: &[&str] = &[
    "ready",
    "acknowledge_draft_flush",
    "show_diagnostics",
    "request_full_exit",
    "open_committed_artifact",
    "select_path",
];

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=permissions");
    println!("cargo:rerun-if-changed=tauri.conf.json");

    if std::env::var_os("CARGO_FEATURE_DESKTOP").is_none() {
        return;
    }

    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(COMMANDS)),
    )
    .expect("failed to run tauri-build");
}
