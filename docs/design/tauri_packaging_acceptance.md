# Experimental Tauri packaging acceptance (E/F)

This is an experimental Windows host acceptance, not a production release.
The backend stays at the validated 5.3.0 baseline. The operator library, frozen
parameter JSON, memory management and scientific environment isolation are not
changed by this work. A passing build is not an installed-product acceptance.

## Scope and evidence rules

E implements packaging and installation maintenance through DeepSeek Harness.
The integration owner reviews E and owns F. The production checkout, global
runtime configuration, production shortcuts and uninstall registration must stay
unchanged. Tests use new explicitly named experimental directories and synthetic
data. Preserve all prior acceptance evidence.

Do not repeat the unchanged scientific suites. Reuse their recorded 5.3.0
evidence. Recheck native lifecycle only where the installer maintenance hook
changes it. Every result below must identify the actual built executable hash.

| Gate | Required evidence |
|---|---|
| Package | Strict experimental identity, validated input package, exact source/lock hashes, per-component size, Setup SHA256 |
| Boundaries | Foreign root/payload rejected; traversal and reparse paths rejected; unknown files and profiles retained |
| Maintenance | Authentication, bounded framing, request replay, startup exclusion, exact process identity, cancelled/failed drain leaves current version intact |
| Install | Interactive double-click on a second machine; bundled management Python; no preinstalled developer Rust/Node/Python required |
| Update | Stage candidate before exit; actual open workbench saves drafts and exits; new shortcut uses new version and same experimental profile |
| Lifecycle | Shortcut reopen, hide/show, explicit Quit; owned management tree exits; unrelated process survives |
| Desktop | Real selection -> agent read -> batch edit -> single undo; node drag/multi-select; language/theme persist; actual original-result links |
| Export | Existing RunPlan route exports through the Tauri UI; relocated standalone output runs without the source environment |
| Uninstall | Only experimental registration/shortcuts removed; profile and unknown files retained; no force-kill of scientific workers |
| Preservation | Before/after production file hashes and uninstall entries match |

An automated `--smoke-test` opens the real React workbench and exercises its ready,
draft-save and native shutdown handshake. It is not a substitute for double-click,
manual menu, picker, canvas or external viewer evidence. Do not label pending
interactions as passed because an API test passed. Server browsing requires an
available configured server; no paid server is started for this packaging task.

## Local probes

Before installation, run `scripts/acceptance/tauri_preservation.py --baseline
<new-baseline.json>`. After uninstall, use `--compare --baseline <same-file>
--report <comparison.json>`. The probe requires Windows registry access and fails
on inaccessible state; do not substitute an empty baseline.

For each installed native smoke sample, run
`scripts/acceptance/tauri_installed_smoke.py --host <installed-host.exe> --config
<installed-host.json> --evidence <new-directory>`. A timeout is a failure and keeps
the test window available for diagnosis. It never terminates processes by name.

## Status

The checklist above defines the gates. Results, exact commands, package location,
known gaps and evidence references will be recorded after the candidate is built
and reviewed. No publication or production promotion is authorized by this file.
