# Operon Studio 5.6.3

Released 2026-11-18. Library: **main-v1.0.2** (unchanged).

## Added

- **Official-unit cards.** Every database or weight resource is shown as one card
  per official maintenance unit (`afdb`, `ProteinMPNN`, `Pfam-A.hmm`,
  `esm2_t6_8M_UR50D.pt`, ...). Each card carries the download URL, the unit size,
  the official name and the per-file presence report.
- **Missing-file report.** When a unit is missing or partially present, the card
  lists the files that are still missing, so it is clear what a link or download
  has to provide.
- **Remote versus local manifest warning.** When a remote host reports a
  different environment list than the local installation, the panel states how
  many environments each side has, which names differ and which manifest file
  each side used.

## Changed

- Environment detail now opens two entry cards (dependencies, resources) in the
  same card style as the environment cards; dependency and unit cards use that
  same style and are laid out in a single centered column.
- Every "install all" action sits in the top-right corner of its card group; the
  duplicate download-all action was removed, and cancel remains available only
  where a running operation exists.
- Progress bars render the real percentage as a filling bar and print
  `NN% - phase`, instead of an indeterminate sweep animation.
- The back control moved to the bottom-left of the detail dialog.
- A note states that installs and downloads keep running in the background when
  the window is closed.

## Fixed

- F-36 progress bar ignored the reported percentage and only animated a fixed
  width block.
- F-37 the environment detail dialog leaked a `targets`/`onTarget` prop pair that
  no longer existed, so the "execution location" selector was missing from the
  panel header.
- F-38 unit cards dropped the download URL and the missing-file list, so an
  incomplete unit looked identical to an empty one.

## Verification

Clean install of `Operon_Setup-5.6.3.exe` (24 s): 18 environments, 1,177
operators assigned, 16 resources, 16 official units, library `main-v1.0.2`.
API and UI checks are listed in the 5.6.3 test report.
