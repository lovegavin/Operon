//! Shared experimental Tauri host contracts.
//!
//! Session A exports the transport-neutral error and configuration modules. The
//! root integration adds the C lifecycle modules (backend, instance, lifecycle,
//! logging, windows), the D OS-service modules (artifacts, credentials, dialogs,
//! navigation) and the Tauri-facing bridge.

pub mod artifacts;
pub mod backend;
pub mod config;
pub mod credentials;
pub mod dialogs;
pub mod error;
pub mod instance;
pub mod lifecycle;
pub mod logging;
pub mod navigation;
pub mod windows;

#[cfg(feature = "desktop")]
pub mod bridge;
