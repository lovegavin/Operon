# Pending resource UI fixes (5.7.23 cycle)

These four defects were reproduced on three consecutive 5.7.23 builds
(`84d98f28`, `20d12c03`, `68ae4d8e`) with a headed browser against a clean
install. The fixes exist as an unapplied patch and are not part of any build
yet.

The combined patch covers 7 files (+276/-31), applied on a worktree based on
`60ae512d`. Backend tests: 49 passed. The patch is kept outside the repository
and must be handed to whoever builds the next release.

## 1. Download progress never reports progress

`src/web/resource_api.py` creates the download job without byte totals, so the
dialog can only show "downloading". Fix: expose `percent`, fall back to
`planned_bytes` from the unit's declared file sizes, and mark the job
`downloading` at creation.

## 2. Cancel is unreachable and leaves English text

`frontend/src/LargeResourceSection.tsx` registers the dialog action but no
cancel control, and renders the raw operation state. Fix: keep the download
button after cancel, map the terminal states to Chinese text, and stop polling
once terminal.

## 3. `shared` disagrees with `shared_resources_total`

`src/web/environment_api.py` reports `shared: true` together with
`shared_resources_total: 0` for `core`. Fix: count shared entries and derive
`shared` from that count.

## 4. Legacy AF2 file name is not recognised

`library/seed/src/task/step/steps/_resources_common.py` compares declared paths
literally, so an existing `pdb_seqres_2022_09_28.fasta` is reported missing and
downloaded again as `pdb_seqres.txt`. Fix: explicit alias table plus retained
file sizes.

## Verification recipe

Install a build to a scratch root, open the settings dialog, select
`alphafold2` -> `afdb`, and check: progress percentage appears within ten
seconds, cancel returns to a Chinese label with the button restored, `core`
reports consistent shared counts, and an existing legacy-named file is counted
as present.
