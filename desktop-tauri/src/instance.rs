//! Exclusive, OS-backed single-instance ownership for one experimental profile.
//!
//! The persistent lock file is evidence, not liveness proof: after a crash the
//! file remains, but the OS lock is released, so the next launch can re-lock it
//! safely. The lock path is never removed on drop, which avoids splitting one
//! profile between an old and a new lock file. Two different profiles use two
//! different lock files and remain independent.

use crate::error::{HostError, HostNextAction};
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

/// Lock file retained inside the canonical configured profile.
pub const INSTANCE_LOCK_FILE: &str = ".operon-instance.lock";

const LOCK_SCHEMA_VERSION: u32 = 1;

/// Holds the exclusive file lock for its whole lifetime. Dropping it releases
/// the OS lock but intentionally leaves the lock file in place.
pub struct InstanceGuard {
    profile: PathBuf,
    _file: File,
}

#[derive(Serialize, Deserialize)]
struct LockRecord {
    schema_version: u32,
    installation_id: String,
    profile: PathBuf,
    pid: u32,
    created_unix: u64,
}

impl InstanceGuard {
    /// Acquire the exclusive lock for `profile`.
    ///
    /// Call `HostConfig::ensure_experimental_profile()` first: the profile
    /// marker must exist before this lock file is created, otherwise the next
    /// marker check sees a non-empty unmarked profile.
    ///
    /// A second acquisition for the same canonical profile returns a typed
    /// already-running action (`use_tray_menu_exit`). Activation IPC is not part
    /// of this module, so the caller must not pretend the second launch
    /// succeeded. The profile marker/foreign-install decision belongs to
    /// `HostConfig`, not to this lock.
    pub fn acquire(profile: &Path, installation_id: &str) -> Result<Self, HostError> {
        if installation_id.is_empty()
            || installation_id.trim() != installation_id
            || installation_id.chars().any(char::is_control)
        {
            return Err(HostError::bridge_unavailable());
        }

        fs::create_dir_all(profile).map_err(|_| HostError::bridge_unavailable())?;
        let profile = fs::canonicalize(profile).map_err(|_| HostError::bridge_unavailable())?;
        let lock_path = profile.join(INSTANCE_LOCK_FILE);
        let mut file = match OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .open(&lock_path)
        {
            Ok(file) => file,
            Err(error) if is_lock_contention(&error) => {
                return Err(HostError::capability_unavailable(
                    HostNextAction::UseTrayMenuExit,
                    None,
                ));
            }
            Err(_) => return Err(HostError::bridge_unavailable()),
        };

        match file.try_lock_exclusive() {
            Ok(()) => {}
            Err(error) if is_lock_contention(&error) => {
                return Err(HostError::capability_unavailable(
                    HostNextAction::UseTrayMenuExit,
                    None,
                ));
            }
            Err(_) => return Err(HostError::bridge_unavailable()),
        }

        let record = LockRecord {
            schema_version: LOCK_SCHEMA_VERSION,
            installation_id: installation_id.to_owned(),
            profile: profile.clone(),
            pid: std::process::id(),
            created_unix: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|value| value.as_secs())
                .unwrap_or(0),
        };
        let mut body = serde_json::to_vec(&record).map_err(|_| HostError::bridge_unavailable())?;
        body.push(b'\n');
        file.set_len(0)
            .and_then(|()| file.seek(SeekFrom::Start(0)).map(|_| ()))
            .and_then(|()| file.write_all(&body))
            .map_err(|_| HostError::bridge_unavailable())?;
        let _ = file.sync_all();

        Ok(Self {
            profile,
            _file: file,
        })
    }

    /// Canonical profile bound to this lock.
    pub fn profile(&self) -> &Path {
        &self.profile
    }
}

fn is_lock_contention(error: &io::Error) -> bool {
    if error.kind() == io::ErrorKind::WouldBlock {
        return true;
    }
    #[cfg(windows)]
    {
        // ERROR_SHARING_VIOLATION / ERROR_LOCK_VIOLATION.
        return matches!(error.raw_os_error(), Some(32) | Some(33));
    }
    #[cfg(not(windows))]
    {
        // EAGAIN / EWOULDBLOCK. EACCES is deliberately not treated as
        // contention because it can represent a real permission problem.
        matches!(error.raw_os_error(), Some(11) | Some(35))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn second_guard_for_same_profile_is_rejected() {
        let root = tempdir().unwrap();
        let profile = root.path().join("profile");
        let _first = InstanceGuard::acquire(&profile, "installation-a").unwrap();
        let error = match InstanceGuard::acquire(&profile, "installation-a") {
            Ok(_) => panic!("second instance unexpectedly acquired the profile"),
            Err(error) => error,
        };
        assert_eq!(error.code(), crate::error::HostErrorCode::HostCapabilityUnavailable);
        assert_eq!(
            error.next_actions(),
            [HostNextAction::UseTrayMenuExit].as_slice()
        );
        assert!(!error.retryable());
    }

    #[test]
    fn different_profiles_are_independent() {
        let root = tempdir().unwrap();
        let _first = InstanceGuard::acquire(&root.path().join("one"), "installation-a").unwrap();
        let _second = InstanceGuard::acquire(&root.path().join("two"), "installation-a").unwrap();
    }

    #[test]
    fn stale_lock_file_can_be_relocked_and_is_not_removed() {
        let root = tempdir().unwrap();
        let profile = root.path().join("profile");
        fs::create_dir_all(&profile).unwrap();
        let lock_path = profile.join(INSTANCE_LOCK_FILE);
        fs::write(&lock_path, b"stale").unwrap();

        let first = InstanceGuard::acquire(&profile, "installation-a").unwrap();
        let bound = first.profile().to_path_buf();
        drop(first);
        assert!(lock_path.is_file());

        let _second = InstanceGuard::acquire(&profile, "installation-a").unwrap();
        assert_eq!(bound, fs::canonicalize(&profile).unwrap());
    }

    #[test]
    fn record_is_bound_to_profile_and_installation() {
        let root = tempdir().unwrap();
        let profile = root.path().join("profile");
        let _guard = InstanceGuard::acquire(&profile, "installation-a").unwrap();
        let record: LockRecord =
            serde_json::from_slice(&fs::read(profile.join(INSTANCE_LOCK_FILE)).unwrap()).unwrap();
        assert_eq!(record.schema_version, LOCK_SCHEMA_VERSION);
        assert_eq!(record.installation_id, "installation-a");
        assert_eq!(record.profile, fs::canonicalize(&profile).unwrap());
        assert_eq!(record.pid, std::process::id());
        assert!(record.created_unix > 0);
    }
}
