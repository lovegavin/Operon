# RC6: attempt-owned process cwd metadata recovery

RC5's worker finally block cleaned aliases on cooperative exit. A real
coordinator cancellation terminates the worker too, so that finally block cannot
run. Process containment was correct; a prepared junction journal remained.

RC6 creates a durable scope receipt before launching each RunPlan attempt.
Native and command workers inherit the attempt ID, fence and canonical root.
Long-cwd launches register metadata under a deterministic scope in the OS-known
local application-data directory; data, results and task TEMP remain in their
original partitions. Each launch still gets its own junction and journal.

The outer RunPlan executor reclaims only that attempt's scope after supervisor
generation containment proves the entire tree exited. Recovery uses the same
durable receipt after restart, not an in-memory PID list. No global directory
sweep, PID-only stale detection or recursive target deletion is used. Journal
identity, fence, canonical target spelling and exact reparse targets are checked before
metadata removal. A mismatch or uncertain stop retains metadata and records
recovery_required in the attempt's process-cwd-cleanup.json.

Unscoped RC5 journals cannot establish these stronger ownership guarantees and
remain diagnostic evidence. This repair does not silently sweep historical
aliases or alter scientific outputs. The process cleanup and scientific result
remain independently observable.

Targeted tests cover a real Windows Job Object forcibly killing a worker and
its child before the worker can clean up; fresh-observer recovery; idempotence;
wrong-fence and unconfirmed-stop refusal; tampered metadata and another active
scope preservation; and the RunPlan executor's containment-proof gate.

Local Windows validation: 14 process/scope checks passed using native Windows
permissions. The sandbox first rejected junction DeviceIoControl; those
environment-denied attempts are not counted as product regressions or passes.
No Windows host, installer, frontend or operator-library source was changed.
Actual RC6 packaged-runtime and test-machine acceptance are recorded separately.
