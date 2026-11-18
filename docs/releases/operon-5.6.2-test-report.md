# Operon Studio 5.6.2 test report

## Scope

Release 5.6.2 rebuilds the runtime view around environments and makes the
resource unit the thing that is downloaded or linked. The pieces under test:

- descriptor environment assignment produced by the library packager;
- environment listing with `operator_count` and declared dependencies;
- per-unit resource downloads and per-dependency installs;
- the card layout of the runtime window, environment detail, dependency list
  and resource units;
- the execution-location selector and the local/remote directory picker.

## Builds

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| Operon-Studio-v5.6.2-Windows-x64.zip | 357,349,906 | 1b908986a7906739d97af593b66e27fa79cb5f6946f43a5800b9d35cb568d9df |
| Operon_Setup-5.6.2.exe | 429,127,258 | 907493b0b308131469233f52352c3af98839608931fd18b6e500e0fddc97f5f2 |
| Operon-5.6.2-Server.zip | 4,751,042 | 97c85443d479e7ce9844dc8256af28114d2b347a69c1208b9dcffc431d33f9e2 |
| operon_studio-5.6.2-py3-none-any.whl | 992,674 | 56c3202256f7ab240ac10bf8046be9ae3d28ebd5feeb641c1561949ed241043b |
| operon-library-main-v1.0.2 | 6,949,024 | 3f2c672e13094ee66fede0256bc4707a2d3985ab5eedd162d70d776a02e52b1f |
| operon-routes-main-v1.0.2.zip | 201,279 | f0ce2def544407553de809a8302f4fa7a8ba757e0796a9bf187ea8af24545539 |

## Clean install

Installed with `Operon_Setup-5.6.2.exe --quiet --install-dir <root>
--no-register --result <file>` into an empty directory.

| Check | Result |
| --- | --- |
| Install time | 21 s |
| `/api/version` | `5.6.2 (a5901d99)` |
| `/api/libraries` | `main-v1.0.2`, 7 packages, 1,177 descriptors, 1,069 operators, 108 readers |
| Environments | 18 |
| `operator_count` total | 1,177 |
| Resources | 16 |
| Components | 16, one official unit per resource |
| `/api/browse` | local drive roots; 29 entries |

Environment assignment as shipped: core 1,094, proteinmpnn 26, esm2 11,
genomics 10, esm3 6, openmm81 6, ligandmpnn 4, antismash 3, boltz 3, hmmer 3,
rna 3, antifold 2, hic 2, colabfold 1, esmfold 1, openfold 1, rfdiffusion 1,
alphafold2 0.

## Interface parity

`POST /api/resources/{name}/download` accepts `unit` and only fetches the files
of that unit; `POST /api/environments/{name}/dependencies/download` installs one
declared dependency; `POST /api/browse` lists local directories. The same
operations exist for a connected server through the remote endpoints and the
agent actions, and through `operon resources`/`operon environment` on the CLI.

## User interface

Verified on the installed build with a headless browser:

- 18 environment cards, titles in Chinese, 1,094 operators shown for the shared
  runtime environment;
- one *install all* button in the top right, no *download all*, no *cancel*;
- execution-location selector present in the runtime summary;
- environment detail shows two entry cards (dependencies, resources);
- dependency cards and resource-unit cards reuse the environment card layout;
- link dialog opens a picker listing 29 entries (24 folders);
- no console errors and no error banners.

## Automation

- `pytest tests/test_resource_link.py tests/test_environment_install.py
  tests/test_environment_api.py` - 43 passed, 1 skipped.
- `pytest tests/test_manifest_registry.py tests/test_registry_maintenance.py`
  - 16 passed, 1 failed; the failure also fails on the previous release.
- `npm test -- --run` (frontend) - 43 files, 265 tests passed.
- `npm run build` - succeeds, bundle contains the `5.6.2` literal.

## Known limitations

- `operon environment status <name>` still resolves a workflow directory rather
  than an environment name; `list`, `install` and `cancel` work.
- The disk-space guard compares the estimate with free space, so a resource
  whose real size exceeds its estimate can still fail midway.
- The `alphafold2` environment has no operator yet; its card exists so the
  `afdb` unit can be linked before a runner is bundled.
- `POST /api/capabilities` is not mounted in this build and returns 404.

## Not tested

- Installing a full deep-learning environment through the UI (the download is
  hundreds of gigabytes).
- Linking a unit on a remote server from the desktop window against a live
  cluster beyond the directory browse call.
