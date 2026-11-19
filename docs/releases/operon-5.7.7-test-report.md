# Operon Studio 5.7.7 test report

## Scope

This release is a data and plumbing fix, not an operator change:

- resource downloads honour a list of mirrors instead of a single URL;
- the AlphaFold 2 database names follow the official 2.3.x flag defaults;
- `openfold` and `boltz` declare two mirrors each;
- the `alphafold2` unit file list matches `expected_files`.

Everything below was exercised on a clean Windows installation plus the Linux
test host described in the environment matrix of the 5.7.6 report.

## Builds

| Artifact | Size (bytes) |
| --- | --- |
| `Operon-Studio-v5.7.7-Windows-x64.zip` | 357,604,200 |
| `Operon_Setup-5.7.7.exe` | see `SHA256SUMS-5.7.7.txt` |
| `Operon-5.7.7-Server.zip` | see `SHA256SUMS-5.7.7.txt` |
| `operon_studio-5.7.7-py3-none-any.whl` | 1,001,926 |
| `operon_builtin_library-1.1.5-py3-none-any.whl` | 5,774,880 |
| `operon-library-main-v1.1.5.operon-library.zip` | 6,997,968 |
| route bundle | see `SHA256SUMS-5.7.7.txt` |

Payload: 25,641 files, sha256 `2a6eb5082b3cdb3da41523db541d1ee5990b032f7fd740b0f1f855743bb2270f`
for the first build. The shipped artifact is the one listed in
`SHA256SUMS-5.7.7.txt` next to this report; the report does not embed its own
payload hash because editing the report changes that hash.

## Manifest checks

`GET /api/resources` on the installed build reports:

- `alphafold2` expected files include `mgnify/mgy_clusters_2022_05.fa` and
  `pdb_seqres/pdb_seqres_2022_09_28.fasta`, and no entry still names
  `mgy_clusters.fa` or `pdb_seqres.txt`;
- `openfold` exposes one download with two candidate URLs;
- `boltz` exposes two downloads (`ccd.pkl`, `boltz1_conf.ckpt`) with two
  candidate URLs each;
- every other resource keeps its previous single-URL downloads.

## Download behaviour

`tests/test_resource_fetch.py::test_manifest_accepts_mirror_lists` and
`::test_manifest_accepts_mapping_downloads` cover the parser. The download loop
was exercised against a deliberately unreachable first mirror and a working
second mirror; the file was written once, the `.part` file was removed between
attempts, and the reported failure text lists each URL with its reason when all
mirrors fail.

## Automated checks

| Suite | Result |
| --- | --- |
| `tests/test_resource_fetch.py`, `tests/test_resource_api.py` | 24 passed |
| `tests/test_resource_fetch.py`, `tests/test_resource_link.py`, `tests/test_resource_api.py` | 51 passed, 1 skipped |
| frontend unit tests | 43 files / 265 tests passed |
| backend environment/resource/remote/control suites | reused from 5.7.6 (unchanged code paths) |

## Known limitations

- `pdb_mmcif` still has no HTTP archive: RCSB publishes it over rsync only, and
  the manifest now says so instead of offering a broken download.
- `openfold` and `boltz` depend on the Hugging Face mirror. When both mirrors
  are unreachable the UI reports the two URLs and their errors; ModelScope and
  Kaggle alternatives are documented in the manifest notes but not automated.
- The `uniref30` unit downloads the 2023-02 release (`uniref30_2302.db`), which
  differs from the 2021-03 snapshot named by the upstream AlphaFold script.
  `run_alphafold.py` accepts the path through `--uniref30_database_path`; the
  manifest notes record the difference.

## Not tested

- Two consecutive real mirror failovers against upstream services (only a local
  unreachable mirror plus a working one was exercised to keep the test quick).
- Re-downloading the full AlphaFold 2 database set; the names are validated from
  the manifest and the control API, not by transferring 2.7 TB.
