# Operon for maintainers

You cut the releases, keep the registry honest and decide what the tree is
allowed to contain. The facts below are the ones that decide those calls.

## Two release lines, one tree

| Thing | Version | Tag | Bumped when |
| --- | --- | --- | --- |
| Application | `pyproject.toml` `version` | `v<X.Y.Z>` | application code, API, UI, packaging |
| Operator library | `library/release.json` `version` | `library-v<X.Y.Z>` | operators, Readers, routes, contracts |

`library/release.json` also carries `minimum_application` and
`build_application`, so a library release states which application can load it.
`main` integrates both lines; published tags and installers are immutable, and a
release is cut from a clean commit, not from a working tree.

An application release records the library sources it shipped:
[backend_versioning.md](../backend_versioning.md),
[library_releases.md](../library_releases.md),
[library_release_standard.md](../library_release_standard.md).

## Release checklist

1. Library change: rebuild the registry and its generated docs.

   ```bash
   python -m operon registry check
   python -m operon registry build
   python scripts/build_operator_docs.py
   ```

2. Application change: `cd frontend && npm ci && npm run build`, then run the
   focused tests and the integration tests the change touches.
3. Write the release note in `docs/releases/` (`operon-X.Y.Z.md`,
   `library-vX.Y.Z.md`, with the matching `-test-report.md`) and update
   `docs/releases/README.md`.
4. Package: the candidate scripts consume `docs/OPERON_3_TEST_ACCEPTANCE.md` and
   `docs/OPERON_3_TEST_INSTRUCTIONS_ZH.md` — they are inputs, not history; keep
   them.
5. Install, upgrade and uninstall once on Windows and once on a server before
   tagging. The installer and the server ZIP are separate artifacts.

## Verification pages

`docs/verification/` holds the evidence that survives: the five-layer standard
and the audits that still describe this line. Every page states the tree, the
date and what was counted; a count without those three is not evidence, and an
old audit is not a current claim. See
[verification/README.md](../verification/README.md).

## Architecture notes worth reading before a refactor

- [design/README.md](../design/README.md) — the index; a note's own status line
  ("proposal, not delivered") outranks any summary.
- [design/engine_locking.md](../design/engine_locking.md) — normative lock order.
- [design/port_contract_inventory.md](../design/port_contract_inventory.md) —
  why the port rule exists and what it froze.
- [design/library-application-split.md](../design/library-application-split.md) —
  the proposed split that replaced the library 8.x plan.
- [application_library_boundary.md](../application_library_boundary.md) — the
  boundary rule that is enforced today.

Known structural debts, each with a location: the scheduler is chosen by the
testing flag (`src/web/service.py:132`), execution has two paths rather than one
polymorphic one (`src/web/execution.py:99`, `operon/bridge.py:403-442`), `operon/`
imports `src.web` in 117 places with four name collisions, and 84 modules sit
flat at the package root. Treat these as decisions with a cost, not as free
cleanup: the fallback in `bridge.py` exists for services that predate the
application facade.

## When a server misbehaves

[SERVER_INSTALL_REPAIR.md](../SERVER_INSTALL_REPAIR.md) covers a mismatched or
broken server install, [design/remote_recovery_incident.md](../design/remote_recovery_incident.md)
is the post-mortem that produced the recovery paths, and
[agent_environment_repair.md](../agent_environment_repair.md) is the operator
environment equivalent.
