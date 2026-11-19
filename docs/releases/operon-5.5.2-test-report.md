# Operon Studio 5.5.2 test report

## Scope

Release 5.5.2 changes the large-resource link dialog and adds the
`environments` field to the large-resource API. This report covers the
packaged Windows release, the operator library it ships with, the desktop API
and the browser UI.

## Environment

| Item | Value |
| --- | --- |
| Release | Operon Studio 5.5.2 |
| Build | `5.5.2`; the installer names the version directory with the build hash it was compiled from |
| Operator library | `main-v0.1.29` |
| Install root | a disposable directory outside the source tree |
| Desktop API | `http://127.0.0.1:5771` |
| Installer | `Operon_Setup-5.5.2.exe --quiet --no-register` |
| Host | Windows, clean install per run |

## Artifacts

The four Windows artifacts are published with `SHA256SUMS-5.5.2.txt`; the
release page carries the same digests. The library bundle and route collection
are unchanged from 5.5.1 (`main-v0.1.29`), so their digests are the 5.5.1 ones.

## Phase 1 - install

A clean install of the packaged setup completed in about 20 s (20.3 s measured)
and created a version directory named `5.5.2-<build>`. The headless server
answered `/api/version` with:

```json
{"version": "5.5.2", "build": "<build>", "display": "5.5.2 (<build>)"}
```

## Phase 2 - large-resource API

`GET /api/v1/large-resources` returned 16 resources; 5 of them carry a
non-empty `environments` list and the union is
`antifold`, `boltz`, `colabfold`, `esmfold`, `openfold`. The remaining eleven
show an empty list because no operator declares an environment for them and no
installed environment shares their id.
Each entry keeps `link_roots`, `expected_files`, `used_by`, `status`,
`present`, `linked` and `size_bytes`, so the dialog can drive its choices from
the same payload the list view renders.

## Phase 3 - link dialog

Opening Settings -> Large resources -> "链接资源" on the installed build shows
four fields in this order:

1. `执行位置` - a single `本地` option. No server connection is configured on
   this host, so only the local option is present and the note about adding a
   server is shown.
2. `缺失的环境` - `全部环境`, `AntiFold antibody inverse folding（missing）`,
   `ColabFold (local runner)（missing）`, `ESMFold (fair-esm)（missing）` and
   `OpenFold (AlphaFold-2)（missing）`. Only environments that still have a
   linkable resource are offered, so `boltz` (already present) and the
   environments without a large resource are absent.
3. `缺失的权重或数据库` - the 14 resources that declare linkable roots and are
   not present yet; `esm2` and `boltz` are hidden because they are already
   present.
4. `目标绝对位置` - an input whose placeholder is the first allowed link root
   of the selected resource (`/home/<user>/operon-resources`).

Choosing an environment narrows field 3 to the missing linkable resources of
that environment (only `openfold`) and moves the selection to the first one. The dialog lists the allowed link roots, states that a link only affects
the machine that runs it, and closes through `取消`.

## Phase 4 - regression

| Suite | Command | Result |
| --- | --- | --- |
| Resource API and link control | `pytest tests/test_resource_api.py tests/test_resource_link_control_api.py tests/test_environment_api_runtime.py tests/test_bridge_remote_resources.py tests/test_environment_install.py tests/test_environment_queue.py` | 40 passed |
| Frontend | `npm test` | 43 files, 264 tests passed |

The added frontend suite is `src/LargeResources.test.tsx`; it covers
`missingEnvironments`, `linkCandidates` and the empty-list rendering. The
environment column comes from the API: a resource belongs to the environments of
the operators that mention it outside an import statement, and to the
environment that shares its name when one is installed.

## Defects

| Id | Symptom | Root cause | Fix |
| --- | --- | --- | --- |
| F-21 | The link dialog asked for a "link location" without saying whether that path belongs to this machine or to a remote host, could not target a specific missing environment or resource, and the list showed no environment for any resource. | The dialog was built from the resource list alone and the API had no environment dimension, so the operator had to know which resource belonged to which environment and which of the two selectors executed the link. | Large-resource entries now carry `environments` derived from the operator descriptors, and the dialog asks for the execution location, the missing environment, the missing weights or databases of that environment and the absolute path, in that order. |

No open defects from this round; the deferred items D-01 to D-03 recorded in the
5.5.1 report are unchanged.

## Not tested

- Linking through a real remote server profile: no server connection is
  configured on this host. The remote code paths are covered by
  `tests/test_remote_resources.py` and `tests/test_bridge_remote_resources.py`,
  and answer `404` with a clear message for an unknown profile.
- Installing a multi-gigabyte environment end to end, which is unchanged in
  this release.

## Verification commands

```text
Operon_Setup-5.5.2.exe --quiet --install-dir <stage> --no-register --result <evidence>\install-result.json
python api552.py      # writes <evidence>\api552.json
python ui552.py       # writes <evidence>\ui552.json and two screenshots
```
