//! Bounded, rotating, redacted file diagnostics for the owned management process.
//!
//! Diagnostics are written only below the configured profile's `logs/` directory.
//! Credentials are never formatted into host errors; this module additionally
//! removes known secret values and refuses credential-looking stdout lines.
//! Every line is bounded before it reaches disk, and the log itself is rotated at
//! a fixed size so a noisy child cannot grow an unbounded file.

use std::collections::HashSet;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

const LOG_FILE: &str = "native-host.log";
const ROTATED_FILE: &str = "native-host.1.log";
const MAX_LOG_BYTES: u64 = 4 * 1024 * 1024;
const MAX_LOG_LINE_BYTES: usize = 8 * 1024;
const MAX_SECRETS: usize = 8;
const MAX_SECRET_BYTES: usize = 512;

/// Which owned stream produced a diagnostic line.
#[derive(Debug, Clone, Copy)]
pub enum Stream {
    Stdout,
    Stderr,
    Host,
}

impl Stream {
    fn label(self) -> &'static str {
        match self {
            Self::Stdout => "stdout",
            Self::Stderr => "stderr",
            Self::Host => "host",
        }
    }
}

struct LogState {
    file: File,
    size: u64,
}

/// A profile-owned rotating diagnostics sink. It intentionally does not
/// implement `Debug`: it stores secret values used only for redaction.
pub struct Diagnostics {
    directory: PathBuf,
    state: Mutex<LogState>,
    secrets: Mutex<HashSet<String>>,
}

impl Diagnostics {
    /// Create `logs_dir` and open the current log file for appending.
    pub fn open(logs_dir: &Path) -> io::Result<Self> {
        fs::create_dir_all(logs_dir)?;
        let path = logs_dir.join(LOG_FILE);
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)?;
        let size = file.metadata()?.len();
        Ok(Self {
            directory: logs_dir.to_path_buf(),
            state: Mutex::new(LogState { file, size }),
            secrets: Mutex::new(HashSet::new()),
        })
    }

    /// Register a value that must never appear in a diagnostic line. Called
    /// with the receipt secret and the authenticated studio token.
    pub fn add_secret(&self, secret: &str) {
        if secret.is_empty()
            || secret.len() > MAX_SECRET_BYTES
            || secret.chars().any(char::is_control)
        {
            return;
        }
        if let Ok(mut secrets) = self.secrets.lock() {
            if secrets.len() < MAX_SECRETS {
                secrets.insert(secret.to_owned());
            }
        }
    }

    /// Record one owned stdout line after bounded redaction.
    pub fn stdout_line(&self, line: &str) {
        self.write(Stream::Stdout, line);
    }

    /// Record one owned stderr line after bounded redaction.
    pub fn stderr_line(&self, line: &str) {
        self.write(Stream::Stderr, line);
    }

    /// Record a host-generated diagnostic. Host messages never include tokens.
    pub fn host(&self, line: &str) {
        self.write(Stream::Host, line);
    }

    fn write(&self, stream: Stream, line: &str) {
        let mut safe = sanitize(line);
        if safe.is_empty() {
            return;
        }

        if let Ok(secrets) = self.secrets.lock() {
            for secret in secrets.iter() {
                if safe.contains(secret) {
                    safe = safe.replace(secret, "[redacted]");
                }
            }
        }

        // If a credential field survived (for example a JSON receipt printed by
        // a child), drop the whole line rather than risk persisting the value.
        if contains_credential_marker(&safe) {
            safe = "[redacted: credential-like output]".to_owned();
        }

        let safe = truncate_line(&safe, MAX_LOG_LINE_BYTES);
        let Ok(mut state) = self.state.lock() else {
            return;
        };

        let record = format!(
            "{} [{}] {}\n",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|value| value.as_secs())
                .unwrap_or(0),
            stream.label(),
            safe
        );
        let bytes = record.as_bytes();
        let projected = state.size.saturating_add(bytes.len() as u64);
        if projected > MAX_LOG_BYTES {
            if rotate(&mut state, &self.directory).is_err() && state.size > MAX_LOG_BYTES * 2 {
                return;
            }
        }
        if state.file.write_all(bytes).is_ok() {
            state.size = state.size.saturating_add(bytes.len() as u64);
        }
    }
}

fn rotate(state: &mut LogState, directory: &Path) -> io::Result<()> {
    let current = directory.join(LOG_FILE);
    let rotated = directory.join(ROTATED_FILE);
    let _ = fs::remove_file(&rotated);
    fs::rename(&current, &rotated)?;
    state.file = OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(&current)?;
    state.size = 0;
    Ok(())
}

fn sanitize(line: &str) -> String {
    let mut value = String::with_capacity(line.len().min(MAX_LOG_LINE_BYTES));
    for character in line.chars() {
        if character == '\t' || !character.is_control() {
            value.push(character);
        } else {
            value.push(' ');
        }
    }
    value.trim_end().to_owned()
}

fn contains_credential_marker(line: &str) -> bool {
    let lower = line.to_ascii_lowercase();
    [
        "\"token\"",
        "\"secret\"",
        "\"password\"",
        "\"passphrase\"",
        "\"authorization\"",
        "x-operon-bridge",
        "x-studio-token",
        "\"api_key\"",
        "\"apikey\"",
        "bearer ",
    ]
    .iter()
    .any(|marker| lower.contains(marker))
}

fn truncate_line(line: &str, max_bytes: usize) -> String {
    if line.len() <= max_bytes {
        return line.to_owned();
    }
    let mut end = max_bytes;
    while end > 0 && !line.is_char_boundary(end) {
        end -= 1;
    }
    let mut value = line[..end].to_owned();
    value.push_str(" [truncated]");
    value
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn redacts_registered_secret_values() {
        let directory = tempdir().unwrap();
        let diagnostics = Diagnostics::open(directory.path()).unwrap();
        diagnostics.add_secret("super-secret-value");
        diagnostics.stdout_line("child said super-secret-value");
        let text = fs::read_to_string(directory.path().join(LOG_FILE)).unwrap();
        assert!(!text.contains("super-secret-value"));
        assert!(text.contains("[redacted]"));
    }

    #[test]
    fn drops_credential_looking_lines() {
        let directory = tempdir().unwrap();
        let diagnostics = Diagnostics::open(directory.path()).unwrap();
        diagnostics.stdout_line(r#"{"token":"unknown-value"}"#);
        let text = fs::read_to_string(directory.path().join(LOG_FILE)).unwrap();
        assert!(!text.contains("unknown-value"));
        assert!(text.contains("credential-like"));
    }

    #[test]
    fn bounds_and_rotates_the_file() {
        let directory = tempdir().unwrap();
        let diagnostics = Diagnostics::open(directory.path()).unwrap();
        let line = "x".repeat(MAX_LOG_LINE_BYTES);
        for _ in 0..600 {
            diagnostics.host(&line);
        }
        let current = fs::metadata(directory.path().join(LOG_FILE)).unwrap().len();
        let rotated = fs::metadata(directory.path().join(ROTATED_FILE)).unwrap().len();
        assert!(current <= MAX_LOG_BYTES);
        assert!(rotated <= MAX_LOG_BYTES);
    }

    #[test]
    fn controls_are_removed() {
        assert_eq!(sanitize("a\u{0}b\nc"), "a b c");
    }
}
