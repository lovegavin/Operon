# Operon Studio 5.6.5

## Highlights

- Runtime status card shows the environment identifier as the heading and the
  localized name as the subtitle, so the same environment is recognizable in
  the desktop client, the CLI and a remote server listing.
- The environment entry card and the resource section of the same environment
  now report the same unit count. The card previously counted resource ids
  instead of maintenance units, which made `core` claim zero units while its
  detail page listed five.
- The detail footer with the back button is pinned to the bottom of the dialog
  instead of scrolling out of view.
- Operator coverage probe: every operator in a ready environment is submitted
  through the installed MCP server with synthesized or real inputs, and the
  measured outcome is recorded per operator instead of being inferred from the
  catalog.

## Fixes

- F-49: runtime-only inputs such as `structure_path` are not published in the
  operator `parameters` schema, so a client that only reads the catalog cannot
  supply them. The probe records the affected operators; the catalog change is
  tracked separately because it alters operator declarations.
- F-51: changing an environment's dependency set leaves the shared execution
  pool registered against the previous interpreter, and every submission fails
  with `The shared pool is unavailable; no local executor fallback was used`.
  Restarting the application clears the stale registration.
- F-53: the ProteinMPNN family resolved an invalid Python executable and failed
  with `[WinError 193] %1 is not a valid Win32 application`. Passing the
  environment interpreter explicitly makes the family run.
- F-54: `CsvReader` accepts exactly two dimensions, so an operator that needs
  two additional columns cannot be wired from a single CSV source. The probe
  reports these operators separately instead of counting them as failures.

## Verification on this build

- Clean installation of the 5.6.5 installer, server reported
  `5.6.5 (4a60ab5f)` on port 5793.
- `/api/libraries` reports `main-v1.0.4` with 18 environments, 1,177 operators,
  16 resources and 16 maintenance units.
- UI probe: 18 environment cards, first card renders `core` with the subtitle
  `基础运行时`, the `core` entry card and its resource section both report five
  units, and the detail footer is `position: sticky` at the bottom of the
  dialog.
- Operator probe: see the coverage section of the 5.6.5 test report for the
  measured per-operator outcome.

## Known limitations

- Operators whose runtime inputs are missing from the catalog schema still need
  a client that knows the convention, and a few families need several input
  dimensions that the CSV reader cannot provide.
- Packages that are only published for Linux and macOS (HMMER, antiSMASH
  databases, Infernal) cannot be installed on Windows.
