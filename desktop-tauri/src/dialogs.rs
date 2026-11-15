//! Native open/save/folder selection.
//!
//! The renderer may choose only the kind of picker. It cannot supply an initial
//! directory, file filter, default file name, executable or command. A path
//! returned here is the user's real OS selection and is the authorization for
//! later use of that path; this module performs no filesystem I/O, does not
//! canonicalize, and never invents a fallback path.

use crate::error::HostError;
use rfd::AsyncFileDialog;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Picker kind exposed to the typed bridge.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SelectPathKind {
    OpenFile,
    SaveFile,
    Folder,
}

/// Show the native picker for `kind`.
///
/// Cancellation is `Ok(None)`. An empty path is also treated as cancellation;
/// it is never converted into a working-directory or home-directory path.
pub async fn select_path(kind: SelectPathKind) -> Result<Option<PathBuf>, HostError> {
    let dialog = AsyncFileDialog::new();
    let handle = match kind {
        SelectPathKind::OpenFile => dialog.pick_file().await,
        SelectPathKind::SaveFile => dialog.save_file().await,
        SelectPathKind::Folder => dialog.pick_folder().await,
    };
    Ok(normalize_selection(
        handle.map(|file| file.path().to_path_buf()),
    ))
}

fn normalize_selection(selected: Option<PathBuf>) -> Option<PathBuf> {
    selected.filter(|path| !path.as_os_str().is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cancellation_maps_to_none() {
        assert_eq!(normalize_selection(None), None);
    }

    #[test]
    fn empty_selection_is_not_a_fake_path() {
        assert_eq!(normalize_selection(Some(PathBuf::new())), None);
    }

    #[test]
    fn real_selection_is_returned_unchanged() {
        let selected = PathBuf::from(r"C:\data\results\plot.png");
        assert_eq!(normalize_selection(Some(selected.clone())), Some(selected));
    }

    #[test]
    fn picker_kind_serializes_snake_case() {
        assert_eq!(
            serde_json::to_string(&SelectPathKind::OpenFile).unwrap(),
            "\"open_file\""
        );
        assert_eq!(
            serde_json::to_string(&SelectPathKind::SaveFile).unwrap(),
            "\"save_file\""
        );
        assert_eq!(
            serde_json::to_string(&SelectPathKind::Folder).unwrap(),
            "\"folder\""
        );
        assert_eq!(
            serde_json::from_str::<SelectPathKind>("\"open_file\"").unwrap(),
            SelectPathKind::OpenFile
        );
    }
}
