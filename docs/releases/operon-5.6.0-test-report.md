# Operon Studio 5.6.0 — test report

Application 5.6.0 with operator library `main-v1.0.0`. The release turns the
runtime panel into an environment-first surface: every operator belongs to
exactly one environment, each environment lists the dependencies it needs and
the resources it consumes, and each resource is described by the official
unit(s) a user downloads or links.

## Scope

- Library model: `operon/environment_assignments.json` maps all 1,177
  operators to one of 18 environments; `registry build` stamps
  `resources.environment` on every descriptor and rejects unknown names.
- `environments.json` v2: 18 environments, each with a `resources` list.
- `resources.json` v2: 16 resources, each with `envs` and `units`; 26 official
  units in total (AlphaFold-2 contributes 9, RFdiffusion 3).
- Application: environment list with dependency and resource payloads, unit
  level link/unlink, disk-space preflight for installations and downloads,
  environment-first runtime panel, CLI/MCP parity.

## Builds

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `Operon-Studio-v5.6.0-Windows-x64.zip` | 357,317,039 | `d8a85ba33f681736db5266563c933c45645a5a17d57c25f7e569c5fff9eb7914` |
| `Operon_Setup-5.6.0.exe` | 429,094,394 | `ccb14ba68883bb2c65c49fa31b865d54027d6ec1572ecde8802fbc9f2ebce9ec` |
| `Operon-5.6.0-Server.zip` | 4,740,756 | `093e64179476d364ce11b039126ff48b0acac8f534a2531f163291d12f64e981` |
| `operon_studio-5.6.0-py3-none-any.whl` | 990,596 | `3843b413fc6007fab757d44d1681565f48ed090bf797d44f6a327b86ca399da9` |
| `operon-library-main-v1.0.0.operon-library.zip` | 6,949,271 | `c715ea2e2e2ce510b311e1f374cea3dcef3db414ba964009d91652871c7cc6cf` |
| `operon-routes-main-v1.0.0.zip` | 201,272 | `c393451ea098db644bfdf586f3624420c8db849b884f468c54d4e310a36d1b5d` |

## Clean-install verification

Installed from the setup executable into a fresh root and started headless.

| Check | Result |
| --- | --- |
| Installation time | 21.32 s |
| Installed version directory | `5.6.0-ec6789c26048` |
| `/api/version` | `5.6.0 (ec6789c2)` |
| `/api/libraries` | `main-v1.0.0`, 7 packages, 1,177 descriptors, 1,069 operators, 108 readers |
| `/api/environments` | 18 environments |
| Environment payload | `antifold` reports `resources: ["antifold"]`, 8 dependency rows, `shared: false`, `managed: true` |
| `/api/v1/large-resources` | 16 resources, 26 components |
| AlphaFold-2 units | 9 components, every one `missing` on a clean profile |
| Resource to environment tags | `proteinmpnn` to `esm3`/`proteinmpnn`, `esm2` to `esm2`/`proteinmpnn`, `pfam` to `hmmer`, `prodigal` to `antismash` |

## Interface parity

- CLI: `operon environment list`, `operon resources list` return JSON; the
  guard that rejected `list`/`install`/`cancel` for lack of a workflow file is
  fixed. `operon environment install <name>`, `... cancel <name>` and
  `operon resources download|link|unlink|cancel|log` share the service layer.
- MCP: `operon_environments_cancel` added; resource tools accept `unit`.
- HTTP: unit-level link and unlink, component state per resource, dependency
  and resource lists per environment.

## UI verification

- Runtime panel renders **18 environment cards** and nothing else; the resource
  section that used to be rendered first is gone from the landing view.
- Opening a card shows `环境依赖` (dependency rows with install/cancel) and
  `资源` scoped to that environment only.
- Resource cards list the official unit names with state chips and byte
  sizes (AlphaFold-2 units: 5.0 GB, 76.4 GB, 191.9 GB, 1.6 TB, 111.8 GB,
  52.2 GB, 259.8 GB, 271.7 MB, 214.2 GB), plus per-unit link controls.
- Frontend suite: 43 files, 266 tests passing; bundle `index-BLxvt6-r.js`.

## Automation

| Suite | Result |
| --- | --- |
| `tests/test_resource_link.py` | 59 passed, 1 skipped |
| Environment tests (4 files) | 27 passed |
| `tests/test_manifest_registry.py`, `tests/test_registry_maintenance.py` | 16 passed, 1 failed (same pre-existing failure on the 5.5.3 baseline) |

## Defects fixed

- **F-28** Stamping `resources.environment` changed the declaration digest
  without recomputing it, so runtime validation reported a declaration hash
  mismatch instead of the intended code hash message. `stamp_environments`
  now recomputes `declaration_sha` whenever the environment name changes.
- **F-29** `operon environment list|install|cancel` were blocked by a guard
  meant for `check`/`prepare`.
- **F-30** The runtime panel rendered the whole resource section before the
  environment cards, so the environment list was pushed off-screen.
- **F-31** Remote handshakes probed 15 external tools on every connection and
  reported a misleading availability fraction; probing is removed and the
  panel shows the reader and operator counts only.

## Known limitations

- `operon environment status <name>` still expects a workflow directory and
  reports a file-not-found error for a bare environment name.
- Disk-space preflight uses the estimated size for environments and the
  declared unit size (or `Content-Length`) for downloads; a download that
  grows beyond its declared size can still fill the disk.
- `alphafold2` declares no operators; its environment card exists so the
  parameter and MSA units can be linked before a runner is added.

## Not tested

- Full Windows installation on a machine without a developer toolchain.
- Remote (SSH) installs of the new environments end to end; only the API and
  transport paths were exercised.
