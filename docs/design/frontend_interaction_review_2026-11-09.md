# Interaction review: update lifecycle and workflow feedback

Date: 2026-11-09. Baseline: application branch `fix/3.0.1-installation`,
commit `b69f8859`, application 3.1.4. Library contents and scientific execution
are outside this change. This is a source-based interaction review; recommendations
are not claims that all flows have been manually tested or already changed.

## Implemented in this change

Windows Setup previously attempted to delete old versions after committing the
new receipt. A live desktop held the profile lock, so cleanup failed and was
only logged. Setup never asked that window to close. The detached pool could
also keep the old Python executable open after its window disappeared.

Setup now checks the old owned installation, requests normal desktop closure,
waits for owned processes to exit, and holds old profile locks across the commit.
The transition happens only after the new payload and runtime have been verified.
Unfinished tasks, an unverified window, or a refused/timed-out close preserve the
previous installation and permit retry. There is no global process-name kill.
See `installer/InstallUpgrade.cs`, `installer/InstallEngine.cs`, and
`tests/native_setup/UpgradeTests.cs`.

Further process-lifetime testing reproduced a second Windows defect: console
detachment did not remove the managed pool from the desktop's kill-on-close Job
Object. `biopipe/managed_pool.py` now requests explicit Job Object breakaway. The
regression test closes the real host Job Object while a second client has work,
then verifies the original pool and worker survive without restart and finish.
Setup additionally checks the owned pool's registered workspaces before closing
an older host that does not yet contain that lifecycle fix.

Focused evidence: 71 native installer checks, 15 pool/viewer lifecycle tests and
3 Setup wrapper tests passed. A private Setup candidate also updated a running
installed 3.1.4 desktop in an isolated directory in 42.14 seconds: normal draft
flush, backend exit 0, old executable removal and old profile preservation were
observed in logs/files. This package check preceded the additional shared-pool
guard/breakaway changes; those final changes have focused native/real-process
regression coverage. This is not a final release-package or full desktop acceptance.
The desktop UI capture could not reliably activate the test window, so the
frontend recommendations below remain code-review findings.

Scope: same managed installation directory. Other installations, portable
copies, and unrelated Python processes are intentionally not stopped. A legacy
desktop has no atomic prepare-update endpoint; its task metadata and bootstrap
are checked before normal window closure, and its existing close handler remains
responsible for changes occurring after that check. A future lifecycle handshake
should close task admission and flush drafts atomically before acknowledging
that a version is ready to be replaced.

## Prioritized follow-up

| Priority | Observed implementation | User impact | Proposed behavior |
| --- | --- | --- | --- |
| P0 | `desktop/Program.cs: ClosingStudio` warns that leaving stops tasks and only checks the bounded history for `running`; the shared pool intentionally keeps accepted tasks alive | The close dialog describes a different lifecycle from the default engine and misses queued/preparing states | Use a complete lifecycle summary. Distinguish leaving the editor from explicitly cancelling tasks. For an update, show the tasks/clients that prevent retirement |
| P1 | `frontend/src/ReadinessChecks.tsx` uses `JSON.stringify(graph)` for both dependency and preflight feedback | Moving a node or renaming the route hides a valid dependency result; this looks like rechecking is required even though backend dependency checks are cached | Separate dependency identity from execution identity and presentation state. Reuse the server's dependency identity; invalidate on host, operator, Reader or dependency changes, not layout |
| P1 | `frontend/src/App.tsx: validate` opens persistent execution settings, but `run` uses the generic transient error path | The same missing dependency has different recovery affordances depending on which button was pressed | A blocked Run opens the same readiness panel and explicit installation action as Check; keep scientific execution separate from installation permission |
| P1 | `frontend/src/RouteDialogs.tsx: Modal` applies `dismissDisabled` to the X button, but Escape and the backdrop call `onClose` directly | Callers must remember their own guards; a future caller can disappear during a mutation despite its disabled close button | Centralize the guard for X, Escape, backdrop and footer; distinguish dismissing a background view from cancelling an operation |
| P1 | `frontend/src/PluginPanel.tsx: operate` polls a running operation indefinitely, displaying one generic scan message and disabling dismissal | Slow imports look stuck; users cannot tell whether validation, copying or registration is progressing | Display a compact current phase, elapsed time and a detail/log action. Allow background observation when the backend supports it; offer cancellation only where cancellation is real |
| P1 | `frontend/src/SettingsPage.tsx` allows switching sections while `serverBusy` disables the entire dialog's close action | On the Appearance or Language page the disabled close button has no visible explanation | Keep a small ongoing-operation status across sections, with a link back to its owning section and its supported cancel action |
| P1 | `frontend/src/RemotePanel.tsx` replaces `profile` when choosing another server or Add, without preserving that server's draft | Unsaved connection fields disappear when switching server entries, although switching settings sections correctly preserves them | Keep drafts per server ID (credentials only in session memory), or ask only when discarding a changed draft |
| P2 | `frontend/src/TaskManager.tsx` displays queued status/progress; backend queue reasons are not surfaced in the task UI | Users cannot distinguish waiting for RAM/CPU, environment maintenance, or another pool client | Expose the specific waiting reason beside the queued status and link to resources; do not show an animated compute indicator for work that has not started |
| P2 | `frontend/src/App.tsx: stop` tracks one cancelling ID for all concurrent tasks | Overlapping stop requests can clear one another's busy indicator | Track cancellation state per task and keep each Stop action disabled until its own request settles |

## Implementation order and checks

1. Unify lifecycle/readiness feedback and modal dismissal rules. Cover Run versus
   Check, queued tasks on close, blocked upgrades, draft-save failure, and Escape.
2. Preserve dependency feedback through layout edits and preserve per-server
   drafts. Test host/operator edits still invalidate readiness correctly.
3. Add operation phases and queued reasons using existing backend state. Do not
   invent progress percentages. Test disconnect/reconnect and two overlapping
   cancellation requests.

Keep the current visual language, double-click inspector, middle-button pan,
selection/clipboard shortcuts and explicit fit-to-canvas behavior. These changes
should improve state visibility and recovery without adding permanent small-print
instructions or changing the user's established canvas interactions.
