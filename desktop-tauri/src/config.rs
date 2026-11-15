//! Typed experimental host configuration and profile guard.
//!
//! The configuration file is installation metadata, not a source of defaults.
//! Relative paths resolve against the directory containing the configuration
//! file. There is no `PATH`, user-home or production-profile fallback.

use serde::{Deserialize, Serialize};
use std::fmt;
use std::fs;
use std::io;
use std::path::{Component, Path, PathBuf};

/// Marker that claims a profile directory for this experiment.
pub const PROFILE_MARKER_FILE: &str = ".operon-experimental.json";
/// Runtime preference file owned by the experimental profile.
pub const RUNTIME_CONFIG_FILE: &str = "runtime.json";
/// Owned log directory for the experimental profile.
pub const LOGS_DIR: &str = "logs";

const MARKER_SCHEMA_VERSION: u32 = 1;
const BACKEND_ENTRY_POINT: &str = "scripts/desktop_server.py";
const FRONTEND_INDEX: &str = "index.html";

/// Parsed host configuration.
///
/// Construct it through [`HostConfig::load`] so every input is resolved and
/// validated. The derived `Deserialize` is the raw file shape; it is not the
/// supported loader.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct HostConfig {
    pub installation_id: String,
    pub backend_root: PathBuf,
    pub python: PathBuf,
    pub frontend: PathBuf,
    pub profile: PathBuf,
}

/// Existing runtime inputs must have the expected file-system kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PathKind {
    File,
    Directory,
}

impl fmt::Display for PathKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::File => f.write_str("file"),
            Self::Directory => f.write_str("directory"),
        }
    }
}

/// Configuration and experimental-profile failures.
///
/// These are startup diagnostics, not renderer errors. Renderer-visible failures
/// use [`crate::error::HostError`].
#[derive(Debug)]
pub enum ConfigError {
    Read {
        path: PathBuf,
        source: io::Error,
    },
    Parse {
        path: PathBuf,
        source: serde_json::Error,
    },
    InvalidConfigPath {
        path: PathBuf,
    },
    EmptyPath {
        field: &'static str,
    },
    InvalidInstallationId,
    PathUnavailable {
        field: &'static str,
        path: PathBuf,
        source: io::Error,
    },
    WrongPathKind {
        field: &'static str,
        path: PathBuf,
        expected: PathKind,
    },
    MissingBackendScript {
        path: PathBuf,
    },
    MissingFrontendIndex {
        path: PathBuf,
    },
    ProfileCreate {
        path: PathBuf,
        source: io::Error,
    },
    ProfileRead {
        path: PathBuf,
        source: io::Error,
    },
    ProfileMarkerRead {
        path: PathBuf,
        source: io::Error,
    },
    ProfileMarkerParse {
        path: PathBuf,
        source: serde_json::Error,
    },
    ForeignProfile {
        path: PathBuf,
    },
    ProfileMarkerWrite {
        path: PathBuf,
        source: io::Error,
    },
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Read { path, source } => {
                write!(f, "cannot read host config {}: {source}", path.display())
            }
            Self::Parse { path, source } => {
                write!(f, "cannot parse host config {}: {source}", path.display())
            }
            Self::InvalidConfigPath { path } => {
                write!(f, "host config path has no parent: {}", path.display())
            }
            Self::EmptyPath { field } => {
                write!(f, "host config field {field} must not be empty")
            }
            Self::InvalidInstallationId => f.write_str(
                "host config installation_id must be non-empty, trimmed and contain no control characters",
            ),
            Self::PathUnavailable {
                field,
                path,
                source,
            } => write!(
                f,
                "host config field {field} is unavailable at {}: {source}",
                path.display()
            ),
            Self::WrongPathKind {
                field,
                path,
                expected,
            } => write!(
                f,
                "host config field {field} must be a {expected}: {}",
                path.display()
            ),
            Self::MissingBackendScript { path } => write!(
                f,
                "backend management entry point is missing: {}",
                path.display()
            ),
            Self::MissingFrontendIndex { path } => {
                write!(f, "frontend index is missing: {}", path.display())
            }
            Self::ProfileCreate { path, source } => write!(
                f,
                "cannot create experimental profile {}: {source}",
                path.display()
            ),
            Self::ProfileRead { path, source } => {
                write!(f, "cannot read experimental profile {}: {source}", path.display())
            }
            Self::ProfileMarkerRead { path, source } => {
                write!(f, "cannot read profile marker {}: {source}", path.display())
            }
            Self::ProfileMarkerParse { path, source } => {
                write!(f, "cannot parse profile marker {}: {source}", path.display())
            }
            Self::ForeignProfile { path } => write!(
                f,
                "profile {} is not owned by this experimental installation",
                path.display()
            ),
            Self::ProfileMarkerWrite { path, source } => {
                write!(f, "cannot write profile marker {}: {source}", path.display())
            }
        }
    }
}

impl std::error::Error for ConfigError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Read { source, .. }
            | Self::PathUnavailable { source, .. }
            | Self::ProfileCreate { source, .. }
            | Self::ProfileRead { source, .. }
            | Self::ProfileMarkerRead { source, .. }
            | Self::ProfileMarkerWrite { source, .. } => Some(source),
            Self::Parse { source, .. } | Self::ProfileMarkerParse { source, .. } => Some(source),
            _ => None,
        }
    }
}

#[derive(Serialize, Deserialize)]
struct ExperimentalProfileMarker {
    schema_version: u32,
    installation_id: String,
}

impl HostConfig {
    /// Read a configuration file, resolve every path and validate owned inputs.
    pub fn load(path: impl AsRef<Path>) -> Result<Self, ConfigError> {
        let path = path.as_ref();
        let bytes = fs::read(path).map_err(|source| ConfigError::Read {
            path: path.to_path_buf(),
            source,
        })?;
        let config: Self = serde_json::from_slice(&bytes).map_err(|source| ConfigError::Parse {
            path: path.to_path_buf(),
            source,
        })?;
        let canonical_config =
            fs::canonicalize(path).map_err(|source| ConfigError::PathUnavailable {
                field: "config",
                path: path.to_path_buf(),
                source,
            })?;
        let base = canonical_config
            .parent()
            .ok_or_else(|| ConfigError::InvalidConfigPath {
                path: path.to_path_buf(),
            })?;
        config.resolve(base)
    }

    /// `profile/runtime.json`; the existing runtime preference schema belongs
    /// to the management service.
    pub fn runtime_config_path(&self) -> PathBuf {
        self.profile.join(RUNTIME_CONFIG_FILE)
    }

    /// `profile/logs`; the backend owner creates and rotates files there.
    pub fn logs_dir(&self) -> PathBuf {
        self.profile.join(LOGS_DIR)
    }

    /// Marker path used to prove profile ownership before a backend spawn.
    pub fn profile_marker_path(&self) -> PathBuf {
        self.profile.join(PROFILE_MARKER_FILE)
    }

    /// Claim an empty profile, or verify that an existing profile carries this
    /// installation's marker. Unmarked non-empty profiles are never adopted.
    ///
    /// Call this before spawning the management service. It writes only the
    /// marker under the configured profile; it never consults a global profile.
    pub fn ensure_experimental_profile(&self) -> Result<(), ConfigError> {
        if self.profile.exists() {
            if !self.profile.is_dir() {
                return Err(ConfigError::WrongPathKind {
                    field: "profile",
                    path: self.profile.clone(),
                    expected: PathKind::Directory,
                });
            }
        } else {
            fs::create_dir_all(&self.profile).map_err(|source| ConfigError::ProfileCreate {
                path: self.profile.clone(),
                source,
            })?;
        }

        let mut entries =
            fs::read_dir(&self.profile).map_err(|source| ConfigError::ProfileRead {
                path: self.profile.clone(),
                source,
            })?;
        let first = entries.next();
        drop(entries);
        match first {
            None => self.write_marker(),
            Some(Ok(_)) => {
                if !self.profile_marker_path().is_file() {
                    return Err(ConfigError::ForeignProfile {
                        path: self.profile.clone(),
                    });
                }
                self.validate_marker()
            }
            Some(Err(source)) => Err(ConfigError::ProfileRead {
                path: self.profile.clone(),
                source,
            }),
        }
    }

    fn resolve(mut self, base: &Path) -> Result<Self, ConfigError> {
        self.installation_id = validate_installation_id(self.installation_id)?;
        self.python = resolve_existing(base, "python", &self.python, PathKind::File)?;
        self.backend_root = resolve_existing(
            base,
            "backend_root",
            &self.backend_root,
            PathKind::Directory,
        )?;
        let backend_script = self.backend_root.join(BACKEND_ENTRY_POINT);
        if !backend_script.is_file() {
            return Err(ConfigError::MissingBackendScript {
                path: backend_script,
            });
        }
        self.frontend = resolve_existing(base, "frontend", &self.frontend, PathKind::Directory)?;
        let frontend_index = self.frontend.join(FRONTEND_INDEX);
        if !frontend_index.is_file() {
            return Err(ConfigError::MissingFrontendIndex {
                path: frontend_index,
            });
        }
        self.profile = resolve_profile(base, &self.profile)?;
        Ok(self)
    }

    fn validate_marker(&self) -> Result<(), ConfigError> {
        let marker_path = self.profile_marker_path();
        let bytes = fs::read(&marker_path).map_err(|source| ConfigError::ProfileMarkerRead {
            path: marker_path.clone(),
            source,
        })?;
        let marker: ExperimentalProfileMarker =
            serde_json::from_slice(&bytes).map_err(|source| ConfigError::ProfileMarkerParse {
                path: marker_path,
                source,
            })?;
        if marker.schema_version != MARKER_SCHEMA_VERSION
            || marker.installation_id != self.installation_id
        {
            return Err(ConfigError::ForeignProfile {
                path: self.profile.clone(),
            });
        }
        Ok(())
    }

    fn write_marker(&self) -> Result<(), ConfigError> {
        let marker = ExperimentalProfileMarker {
            schema_version: MARKER_SCHEMA_VERSION,
            installation_id: self.installation_id.clone(),
        };
        let mut body = serde_json::to_vec_pretty(&marker)
            .expect("experimental profile marker is serializable");
        body.push(b'\n');

        let marker_path = self.profile_marker_path();
        // Exclusive creation never replaces another installation's marker.
        // A crash during the write leaves an invalid marker and fails closed.
        use std::io::Write;
        match fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&marker_path)
        {
            Ok(mut file) => file
                .write_all(&body)
                .and_then(|_| file.sync_all())
                .map_err(|source| ConfigError::ProfileMarkerWrite {
                    path: marker_path,
                    source,
                }),
            Err(source) if source.kind() == io::ErrorKind::AlreadyExists => self.validate_marker(),
            Err(source) => Err(ConfigError::ProfileMarkerWrite {
                path: marker_path,
                source,
            }),
        }
    }
}

fn validate_installation_id(value: String) -> Result<String, ConfigError> {
    if value.is_empty() || value.trim() != value || value.chars().any(char::is_control) {
        return Err(ConfigError::InvalidInstallationId);
    }
    Ok(value)
}

fn resolve_existing(
    base: &Path,
    field: &'static str,
    value: &Path,
    expected: PathKind,
) -> Result<PathBuf, ConfigError> {
    if value.as_os_str().is_empty() {
        return Err(ConfigError::EmptyPath { field });
    }
    let candidate = join_config_path(base, value);
    let canonical =
        fs::canonicalize(&candidate).map_err(|source| ConfigError::PathUnavailable {
            field,
            path: candidate,
            source,
        })?;
    let metadata = fs::metadata(&canonical).map_err(|source| ConfigError::PathUnavailable {
        field,
        path: canonical.clone(),
        source,
    })?;
    let matches = match expected {
        PathKind::File => metadata.is_file(),
        PathKind::Directory => metadata.is_dir(),
    };
    if !matches {
        return Err(ConfigError::WrongPathKind {
            field,
            path: canonical,
            expected,
        });
    }
    Ok(canonical)
}

fn resolve_profile(base: &Path, value: &Path) -> Result<PathBuf, ConfigError> {
    if value.as_os_str().is_empty() {
        return Err(ConfigError::EmptyPath { field: "profile" });
    }
    let candidate = join_config_path(base, value);
    match fs::canonicalize(&candidate) {
        Ok(canonical) => {
            if !canonical.is_dir() {
                return Err(ConfigError::WrongPathKind {
                    field: "profile",
                    path: canonical,
                    expected: PathKind::Directory,
                });
            }
            Ok(canonical)
        }
        Err(source) if source.kind() == io::ErrorKind::NotFound => Ok(normalize_path(candidate)),
        Err(source) => Err(ConfigError::PathUnavailable {
            field: "profile",
            path: candidate,
            source,
        }),
    }
}

fn join_config_path(base: &Path, value: &Path) -> PathBuf {
    if value.is_absolute() {
        value.to_path_buf()
    } else {
        base.join(value)
    }
}

fn normalize_path(path: PathBuf) -> PathBuf {
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                normalized.pop();
            }
            _ => normalized.push(component.as_os_str()),
        }
    }
    normalized
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::tempdir;

    fn fixture() -> (tempfile::TempDir, PathBuf) {
        let root = tempdir().unwrap();
        write_file(&root.path().join("backend/scripts/desktop_server.py"));
        write_file(&root.path().join("runtime/python.exe"));
        write_file(&root.path().join("frontend/index.html"));
        fs::create_dir_all(root.path().join("config")).unwrap();
        let config_path = root.path().join("config/host.json");
        (root, config_path)
    }

    fn write_file(path: &Path) {
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, b"fixture").unwrap();
    }

    fn config_json() -> serde_json::Value {
        json!({
            "installation_id": "experimental-installation",
            "backend_root": "../backend",
            "python": "../runtime/python.exe",
            "frontend": "../frontend",
            "profile": "../profile",
        })
    }

    fn write_config(path: &Path, value: &serde_json::Value) {
        fs::write(path, serde_json::to_vec_pretty(value).unwrap()).unwrap();
    }

    #[test]
    fn resolves_relative_paths_and_runtime_locations() {
        let (root, config_path) = fixture();
        write_config(&config_path, &config_json());
        let config = HostConfig::load(&config_path).expect("valid config");

        assert_eq!(config.installation_id, "experimental-installation");
        assert_eq!(
            config.backend_root,
            fs::canonicalize(root.path().join("backend")).unwrap()
        );
        assert_eq!(
            config.python,
            fs::canonicalize(root.path().join("runtime/python.exe")).unwrap()
        );
        assert_eq!(
            config.frontend,
            fs::canonicalize(root.path().join("frontend")).unwrap()
        );
        assert!(config.profile.is_absolute());
        assert!(config.profile.ends_with("profile"));
        assert_eq!(
            config.runtime_config_path(),
            config.profile.join(RUNTIME_CONFIG_FILE)
        );
        assert_eq!(config.logs_dir(), config.profile.join(LOGS_DIR));
    }

    #[test]
    fn traversal_components_resolve_from_the_config_directory() {
        let (root, _config) = fixture();
        let nested = root.path().join("config/deep");
        fs::create_dir_all(&nested).unwrap();
        let config_path = nested.join("host.json");
        let mut value = config_json();
        value["backend_root"] = json!("../../backend");
        value["python"] = json!("../../runtime/python.exe");
        value["frontend"] = json!("../../frontend");
        value["profile"] = json!("../../profile");
        write_config(&config_path, &value);

        let config = HostConfig::load(&config_path).expect("valid config");
        assert_eq!(
            config.backend_root,
            fs::canonicalize(root.path().join("backend")).unwrap()
        );
        assert_eq!(
            config.frontend,
            fs::canonicalize(root.path().join("frontend")).unwrap()
        );
    }

    #[test]
    fn rejects_unknown_config_fields() {
        let (_root, config_path) = fixture();
        let mut value = config_json();
        value["schema_version"] = json!(1);
        write_config(&config_path, &value);
        assert!(matches!(
            HostConfig::load(&config_path),
            Err(ConfigError::Parse { .. })
        ));
    }

    #[test]
    fn rejects_empty_installation_id() {
        let (_root, config_path) = fixture();
        let mut value = config_json();
        value["installation_id"] = json!("");
        write_config(&config_path, &value);
        assert!(matches!(
            HostConfig::load(&config_path),
            Err(ConfigError::InvalidInstallationId)
        ));
    }

    #[test]
    fn rejects_missing_python_without_a_path_lookup() {
        let (root, config_path) = fixture();
        fs::remove_file(root.path().join("runtime/python.exe")).unwrap();
        write_config(&config_path, &config_json());
        assert!(matches!(
            HostConfig::load(&config_path),
            Err(ConfigError::PathUnavailable {
                field: "python",
                ..
            })
        ));

        let mut bare = config_json();
        bare["python"] = json!("python.exe");
        write_config(&config_path, &bare);
        assert!(matches!(
            HostConfig::load(&config_path),
            Err(ConfigError::PathUnavailable {
                field: "python",
                ..
            })
        ));
    }

    #[test]
    fn rejects_python_that_is_not_a_file() {
        let (root, config_path) = fixture();
        fs::remove_file(root.path().join("runtime/python.exe")).unwrap();
        fs::create_dir_all(root.path().join("runtime/python.exe")).unwrap();
        write_config(&config_path, &config_json());
        assert!(matches!(
            HostConfig::load(&config_path),
            Err(ConfigError::WrongPathKind {
                field: "python",
                ..
            })
        ));
    }

    #[test]
    fn rejects_missing_backend_entry_point() {
        let (root, config_path) = fixture();
        fs::remove_file(root.path().join("backend/scripts/desktop_server.py")).unwrap();
        write_config(&config_path, &config_json());
        assert!(matches!(
            HostConfig::load(&config_path),
            Err(ConfigError::MissingBackendScript { .. })
        ));
    }

    #[test]
    fn rejects_missing_frontend_index() {
        let (root, config_path) = fixture();
        fs::remove_file(root.path().join("frontend/index.html")).unwrap();
        write_config(&config_path, &config_json());
        assert!(matches!(
            HostConfig::load(&config_path),
            Err(ConfigError::MissingFrontendIndex { .. })
        ));
    }

    #[test]
    fn empty_profile_is_claimed_with_the_installation_marker() {
        let (_root, config_path) = fixture();
        write_config(&config_path, &config_json());
        let config = HostConfig::load(&config_path).expect("valid config");

        config.ensure_experimental_profile().expect("claim profile");
        let marker_path = config.profile_marker_path();
        assert!(marker_path.is_file());
        let marker: serde_json::Value =
            serde_json::from_slice(&fs::read(&marker_path).unwrap()).unwrap();
        assert_eq!(marker["schema_version"], json!(1));
        assert_eq!(
            marker["installation_id"],
            json!("experimental-installation")
        );

        config
            .ensure_experimental_profile()
            .expect("marker remains valid");
    }

    #[test]
    fn rejects_non_empty_unmarked_profile() {
        let (_root, config_path) = fixture();
        write_config(&config_path, &config_json());
        let config = HostConfig::load(&config_path).expect("valid config");
        fs::create_dir_all(&config.profile).unwrap();
        fs::write(config.profile.join("workspace.json"), b"{}").unwrap();

        assert!(matches!(
            config.ensure_experimental_profile(),
            Err(ConfigError::ForeignProfile { .. })
        ));
    }

    #[test]
    fn rejects_marker_for_another_installation() {
        let (_root, config_path) = fixture();
        write_config(&config_path, &config_json());
        let config = HostConfig::load(&config_path).expect("valid config");
        fs::create_dir_all(&config.profile).unwrap();
        fs::write(
            config.profile_marker_path(),
            br#"{"schema_version":1,"installation_id":"another-installation"}"#,
        )
        .unwrap();

        assert!(matches!(
            config.ensure_experimental_profile(),
            Err(ConfigError::ForeignProfile { .. })
        ));
    }

    #[test]
    fn rejects_malformed_profile_marker() {
        let (_root, config_path) = fixture();
        write_config(&config_path, &config_json());
        let config = HostConfig::load(&config_path).expect("valid config");
        fs::create_dir_all(&config.profile).unwrap();
        fs::write(config.profile_marker_path(), b"{not-json").unwrap();

        assert!(matches!(
            config.ensure_experimental_profile(),
            Err(ConfigError::ProfileMarkerParse { .. })
        ));
    }

    #[test]
    fn rejects_profile_path_that_is_a_file() {
        let (_root, config_path) = fixture();
        write_config(&config_path, &config_json());
        let config = HostConfig::load(&config_path).expect("valid config");
        fs::write(&config.profile, b"not-a-directory").unwrap();

        assert!(matches!(
            config.ensure_experimental_profile(),
            Err(ConfigError::WrongPathKind {
                field: "profile",
                ..
            })
        ));
    }
}
