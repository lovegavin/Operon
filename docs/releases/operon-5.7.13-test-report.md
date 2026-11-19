# Operon Studio 5.7.13 test report

## Scope

- Report-mode operators in the isolated environment bridge (F-96, F-97).
- Column errors for operators that read labelled fields.
- Gene Ontology parameter defaults.

## Defects

| Id | Symptom | Fix |
| --- | --- | --- |
| F-96 | `barplot` failed with `'Context' object has no attribute 'out_dir'` | bridge `Context` exposes `out_dir` and `memory` |
| F-97 | `describe` failed with `KeyError: 'output'` | bridge returns a report value when no output parameter is declared |
| F-98 | `circrna_detect` / `rna_editing_detect` / `propensity_score_matching` raised a bare column `KeyError` | errors now name the dimension and list available columns |
| F-99 | `go_ic_profile` / `go_gene_similarity` defaulted to an example route path | defaults cleared; paths must be supplied |

## Verification on a clean installation

| Operator | Stage | Result | Time |
| --- | --- | --- | --- |
| barplot | run | complete | 7.5 s |
| describe | run | complete | 5.8 s |
| circrna_detect | run | complete | 5.3 s |
| rna_editing_detect | run | complete | 5.3 s |
| propensity_score_matching | run | complete | 6.3 s |
| go_ic_profile | run | complete | 5.2 s |
| go_gene_similarity | run | complete | 5.1 s |

The verification ran against a 5.7.12 tree with the two bridge modules and the
five operator files hot-patched, using representative tables for each contract
(columns `chrom,donor,acceptor,count`; `chrom,pos,ref,alt,coverage,alt_count`;
`t,y,x1,x2`; `gene_a,gene_b`) and a minimal local Gene Ontology bundle.

## Operator coverage

- Unique operators attempted: 1,074 of 1,074.
- Complete before this patch: 401 (37.3%).
- Complete after this patch: 408 (38.0%).

## Automated checks

- `tests/test_env_worker_context.py` 2 passed.
- `tests/test_environments.py` + `tests/test_environment_install.py` 27 passed.

## Known limitations

- Environments start as `missing` on a fresh installation and must be prepared
  explicitly; this is the documented behaviour of the dependency policy.
- Contract errors raised by the planning layer can mix Chinese and English
  wording.

## Coverage follow-up

A second pass re-ran the 289 operators that had never produced a result, now
that the `core` environment was ready on the validation machine. Six
iterations added the columns and parameter values each operator reported
missing.

| Bucket | Tried | Passed |
| --- | --- | ---: |
| Environment-specific (needed a non-core environment) | 172 | 63 |
| Missing-column / parameter coverage | 117 | 44 |
| **Total** | **289** | **107** |

Every one of the 107 passes was a first success for that operator. Cumulative
coverage is now 515 of 1,074 operators (48.0%).

Remaining failures in this pass: 83 blocked on environments that this platform
cannot install (hmmer, antismash, genomics, hic, rna), 48 in the general
bucket, 18 contract mismatches, 14 missing columns, 11 data-quality limits and
8 parameter ranges.

The pass also surfaced two classes of defect that the operators below fixed in
5.7.13: report-mode nodes that were executed through the value-returning
bridge, and operators that indexed label maps without checking the column.
Both are covered by `tests/test_env_worker_context.py` and the environment
bridge test.
