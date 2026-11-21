# Operon Studio 5.7.24 — test report

Scope: acceptance of the runtime, environment and planning fixes in 5.7.24 on a
freshly installed Windows instance driving a cleared Linux server (`licai-srv`).

## Environment

- Fresh install: `D:\OperonAccept`, Windows 11, port 5880, Edge attached over
  CDP 9421 for every UI step (text-only inspection, no screenshots).
- Server: `/public/home/lihj/Operon`, deployment `code-bcc7a49df0379aba3e45`,
  build `08e83cae3f86`, library `main-v1.1.14` (7 packages, 1182 descriptors,
  1074 operators), Python 3.11 from the managed micromamba prefix.
- **19 of 19 environments ready**, installed from the panel: `alphafold2`,
  `antifold`, `antismash`, `boltz`, `colabfold`, `core`, `dssp`, `esm2`, `esm3`,
  `esmfold`, `genomics`, `hic`, `hmmer`, `ligandmpnn`, `openfold`, `openmm81`,
  `proteinmpnn`, `rfdiffusion`, `rna`.
- Resources: 17 declared resources are linked or downloaded, 0 missing files
  (`afdb` 18/18); `prodigal/prodigal` is the only unit a fresh download cannot
  produce because upstream builds it with `make`, and the panel says so.

### Environment declarations

`core` imports were probed one by one in the server environment after the
reinstall:

| module | before | after |
| --- | --- | --- |
| `pyarrow` | missing | OK |
| `pysam` | `ImportError: libdeflate.so.0` | OK (`libdeflate>=1.19` from conda) |
| `pyBigWig` | missing | OK |
| `bed_reader` | missing | OK |
| `bgen_reader` | `AttributeError: module 'coverage' has no attribute 'types'` | OK (`coverage>=7.4` from PyPI) |
| `pgenlib` | missing | OK |
| `scanpy`, `umap` | `coverage` failure through `numba` | OK |
| `torch`, `transformers` | missing | OK (CPU wheel index) |
| `vina` | missing | still missing: the sdist needs a compiler the host lacks, declared best-effort |

`optional_missing` for `core` now lists only `vina==1.2.5`, and the panel offers
"补装可选依赖" on the ready environment instead of a dead card.

## UI route

`CsvReader(rt/data/iris.csv) → PCA` was composed in the canvas and executed from
the run button:

- prepare reached `ready` (`phase=server:code`), the fixed plan ran one unit,
  `native-chain · #1` completed with exit 0;
- the step produced 150 observations and two components, explained variance
  `[0.7470533000277259, 0.1843525688793199]`;
- the artifact was committed (`state=committed`).

After the rebuild, the panel was driven again: `openmm81` prepared from its card
(`missing → installing → ready`), `core` showed the optional-binding action, and
the last environment reached ready without touching an API directly.

## Operator routes over real files

Fourteen readers were exercised against real formats under `workspace/p6/fmt`
(PDB, FASTA, FASTQ, VCF, GFF3, BED, BIOM, SBML, BAM, Newick, Matrix Market, CSV):

| operator | reader | result |
| --- | --- | --- |
| `cox_regression` | CsvReader (`clinical.csv`) | complete, 66 s |
| `fastq_adapter_scan` | FastqReader | complete, 39 s |
| `annotation_gaps` | Gff3Reader | complete, 83 s |
| `coding_variant_filter` | VcfFileReader (`gwas_with_samples.vcf`) | complete, 50 s |
| `interval_annotate` | BedReader | complete, 32 s |
| `nestedness` | BiomReader (`otu_table.biom`) | complete, 24 s |
| `adjusted_rand_index` | two CsvReaders (`cluster_labels.csv`) | complete, 78 s |
| `isotonic` | CsvReader (`regression_sorted.csv`) | complete, 82 s |

`fst_outlier_scan` and `fba_flux_distribution` complete once the fixtures carry
the fields the operators read (allele counts per variant, SBML L3V1 with FBC v2).
`esm_if_design` needs `pydantic` in `esm2`, and `amrfinder_plus` needs the
`amrfinder` binary; both are recorded as environment or tool gaps.

The format sweep covers 687 cases across 14 readers. The first batch
(`fmt01.csv`, 192 rows) is 31 complete / 33 failed / 11 submit-failed /
117 environment-unavailable; the unavailable rows were produced while the server
was being upgraded, which the automatic reconnect now prevents, and they are
being re-run.

## State and reconnect

- A desktop window and an agent instance write the same `remote/profiles.json`.
  Saving now unions the job table, so a restart keeps history: `/api/v1/jobs`
  returned 391 records after the last restart instead of 1.
- With the desktop in the "not connected" state, submitting a graph aimed at the
  key profile returned **202** and completed in 28 s
  (`exec-e7c4ab4b684b4e12a16b139673e45b06`), and `/api/remote` then reported
  `connected: true` — the planner reconnects the profile it was told to use.
- A one-slot workflow that used to fail with "the unit minimum exceeds the frozen
  pool ceiling" now runs: the admission reserve is no longer subtracted twice.

## Automated tests

- `pytest tests/test_environment_install.py tests/test_environment_declarations.py`
  → 27 passed.
- `pytest tests/test_remote_state_merge.py tests/test_remote_environments.py
  tests/test_remote_handshake.py` → 44 passed.
- `pytest tests/test_pool_ceiling.py tests/test_engine_pool.py` → 9 passed;
  the wider admission set → 29 passed, 1 pre-existing failure caused by a
  missing worker in this machine's environment.
- `pytest tests/test_execution_ensure.py` → 4 passed;
  `pytest tests/test_remote_reconnect.py` → 2 passed.
- `vitest run` in `frontend` → 44 files, 287 tests passed.

## Known limitations

- Operator coverage is still partial: the 687 format cases plus the classic
  routes have exercised a few hundred of the 1074 operators. Every failure is
  classified as fixture premise, environment/tool gap, product defect, or
  offline-unavailable, and the product defects found this way are fixed in this
  release.
- `vina` cannot be installed from source on this host; the binding is declared
  best-effort and the operator reports the missing module.
- The `prodigal` resource unit is undownloadable by design (upstream `make`).
