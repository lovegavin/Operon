# Operon Studio 5.7.25 test report

## What this build changes

5.7.25 carries library **1.1.16**. The application code is identical to 5.7.24;
the library adds the inverse-folding declarations for `esm2` and the shared
`design_letters()` helper that reads a sampled ESM-IF design as residues.

## Defects found and fixed

| # | Symptom | Cause | Fix |
|---|---------|-------|-----|
| 1 | `esm_if_*` fail with `No module named 'pydantic'`, then `No module named 'torch_scatter'` | `esm.inverse_folding.gvp_modules` imports `torch_scatter` at load time and the model wrapper imports `pydantic`; neither was declared for `esm2` | `esm2` declares `pydantic==2.14.3` and the matching PyG `torch_scatter` wheel |
| 2 | `esm_if_masked_region_scan: the sampled design has length 50, expected 46` | `GVPTransformerModel.sample` joins dictionary tokens; a sampled `<EOS>` is five characters long | `design_letters()` splits tokens, maps specials to `X`, then checks the residue count |

## Evidence (deployment `code-9ce292db890c14acab61`, library `main-v1.1.16`)

| Route | Reader | Result |
|-------|--------|--------|
| `esm_if_masked_region_scan` (1CRN, window 6, seed 5) | `PdbReader` | complete 106.8 s (`exec-d205eb0d8927403889d84e3353cfde62`) |
| `esm_if_design` (1CRN) | `PdbReader` | complete 58.4 s (`exec-ff4189be0adb474ba28206516aff774f`) |
| `esm_if_position_entropy` (1CRN, 4 samples) | `PdbReader` | complete 42.8 s (`exec-d8dd7d7d3da1485a91d12204659b08a3`) |
| `esm_if_redesign` (1CRN, 2 samples) | `PdbReader` | complete 51.3 s (`exec-ad62921d995f455abba046e49de9acbd`) |
| `fba_flux_distribution` (`e_coli_core.xml`) | `SbmlFileReader` | complete 37.2 s (`exec-5b1604836ed3411c81b208bebd5fa131`) |
| `fba_flux_balance` (wide matrices) | `CsvReader` ×2 | complete 37.3 s (`exec-0517cf20ae8f476e9139a8f9231d36f0`) |
| `fba_flux_variability` (`e_coli_core.xml`) | `SbmlFileReader` | complete 36.9 s (`exec-1ceb87afec36424cbe799d4cd1f4b3b0`) |
| `fba_gene_knockout` (`e_coli_core.xml`) | `SbmlFileReader` | complete 30.7 s (`exec-355c8d41fc8b4231b0e03624b9236ff8`) |
| `interval_annotate` (two BED inputs) | `BedReader` ×2 | complete 36.6 s (`exec-cc7472905bfc418fba284c6bfed222d6`) |

Before the library fix the same masked-scan graph failed in 97.1 s
(`exec-82dcc238b870492b8dfc6445739a0f20`).

## Environment state

19 environments are declared. After a forced server upgrade they were 17 ready,
`esm2` stale (its declaration changed) and `openmm81` missing; both are
reinstalled from the runtime panel and the environment API and return to ready
with the new declarations. `core` keeps the optional bindings that have no
wheel for this platform (`vina`), which is reported per item instead of failing
the environment.

## Known limitations

- `vina` still has no cp311 wheel; it is a best-effort binding and reports its
  own failure without affecting the rest of `core`.
- `prodigal` is a `make` product and has no downloadable archive; the resource
  panel marks it as not downloadable and the linked directory stays usable.
- Databases that cannot be redistributed (for example the full AlphaFold DB or
  licensed FASTA references) are linked, not downloaded.

## Reproduction

```
python -m pytest tests/test_preparing_recovery.py tests/test_remote_state_merge.py \
    tests/test_execution_ensure.py tests/test_remote_reconnect.py -q
python -m operon registry build --scope routes   # 1074 operators, 108 readers, 79 routes, 0 errors
```

The route evidence above is produced through the MCP tools (`operon_submit`,
`operon_job`) against the deployment named in this report; every job id is the
server-side record under `workspace/.studio/jobs/<id>/job.json`.
