//! Experimental native credential helper.
//!
//! This is **not integrated** with the product credential service or SSH. The
//! production SSH credential path remains in the Python credential service.
//! This helper only reserves a private, installation-scoped namespace for
//! future native credentials; it does not migrate or read existing credentials.
//!
//! Service scope: `org.operon.studio.experimental/<installation_id>`.
//! Accounts and values are validated and bounded. No Tauri command is declared
//! here, so neither a secret nor a credential operation is exposed to the
//! renderer. Errors carry only the canonical `HostError` message; keyring error
//! text and secret values are never copied into an error or log.

use crate::error::{HostError, HostNextAction};
use keyring::{Entry, Error as KeyringError};

const SERVICE_PREFIX: &str = "org.operon.studio.experimental";
const MAX_IDENTIFIER_BYTES: usize = 128;
const MAX_SECRET_BYTES: usize = 8192;

/// A secret value that deliberately has no `Debug`, `Display` or `Serialize`.
///
/// Callers must not log the exposed value. This type does not claim to zero
/// memory on drop; it prevents accidental formatting/serialization instead.
pub struct Secret(String);

impl Secret {
    fn new(value: String) -> Self {
        Self(value)
    }

    /// Borrow the secret for the one caller that needs it.
    pub fn expose(&self) -> &str {
        &self.0
    }
}

/// Store failure without any platform error text.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CredentialStoreError {
    Unavailable,
}

/// Injectable keyring boundary for tests and future platform adapters.
pub trait CredentialStore: Send + Sync {
    fn get(&self, service: &str, account: &str) -> Result<Option<String>, CredentialStoreError>;
    fn set(&self, service: &str, account: &str, value: &str) -> Result<(), CredentialStoreError>;
    fn delete(&self, service: &str, account: &str) -> Result<(), CredentialStoreError>;
}

/// Read an experimental native credential.
pub fn get_native_credential(
    installation_id: &str,
    account: &str,
) -> Result<Option<Secret>, HostError> {
    get_native_credential_with(&KeyringStore, installation_id, account)
}

/// Write an experimental native credential.
pub fn set_native_credential(
    installation_id: &str,
    account: &str,
    value: &str,
) -> Result<(), HostError> {
    set_native_credential_with(&KeyringStore, installation_id, account, value)
}

/// Delete an experimental native credential. Missing entries are success.
pub fn delete_native_credential(installation_id: &str, account: &str) -> Result<(), HostError> {
    delete_native_credential_with(&KeyringStore, installation_id, account)
}

/// Read through an injected store.
pub fn get_native_credential_with(
    store: &dyn CredentialStore,
    installation_id: &str,
    account: &str,
) -> Result<Option<Secret>, HostError> {
    let (service, account) = scope(installation_id, account)?;
    let value = store
        .get(&service, account)
        .map_err(|_| store_unavailable())?;
    Ok(value.map(Secret::new))
}

/// Write through an injected store.
pub fn set_native_credential_with(
    store: &dyn CredentialStore,
    installation_id: &str,
    account: &str,
    value: &str,
) -> Result<(), HostError> {
    let (service, account) = scope(installation_id, account)?;
    if value.is_empty() || value.len() > MAX_SECRET_BYTES {
        return Err(HostError::request_stale(None));
    }
    store
        .set(&service, account, value)
        .map_err(|_| store_unavailable())
}

/// Delete through an injected store.
pub fn delete_native_credential_with(
    store: &dyn CredentialStore,
    installation_id: &str,
    account: &str,
) -> Result<(), HostError> {
    let (service, account) = scope(installation_id, account)?;
    store
        .delete(&service, account)
        .map_err(|_| store_unavailable())
}

fn scope<'a>(installation_id: &str, account: &'a str) -> Result<(String, &'a str), HostError> {
    if !valid_installation_id(installation_id) || !valid_account(account) {
        return Err(HostError::request_stale(None));
    }
    Ok((format!("{SERVICE_PREFIX}/{installation_id}"), account))
}

fn valid_installation_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_IDENTIFIER_BYTES
        && value.trim() == value
        && !value.chars().any(char::is_control)
        // The service scope uses '/' as the installation separator. Do not let
        // an installation ID create a second scope or a path-like target.
        && !value.contains('/')
        && !value.contains('\\')
}

fn valid_account(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_IDENTIFIER_BYTES
        && value != "."
        && value != ".."
        && value.bytes().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'.' | b':' | b'@' | b'-')
        })
}

fn store_unavailable() -> HostError {
    HostError::capability_unavailable(HostNextAction::OpenHostLogs, None)
}

struct KeyringStore;

impl CredentialStore for KeyringStore {
    fn get(&self, service: &str, account: &str) -> Result<Option<String>, CredentialStoreError> {
        match entry(service, account)?.get_password() {
            Ok(value) => Ok(Some(value)),
            Err(KeyringError::NoEntry) => Ok(None),
            Err(_) => Err(CredentialStoreError::Unavailable),
        }
    }

    fn set(&self, service: &str, account: &str, value: &str) -> Result<(), CredentialStoreError> {
        entry(service, account)?
            .set_password(value)
            .map_err(|_| CredentialStoreError::Unavailable)
    }

    fn delete(&self, service: &str, account: &str) -> Result<(), CredentialStoreError> {
        match entry(service, account)?.delete_credential() {
            Ok(()) => Ok(()),
            Err(KeyringError::NoEntry) => Ok(()),
            Err(_) => Err(CredentialStoreError::Unavailable),
        }
    }
}

fn entry(service: &str, account: &str) -> Result<Entry, CredentialStoreError> {
    Entry::new(service, account).map_err(|_| CredentialStoreError::Unavailable)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::Mutex;

    #[derive(Default)]
    struct MemoryStore {
        values: Mutex<HashMap<(String, String), String>>,
    }

    impl CredentialStore for MemoryStore {
        fn get(
            &self,
            service: &str,
            account: &str,
        ) -> Result<Option<String>, CredentialStoreError> {
            Ok(self
                .values
                .lock()
                .unwrap()
                .get(&(service.to_owned(), account.to_owned()))
                .cloned())
        }

        fn set(
            &self,
            service: &str,
            account: &str,
            value: &str,
        ) -> Result<(), CredentialStoreError> {
            self.values
                .lock()
                .unwrap()
                .insert((service.to_owned(), account.to_owned()), value.to_owned());
            Ok(())
        }

        fn delete(&self, service: &str, account: &str) -> Result<(), CredentialStoreError> {
            self.values
                .lock()
                .unwrap()
                .remove(&(service.to_owned(), account.to_owned()));
            Ok(())
        }
    }

    struct FailingStore;

    impl CredentialStore for FailingStore {
        fn get(
            &self,
            _service: &str,
            _account: &str,
        ) -> Result<Option<String>, CredentialStoreError> {
            Err(CredentialStoreError::Unavailable)
        }

        fn set(
            &self,
            _service: &str,
            _account: &str,
            _value: &str,
        ) -> Result<(), CredentialStoreError> {
            Err(CredentialStoreError::Unavailable)
        }

        fn delete(&self, _service: &str, _account: &str) -> Result<(), CredentialStoreError> {
            Err(CredentialStoreError::Unavailable)
        }
    }

    #[test]
    fn round_trip_uses_experimental_installation_scope() {
        let store = MemoryStore::default();
        set_native_credential_with(&store, "installation-1", "account-1", "value-1").unwrap();

        {
            let values = store.values.lock().unwrap();
            assert_eq!(values.len(), 1);
            let (service, account) = values.keys().next().unwrap();
            assert_eq!(
                service.as_str(),
                "org.operon.studio.experimental/installation-1"
            );
            assert_eq!(account.as_str(), "account-1");
        }

        let value = get_native_credential_with(&store, "installation-1", "account-1")
            .unwrap()
            .expect("stored credential");
        assert_eq!(value.expose(), "value-1");

        delete_native_credential_with(&store, "installation-1", "account-1").unwrap();
        assert!(
            get_native_credential_with(&store, "installation-1", "account-1")
                .unwrap()
                .is_none()
        );
        // Deleting a missing entry is idempotent.
        delete_native_credential_with(&store, "installation-1", "account-1").unwrap();
    }

    #[test]
    fn missing_credential_is_none() {
        let store = MemoryStore::default();
        assert!(
            get_native_credential_with(&store, "installation-1", "account-1")
                .unwrap()
                .is_none()
        );
    }

    #[test]
    fn rejects_invalid_identifiers() {
        let store = MemoryStore::default();
        for installation in [
            "",
            " leading",
            "trailing ",
            "bad/scope",
            "bad\\scope",
            "bad\nscope",
        ] {
            let error = get_native_credential_with(&store, installation, "account")
                .err()
                .expect("invalid installation must fail");
            assert_eq!(error.code(), crate::error::HostErrorCode::HostRequestStale);
        }
        for account in ["", ".", "..", "bad/account", "bad account", "bad\naccount"] {
            let error = get_native_credential_with(&store, "installation", account)
                .err()
                .expect("invalid account must fail");
            assert_eq!(error.code(), crate::error::HostErrorCode::HostRequestStale);
        }
    }

    #[test]
    fn rejects_empty_and_oversize_values_without_writing() {
        let store = MemoryStore::default();
        assert!(set_native_credential_with(&store, "installation", "account", "").is_err());
        let oversize = "x".repeat(MAX_SECRET_BYTES + 1);
        assert!(set_native_credential_with(&store, "installation", "account", &oversize).is_err());
        assert!(store.values.lock().unwrap().is_empty());
    }

    #[test]
    fn maximum_bounded_value_is_accepted() {
        let store = MemoryStore::default();
        let maximum = "x".repeat(MAX_SECRET_BYTES);
        set_native_credential_with(&store, "installation", "account", &maximum).unwrap();
        assert_eq!(
            get_native_credential_with(&store, "installation", "account")
                .unwrap()
                .unwrap()
                .expose()
                .len(),
            MAX_SECRET_BYTES
        );
    }

    #[test]
    fn store_errors_are_redacted() {
        let error =
            set_native_credential_with(&FailingStore, "installation", "account", "super-secret")
                .unwrap_err();
        assert_eq!(
            error.code(),
            crate::error::HostErrorCode::HostCapabilityUnavailable
        );
        assert!(!format!("{error:?}").contains("super-secret"));
        assert!(!format!("{error}").contains("super-secret"));
    }

    #[cfg(windows)]
    #[test]
    fn windows_keyring_round_trip_is_opt_in_and_cleans_up() {
        let enabled = std::env::var("OPERON_RUN_KEYRING_TEST").ok();
        if enabled.as_deref() != Some("1") {
            return;
        }

        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0);
        let unique = format!("d{}-{nanos}", std::process::id());
        let installation = format!("installation-{unique}");
        let account = format!("account-{unique}");

        struct Cleanup {
            installation: String,
            account: String,
        }

        impl Drop for Cleanup {
            fn drop(&mut self) {
                let _ = delete_native_credential(&self.installation, &self.account);
            }
        }

        let _cleanup = Cleanup {
            installation: installation.clone(),
            account: account.clone(),
        };

        set_native_credential(&installation, &account, "opt-in-test-value").unwrap();
        let value = get_native_credential(&installation, &account)
            .unwrap()
            .expect("opt-in keyring entry");
        assert_eq!(value.expose(), "opt-in-test-value");
        delete_native_credential(&installation, &account).unwrap();
        assert!(get_native_credential(&installation, &account)
            .unwrap()
            .is_none());
    }
}
