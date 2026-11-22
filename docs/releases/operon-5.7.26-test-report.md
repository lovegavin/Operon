# Operon Studio 5.7.26 — acceptance report

- Version: `5.7.26`
- Source commit: recorded in `package-manifest.json` of the payload
- Library: `main-v1.1.16` (7 packages, 1182 descriptors, 1074 operators, 79 routes)
- Host: `licai-srv` (`172.22.148.93`), managed Python 3.11 via micromamba

## What changed

One defect, found while repairing the `esm2` environment for the ESM-IF family:

| Symptom | Cause | Fix |
| --- | --- | --- |
| `esm2` stays `incomplete` with 1 pending dependency although `import torch_scatter` works | the declaration installs `torch_scatter` from a `data.pyg.org` wheel URL; the readiness table asked `_requirement_name()` for a project name and got the whole URL, so the row never matched `torch_scatter-2.1.2.dist-info` | read the project out of the wheel filename in `operon/environment_install.py` and `src/web/environment_api.py` (`2e73c6b7d`) |

## Evidence

- `pytest tests/test_wheel_requirement_name.py` → 3 passed (URL, local path,
  and the unchanged requirement forms).
- `esm2` reinstall on `licai-srv`: staging interpreter imports `biotite`, `esm`,
  `torch`, `torch_geometric`, `pydantic`, `torch_scatter`; environment log ends
  with `environment esm2 is ready`.
- Environment panel reaches 19/19 `ready` after the reinstall; `openmm81` needed
  only the missing `wheel` package, which the same panel install supplied.
- ESM-IF regression: `esm_if_masked_region_scan` on 1CRN chain A (seed 5)
  completes in 106.8 s — the `<EOS>` token defect fixed in `08f3e4a54` stays
  fixed on this build.

## Known limits

- `vina==1.2.5` has no cp311 wheel; it sits in `core.best_effort` and is the one
  optional binding that stays uninstalled.
- `prodigal/prodigal` is a `make` product and is reported as `undownloadable`.
- Offline-only databases (PDB mirrors, GTEx/BiGG downloads) are out of scope for
  the format sweep.

## Reproduce

```bash
python -m pytest tests/test_wheel_requirement_name.py -q
curl -s -X POST http://127.0.0.1:5880/api/remote/db125ae3be324023b9770b34c337ede7/environments/prepare \
  -H "x-studio-token: $TOKEN" -H 'content-type: application/json' \
  -d '{"names": ["esm2"], "force": true}'
```
