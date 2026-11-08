# Three-end verification audit — library 7.0.1 (Studio 3.1.4)

Scope: every operator added after `library-v5.0.2` (867 -> 1063, 196 operators)
must have a WSL route run, a Windows cross-check (PASS or SKIP with a reason)
and an srv result (PASS or SKIP with a reason) recorded in
`docs/verification/routes-5.x.md`.

## Method

- Added ids: `git show library-v5.0.2:library/seed/operator_index.json` vs the
  current index (196 added, 0 removed).
- Batch mapping: `workdir/b*_route/*parameters.json` step names, then
  `workdir/plan_134.tsv`, then the batch number in the commit that added the file.
- Evidence flags: the `##` section whose heading carries the batch token;
  `_b67` is a `###` subsection of a larger section.
- Counts below include the batch's operators only; routes with shared steps
  are listed once.

## Result

- Operators mapped: **196 / 196**
- Batch sections audited: **50**
- Missing WSL, Windows, or srv/SKIP evidence: **0**

| Batch | Operators | WSL | Windows | srv / SKIP | Export checks |
| --- | --- | --- | --- | --- | --- |
| b49 | 5 | PASS | PASS | recorded | md5/export |
| b50 | 5 | PASS | PASS | recorded | md5/export |
| b51 | 5 | PASS | PASS | recorded | md5/export |
| b52 | 5 | PASS | PASS | recorded | md5/export |
| b53 | 4 | PASS | PASS | recorded | md5/export |
| b54 | 3 | PASS | PASS | recorded | md5/export |
| b55 | 5 | PASS | PASS | recorded | md5/export |
| b56 | 5 | PASS | PASS | recorded | md5/export |
| b57 | 2 | PASS | PASS | recorded | md5/export |
| b58 | 6 | PASS | PASS | recorded | md5/export |
| b59 | 5 | PASS | PASS | recorded | values |
| b60 | 4 | PASS | PASS | recorded | md5/export |
| b61 | 5 | PASS | PASS | recorded | values |
| b62 | 7 | PASS | PASS | recorded | md5/export |
| b62b | 2 | PASS | PASS | recorded | md5/export |
| b63 | 5 | PASS | PASS | recorded | md5/export |
| b64 | 5 | PASS | PASS | recorded | md5/export |
| b65 | 3 | PASS | PASS | recorded | md5/export |
| b65b | 3 | PASS | PASS | recorded | md5/export |
| b66 | 4 | PASS | PASS | recorded | md5/export |
| b67 | 3 | PASS | PASS | recorded | md5/export |
| b68 | 6 | PASS | PASS | recorded | values |
| b69 | 4 | PASS | PASS | recorded | md5/export |
| b70 | 5 | PASS | PASS | recorded | md5/export |
| b71 | 5 | PASS | PASS | recorded | md5/export |
| b72 | 3 | PASS | PASS | recorded | md5/export |
| b72c | 3 | PASS | PASS | recorded | md5/export |
| b73 | 5 | PASS | PASS | recorded | md5/export |
| b75 | 9 | PASS | PASS | recorded | md5/export |
| b76 | 3 | PASS | PASS | recorded | md5/export |
| b77 | 3 | PASS | PASS | recorded | md5/export |
| b78 | 2 | PASS | PASS | recorded | md5/export |
| b79 | 3 | PASS | PASS | recorded | md5/export |
| b80 | 2 | PASS | PASS | recorded | md5/export |
| b81 | 3 | PASS | PASS | recorded | md5/export |
| b82 | 5 | PASS | PASS | recorded | md5/export |
| b83 | 4 | PASS | PASS | recorded | md5/export |
| b84 | 5 | PASS | PASS | recorded | md5/export |
| b85 | 3 | PASS | PASS | recorded | md5/export |
| b86 | 3 | PASS | PASS | recorded | md5/export |
| b87 | 3 | PASS | PASS | recorded | md5/export |
| b88 | 3 | PASS | PASS | recorded | md5/export |
| b89 | 3 | PASS | PASS | recorded | md5/export |
| b90 | 3 | PASS | PASS | recorded | md5/export |
| b91 | 3 | PASS | PASS | recorded | md5/export |
| b92 | 3 | PASS | PASS | recorded | md5/export |
| b93 | 3 | PASS | PASS | recorded | md5/export |
| b94 | 2 | PASS | PASS | recorded | md5/export |
| b95 | 3 | PASS | PASS | recorded | md5/export |
| final | 3 | PASS | PASS | recorded | md5/export |

All 196 operators fall under a section that records a WSL run, a Windows run,
and an srv result or an explicit SKIP. The dominant srv SKIP reason is that
`ssh srv` did not resolve and `/public/home/lihj` was not mounted on the WSL
host; the srv work that did run (for example b92/b93 and the 6.0.0
re-verification) is recorded separately in the same document.

## Studio 3.1.4 compatibility

- Clean Python 3.11 environment with the released Studio 3.1.4 wheel and the
  `Operon-Library-v7.0.1-Linux.operon-library.zip` bundle.
- Catalog: 1063 operators, 108 readers, 1171 descriptors, 7 packages.
- Documentation cache: 1171 documents verified, 0 failures.
- Routes: 78/78 bundles contain exactly `graph.json`, `parameters.json` and
  `execution.json`; all import through `src.web.parameters.import_bundle`;
  every node parameter object validates against its descriptor schema after
  ignoring the engine-owned `output` parameter that some schemas omit.
- Descriptor `outputs` may be empty because ports are declared in contracts;
  schema checks must use contracts, not a naive outputs key.

## Package import rules (Studio 3.1.4)

Operator library (`POST /api/plugins/install`):

- Accepted filenames: `.whl`, `.operon-library.zip`, `.biopipe-library.zip`.
- Archive: `library.json` plus exactly the files listed in its `files` map;
  no absolute paths, `..`, drive letters, backslashes or symlinks.
- `library.json` must be `format: operon.library`, `protocol_version: 3`; the
  installed application version must be at least `minimum_application`.
- Every listed file is checksummed before installation; package names and
  wheel files must be unique; `sources/operon/builtin_packages.json` must
  match the packaged wheel list.
- Installation is transactional; a failed probe leaves the registry unchanged.

Routes (`graph.json` / `parameters.json` / `execution.json`):

- A route is imported as a single `.operon.zip` containing exactly those three
  files, one bundle at a time.
- CLI: `operon graph open <name>.operon.zip`.
- Source paths inside the graph are relative to the builtin route workspace;
  after import the user re-points them to local data.

## Reproduction

```bash
python -m operon registry build
python scripts/build_builtin_packages.py --refresh
python scripts/build_operator_docs.py --check
python scripts/package_routes.py --output /tmp/routes701
```
