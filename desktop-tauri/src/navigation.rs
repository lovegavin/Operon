//! Navigation and external documentation policy.
//!
//! This module deliberately exposes no general-purpose URL opener. The only
//! external URL accepted by [`open_documentation`] is the project documentation
//! under `https://github.com/lovegavin/Operon`.
//!
//! [`allow_owned_navigation`] is a main-frame/top-level-navigation predicate.
//! Callers must still deny subframe navigation and new-window privileges in the
//! Tauri capability/configuration layer; a URL predicate cannot revoke those
//! privileges by itself.

use crate::error::{HostError, HostNextAction};
use url::Url;

/// Canonical project documentation root.
pub const DOCUMENTATION_BASE_URL: &str = "https://github.com/lovegavin/Operon";

/// True only for a same-origin, top-level navigation to the owned UI root.
///
/// The comparison is exact for scheme, host and effective port. Userinfo,
/// non-HTTP(S) schemes, explicit alternate ports, any path other than `/`, and
/// any query/fragment are rejected. This intentionally blocks navigating the
/// main window to API result bodies (for example an artifact `.../open` URL).
pub fn allow_owned_navigation(target: &Url, origin: &Url) -> bool {
    if !is_http_url(origin) || !is_http_url(target) {
        return false;
    }
    if has_userinfo(origin) || has_userinfo(target) {
        return false;
    }
    // The configured origin is a bare origin, never a path or query carrier.
    if origin.path() != "/" || origin.query().is_some() || origin.fragment().is_some() {
        return false;
    }
    if target.scheme() != origin.scheme() {
        return false;
    }
    if target.host_str() != origin.host_str() {
        return false;
    }
    if target.port_or_known_default() != origin.port_or_known_default() {
        return false;
    }
    target.path() == "/" && target.query().is_none() && target.fragment().is_none()
}

/// True only for HTTPS GitHub URLs in the project repository.
///
/// An explicit port is rejected even when it is the HTTPS default. This avoids
/// credential/port confusion in the OS-browser handoff. Sub-paths and fragments
/// (document anchors) are allowed; query strings are not.
pub fn is_documentation_url(url: &Url) -> bool {
    if url.scheme() != "https" || has_userinfo(url) || url.port().is_some() {
        return false;
    }
    if url.host_str() != Some("github.com") || url.query().is_some() {
        return false;
    }
    let path = url.path();
    path == "/lovegavin/Operon" || path.starts_with("/lovegavin/Operon/")
}

/// Open the project documentation after enforcing [`is_documentation_url`].
///
/// This is the only public URL-opening entry point in the host. The caller
/// should expose a fixed command (or pass only the configured documentation
/// URL), not a renderer-provided arbitrary URL.
pub fn open_documentation(url: &Url) -> Result<(), HostError> {
    open_documentation_with(url, &SystemDocumentationOpener)
}

/// Open the canonical project documentation root.
pub fn open_default_documentation() -> Result<(), HostError> {
    let url = Url::parse(DOCUMENTATION_BASE_URL).map_err(|_| HostError::bridge_unavailable())?;
    open_documentation(&url)
}

/// Test seam for the OS browser handoff.
pub trait DocumentationOpener: Send + Sync {
    fn open(&self, url: &Url) -> Result<(), ()>;
}

/// Policy-checked documentation opening with an injected OS opener.
pub fn open_documentation_with<O: DocumentationOpener>(
    url: &Url,
    opener: &O,
) -> Result<(), HostError> {
    if !is_documentation_url(url) {
        return Err(HostError::unsupported(None));
    }
    opener
        .open(url)
        .map_err(|_| HostError::capability_unavailable(HostNextAction::OpenHostLogs, None))
}

fn is_http_url(url: &Url) -> bool {
    matches!(url.scheme(), "http" | "https") && url.host().is_some()
}

fn has_userinfo(url: &Url) -> bool {
    !url.username().is_empty() || url.password().is_some()
}

struct SystemDocumentationOpener;

impl DocumentationOpener for SystemDocumentationOpener {
    fn open(&self, url: &Url) -> Result<(), ()> {
        open_text_with_system(url.as_str())
    }
}

#[cfg(windows)]
fn open_text_with_system(value: &str) -> Result<(), ()> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::UI::Shell::ShellExecuteW;

    let operation: Vec<u16> = "open\0".encode_utf16().collect();
    let target: Vec<u16> = std::ffi::OsStr::new(value)
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    // Zero is a valid null HWND for both windows-sys pointer and integer types.
    let hwnd: windows_sys::Win32::Foundation::HWND = unsafe { std::mem::zeroed() };
    let result = unsafe {
        ShellExecuteW(
            hwnd,
            operation.as_ptr(),
            target.as_ptr(),
            std::ptr::null(),
            std::ptr::null(),
            1, // SW_SHOWNORMAL
        )
    };
    if result as isize > 32 {
        Ok(())
    } else {
        Err(())
    }
}

#[cfg(not(windows))]
fn open_text_with_system(_value: &str) -> Result<(), ()> {
    // The Windows x64 host is the first supported experiment. Do not silently
    // fall back to a shell command on other platforms.
    Err(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    fn url(value: &str) -> Url {
        Url::parse(value).expect("valid test URL")
    }

    #[test]
    fn allows_exact_origin_root() {
        let origin = url("https://operon.example:8443/");
        assert!(allow_owned_navigation(
            &url("https://operon.example:8443/"),
            &origin
        ));
        assert!(allow_owned_navigation(
            &url("https://OPERON.EXAMPLE:8443/"),
            &origin
        ));
        assert!(allow_owned_navigation(
            &url("https://operon.example/"),
            &url("https://operon.example:443/")
        ));
    }

    #[test]
    fn rejects_non_root_paths_and_queries() {
        let origin = url("https://operon.example/");
        for target in [
            "https://operon.example/index.html",
            "https://operon.example/api/v1/plans/run/artifacts/a/files/f/open",
            "https://operon.example/?x=1",
            "https://operon.example/#/canvas",
        ] {
            assert!(
                !allow_owned_navigation(&url(target), &origin),
                "must reject {target}"
            );
        }
    }

    #[test]
    fn rejects_malicious_hosts_and_userinfo() {
        let origin = url("https://operon.example/");
        for target in [
            "https://evil.example/",
            "https://operon.example.evil.example/",
            "https://sub.operon.example/",
            "https://operon.example@evil.example/",
            "https://user@operon.example/",
            "https://user:pass@operon.example/",
        ] {
            assert!(
                !allow_owned_navigation(&url(target), &origin),
                "must reject {target}"
            );
        }
    }

    #[test]
    fn rejects_alternate_ports_and_schemes() {
        let origin = url("https://operon.example:8443/");
        for target in [
            "https://operon.example:443/",
            "http://operon.example:8443/",
            "https://operon.example:8444/",
        ] {
            assert!(
                !allow_owned_navigation(&url(target), &origin),
                "must reject {target}"
            );
        }
    }

    #[test]
    fn rejects_executable_and_opaque_schemes() {
        let origin = url("https://operon.example/");
        for target in [
            "javascript:alert(1)",
            "file:///C:/Windows/System32/cmd.exe",
            "data:text/html,<script>alert(1)</script>",
            "ms-settings:privacy",
        ] {
            assert!(
                !allow_owned_navigation(&url(target), &origin),
                "must reject {target}"
            );
        }
    }

    #[test]
    fn rejects_invalid_origin_forms() {
        let target = url("https://operon.example/");
        for origin in [
            "https://user@operon.example/",
            "https://operon.example/path/",
            "https://operon.example/?x=1",
            "javascript:alert(1)",
            "file:///C:/Windows/",
        ] {
            assert!(
                !allow_owned_navigation(&target, &url(origin)),
                "must reject origin {origin}"
            );
        }
    }

    #[test]
    fn documentation_allowlist_is_exact_repository() {
        for accepted in [
            "https://github.com/lovegavin/Operon",
            "https://github.com/lovegavin/Operon/",
            "https://github.com/lovegavin/Operon/blob/main/docs/README.md",
            "https://github.com/lovegavin/Operon/blob/main/docs/README.md#install",
        ] {
            assert!(is_documentation_url(&url(accepted)), "must accept {accepted}");
        }

        for rejected in [
            "http://github.com/lovegavin/Operon",
            "https://github.com:443/lovegavin/Operon",
            "https://github.com:8443/lovegavin/Operon",
            "https://user@github.com/lovegavin/Operon",
            "https://user:pass@github.com/lovegavin/Operon",
            "https://github.com.evil.example/lovegavin/Operon",
            "https://evil.example/lovegavin/Operon",
            "https://github.com/lovegavin/Operon-evil",
            "https://github.com/lovegavin/operon",
            "https://github.com/lovegavin/Operon?tab=readme-ov-file",
            "https://github.com/lovegavin/Operon/../../etc/passwd",
            "file:///lovegavin/Operon",
        ] {
            assert!(
                !is_documentation_url(&url(rejected)),
                "must reject {rejected}"
            );
        }
    }

    #[derive(Default)]
    struct MockOpener {
        calls: Mutex<Vec<String>>,
    }

    impl DocumentationOpener for MockOpener {
        fn open(&self, url: &Url) -> Result<(), ()> {
            self.calls.lock().unwrap().push(url.to_string());
            Ok(())
        }
    }

    #[test]
    fn invalid_documentation_url_never_reaches_the_os() {
        let opener = MockOpener::default();
        let error = open_documentation_with(&url("https://evil.example/"), &opener).unwrap_err();
        assert_eq!(error.code(), crate::error::HostErrorCode::HostUnsupported);
        assert!(opener.calls.lock().unwrap().is_empty());
    }

    #[test]
    fn valid_documentation_url_reaches_the_injected_opener_once() {
        let opener = MockOpener::default();
        open_documentation_with(
            &url("https://github.com/lovegavin/Operon/blob/main/docs/README.md"),
            &opener,
        )
        .unwrap();
        assert_eq!(opener.calls.lock().unwrap().len(), 1);
    }
}
