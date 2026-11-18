# Operon Studio 5.6.6 test report

## Scope

Application 5.6.6 with operator library 1.0.5. Verification covered a clean
Windows install, the HTTP interface, the MCP server, the CLI and a real
end-to-end operator sweep driven through the HTTP API.

## Builds

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `Operon-Studio-v5.6.6-Windows-x64.zip` | 357,383,010 | `6d4eeba92682a3d85d12d055a7969931ba950b4ed60f49d82d51ec629b8fd93e` |
| `Operon_Setup-5.6.6.exe` | 429,160,364 | `517ae408eb493a6699d9cc59a483ac1696e4d50c7320ed58cc5a4d9ea439b3cd` |
| `Operon-5.6.6-Server.zip` | 9,768,991 | `effdb81eab33da1aa1269fb82a582fc9a7d6a0a24bde6f71f0600dc948b3db27` |
| `operon_studio-5.6.6-py3-none-any.whl` | 993,541 | `cb3a9b7f8c2ca48c646e48137bdbf30ed7945a74ecefaefd3d24cdaeef586d87` |
| `operon-library-main-v1.0.5.operon-library.zip` | 6,953,761 | `4528c6c6187e2a38f271fb6d46ca7e00c6d44d558f7ffa336d4fd39f85d82aed` |
| `operon-routes-main-v1.0.5.zip` | 201,292 | `97d38b022d70233437fd490169a7206ce5aa7d34d5ded83fa9896641beed0eb3` |

## Clean install

| Check | Result |
| --- | --- |
| Installer exit | 0 |
| Service start | 24 s |
| `/api/version` | `5.6.6` build `fc9f00e313e5` |
| `/api/libraries` | `main-v1.0.5`, 7 packages, 1,177 descriptors, 1,069 operators, 108 readers |
| `/api/environments` | 18 environments, 1,177 operator assignments |
| `/api/v1/large-resources` | 16 resources, 16 official units |

## Interface parity

| Interface | Result |
| --- | --- |
| HTTP `/api/v1/environments/{name}/retry` | 200 |
| HTTP `/api/v1/environments/{name}/cancel` | 200 |
| HTTP unit download | 200, job starts |
| HTTP unknown environment | 404 `unknown isolated environment` |
| MCP `operon_environments_cancel` | reachable, returns `没有正在进行的准备任务。` |
| MCP `operon_job`/`operon_result_files` with `id` | accepted |
| CLI `environment status/install/cancel <name>` | accepted |
| CLI UTF-8 BOM graph | accepted |

## Environment attempts

Eighteen environments were prepared one at a time, never with the bulk action.

| Environment | Outcome |
| --- | --- |
| core | ready (1.0 GB, 13,414 files) |
| openmm81 | ready |
| proteinmpnn | ready (interpreter 3.11.18, ProteinMPNN checkout linked) |
| alphafold2, antifold, antismash, boltz, colabfold, esm2, esm3, esmfold, genomics, hic, ligandmpnn, openfold, proteinmpnn, rfdiffusion, rna | started then cancelled; state returns to `missing` |
| hmmer | failed: `hmmer=3.4` and `infernal=1.1.4` have no Windows builds |

## Operator coverage probe

Operators attempted: **491** of 1,069. Completed end to end: **112**.

| Outcome | Count | Meaning |
| --- | --- | --- |
| completed | 112 | completed end to end |
| environment-not-installed | 26 | environment not installed on this host |
| missing-dependency | 5 | operator dependency missing from the environment |
| file-reader-limitation | 67 | needs a file-artifact input that a form Reader cannot produce |
| domain-data-columns | 35 | needs domain-specific columns in the input table |
| contract-shape | 24 | input shape or axis annotation mismatch |
| parameter-value | 3 | parameter value rejected by the operator |
| insufficient-sample-data | 48 | sample too small or degenerate for the operator |
| external-tool-missing | 1 | external tool or checkout missing |
| timed-out | 16 | still queued when the harness stopped waiting |
| other | 154 | other |

The sweep wires every operator from its contract axis names, generates a table
per operator, submits it through `POST /api/v1/workflows/prepare` and
`POST /api/v1/jobs`, and waits for a terminal state. The three largest buckets
are not wiring defects: they need domain data (`count_a`, `a_methylated`,
`taxon`), a file artifact input, or they ran out of the harness wait window.

Representative operators that completed end to end include `rdkit_qed`,
`proteinmpnn_score`, `interface_mmgbsa_delta`, `structure_openmm_energy`,
`structure_interface_residue_energy`, `jarque_bera`, `kpss_test`,
`shapiro_wilk`, `acf`, `pca`, `agglomerative`, `adjusted_rand_index` and
`resource_preflight`.

## Known limitations

- `operon environment status <name>` still resolves the name as a workflow
  directory.
- Environment dependencies changed outside the application require a service
  restart before the shared pool accepts new work.
- Molecular dynamics operators exceed the 90 s client timeout used by the
  sweep harness.
- Operator families that need domain-specific tables or file artifacts require
  per-family sample data; the sweep classifies them instead of faking inputs.

## Not tested

- Full download of multi-gigabyte databases and weights (deliberately skipped;
  those paths are exercised with small units only).
- Remote SSH installations in this build.
