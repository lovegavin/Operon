# Tauri delegation progress

Status snapshot for the coordinated T01 pass. This is not release evidence and
does not claim a native Tauri adapter.

| Session | Scope | Implementation | Review | Automated tests | Real interaction |
|---|---|---|---|---|---|
| A | Shared T01 contract, baseline observations, bridge v1 document | Done | Pending Codex review | `frontend/src/host/types.test.ts` written; not run because frontend dependencies are absent | Pending |
| B | Browser/WebView2 adapters, close lifecycle, narrow App wiring | Not implemented | Pending | Not run | Pending |
| C | Rust backend process and window lifecycle | Not implemented | Pending | Not run | Pending |
| D | Dialogs, artifacts, credentials, navigation | Not implemented | Pending | Not run | Pending |
| E | Experimental packaging and updates | Not implemented | Pending | Not run | Pending |
| F | Independent installed-window acceptance | Not implemented | Pending | Not run | Pending |

## T01 gate

- Contract: shared six-method `DesktopHost`, stable error shape and exact legacy
  wire strings are defined in `frontend/src/host/types.ts`.
- Adapters: not implemented; no native adapter exists.
- App: unchanged in this pass. No File/Quit control was added.
- Verification: the types test file exists but has not been executed. No build,
  WebView2 smoke test, browser interaction or installed-window check was run.
- Gate result: pending review. T02 Rust work must not start until T01 is reviewed
  and its adapters and tests actually pass.

## T00 baseline

- `verification/tauri/baseline.json` records source observations only.
- Timings are null and explicitly marked not measured.
- Rust and MSVC availability is recorded as missing or unverified.
- No historical timing or build result was copied into the evidence.
