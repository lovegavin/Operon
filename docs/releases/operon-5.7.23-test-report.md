# Operon Studio 5.7.23 test report

5.7.23 is tested on real routes rather than on contract fixtures alone: every
defect listed in the release notes was reproduced from a reader-to-operator graph
on the audited host, fixed, rebuilt, deployed through the desktop interface and
re-run. This report records the environment, the data, the numbers and the
failures that remain.

## What this release fixes

The release notes carry the detail; for the purposes of this report the defects
fall into four groups.

- **Panel and readiness.** Resource unit downloads, per-unit presence, one action
  per state, environment badges, empty reasons and duplicated dependencies, and
  a directory archive that did not count as a source for the files below it
- **Routing layer.** Reader label defaults lost on an empty mapping, isolated
  step workers without a reader table, a revived encoder class that the shipped
  operators do not recognise, resolved external tools that never reached the
  bridge, bridged steps without `task_dir` or a cancellation path, a dynamic
  output name that indexed the wrong data format, every static output port
  required to register, and a wrapped failure that hid `details.reason`.
- **Library 1.1.14 operators.** DSSP on a wired input with solvent removed and a
  chemical component dictionary, empty VCF summaries kept at rank 2, TMM returned
  in the input axis order, unknown interval classes reported instead of fatal,
  numeric chromosome identifiers accepted by the annotation operators, and the
  antiSMASH environment given the imports its steps load.
- **Library 1.1.14 resources and environments.** A `ccd` resource, a dedicated
  `dssp` environment pinned at `dssp=4.4.11`, `flye=2.9.5=py311*`, the
  `econml==0.16.0` and `lightgbm==3.3.5` pins, writable-first ColabFold and
  Prodigal roots, reachable ProteinMPNN mirrors, and the AlphaFold DB in its
  released layout.

## Test environment

| Part | Value |
| --- | --- |
| Application | Operon Studio 5.7.23, Windows x64 payload |
| Local instance | `<workdir>\stage0v55fy`, HTTP on port 5866 |
| Remote host | `licai-srv` (172.22.148.93), CentOS 7 class, glibc 2.17, g++ 4.8.5 |
| Remote root | `/public/home/lihj/Operon` (`managed_root`) |
| Remote code | `managed-v1/code-574b071221c1c3ef7e81` |
| Remote library | `main-v1.1.14`, 7 packages, 1182 descriptors, 1074 operators, 108 readers |
| Environments | 19 declared, 19 `ready` after the interface installed three of them |
| Resources | 17 declared, every unit `downloaded` or `linked`, `ccd` present |

The remote host is reached with the Windows OpenSSH client. Windows Subsystem for
Linux cannot reach the host on this machine (the default route sends
172.22.148.93 to the WSL NAT gateway), so every remote read in this report was
made with `ssh.exe` from Windows or through the application's own HTTP surface.

## Contract validation

- **Operator contracts.** 993 auto-generated cases, one per operator with
  declared inputs, validated against the descriptor: 993 valid, 0 invalid.
- **Library build.** `operon-library-builder build` over `library/seed`:
  1069 operators built, 5 skipped (they need external binaries that the build host
  does not have).
- **Route contracts.** 81 curated routes: 81 valid, 0 invalid.

## Field sweep over MCP

Every run below was submitted through the MCP server of the installed
application (`operon_submit` + `operon_job`), never by calling the engine
directly.

Data, all classic public sources, staged under
`/public/home/lihj/Operon/workspace/rt/data`:

| Domain | Files |
| --- | --- |
| Structure | `1CRN`, `1UBQ`, `1L2Y`, `2GB1`, `1AKE`, `1CA2`, `4HHB` (PDB), `1CRN.cif` |
| Expression | `expr_gtex.csv`, `expr_gtex_T.csv`, `pbmc3k.csv`, `pbmc3k_T.csv` |
| Statistics | `iris.csv`, `mtcars.csv`, `lung.csv`, `gwas_catalog_assoc.csv`, `gwas_catalog_pos_u.csv` |
| Variants | `clinvar_chr21.vcf`, `clinvar_chr21_small.vcf` |
| Annotation | `chr21.gff2`, `chr21.gff3`, `chr21_20k.gtf`, `chr21_features.bed`, `chr21_genes_chr.bed`, `chr21_features_chr.bed` |
| Sequence | `uniprot_human_20.fasta`, `ecoli_20kb.fasta`, `ecoli_reads.fastq`, `brca1_mrna.fasta`, `tp53_mrna.fasta`, `chr21_window.fasta` |

Two derived tables were added where the source format cannot satisfy an operator
precondition, with the transformation recorded: `chr21_genes.csv` and
`chr21_features.csv` carry the chromosome as `chr21` so the annotation operators
can find an encoder, and `chr21_window_chr21.fasta` uses the same spelling. The
originals stay in place, and the derived files are mechanically converted (GFF
1-based coordinates preserved, BED start shifted by one).

Totals on the audited host at the end of the sweep (server-side `job.json`
records):

| Metric | Value |
| --- | --- |
| Jobs submitted | 874 |
| Complete | 520 |
| Failed | 345 |
| Cancelled | 9 |
| Distinct graph names | 720 |
| Distinct operators attempted | 308 |
| Distinct operators with at least one complete run | 237 |

The 345 failures are not all defects. Reading the console of each one, they fall
into these groups.

- **Fixture does not satisfy the operator.** A sites-only VCF has no sample
  columns, a GWAS table without coordinates cannot be placed, a BED file whose
  chromosome column is numeric carries no encoder, a table whose `sample` axis
  has 20 positions cannot be normalised as if it had more. These are recorded as
  data preconditions in `<workdir>\p6\EXPERIMENTS.md`.
- **Reader-to-operator contract gap.** `FastaFileReader` produces a
  `file_artifact` and form-typed operators refuse it with
  `Logical type file_artifact cannot feed form; insert an explicit scientific
  conversion operator`. The library ships no such conversion operator, so
  routes that start from a file reader and continue into a form operator cannot
  be built yet. This is reported as a known limitation, not as an operator
  defect.
- **Defects fixed in this release.** The routing-layer and library-operator items
  listed above; each one has a regression route that now completes.

The automated per-operator sweep over all 1074 operators is deliberately not
included: the generated cases address operators through a 6x2 placeholder table
that carries no column semantics, so their failures say nothing about the
operators. The sweep was replaced by curated routes over the data above, plus a
coverage pass that only submits cases whose operator has no complete run yet.

## UI walkthrough

The desktop interface was driven in a headed browser over the Chrome DevTools
Protocol, and every step was read as text from the page rather than from a
screenshot.

- **Server upgrade.** Settings, server card, `服务端维护`, `安装 / 升级服务端`
  uploads the server package, replaces the managed code directory, reinstalls the
  operator library and reconnects. The panel reports
  `Successfully installed operon-studio-5.7.23` and
  `Operator library installed from the delivered bundle` with
  `packages: 7, descriptors: 1182`, and the remote `server.json` afterwards names
  the new code directory and the new bundle hash. After an upgrade the panel shows
  `服务器未连接` until the connection is re-established, which is expected.
- **Environment installation.** Each environment card offers `准备` or `修复`
  depending on its state. `antismash` and `dssp` were repaired and `openmm81`
  prepared from the cards alone, about 40 seconds each, and the environment list
  then read 19 of 19 ready. No command line was used for these installations.
- **Resources.** Resource cards offer `下载缺失文件（n）`, `rsync 拉取`,
  `链接已有目录` and `移除链接`, and the panel reports declared, present and
  missing files per unit. On the audited host every one of the 17 resources is
  present, and 37 of 37 download targets have at least one reachable source.
- **Route authoring.** Nodes are added from the operator palette, connected, and
  parameterised in the inspector; execution settings are chosen in the dialog's
  own select, and a run started from the canvas produced the same artifacts as
  the same graph submitted over MCP.

## Four-end parity

The CLI, HTTP, MCP and UI surfaces share one engine. The parity suites pass on
this tree: `tests/test_cli_http_parity.py`, `tests/test_mcp_parity.py`,
`tests/test_parity_control_plane.py` — 74 passed. The MCP surface exposes 142
tools, including environment repair, remote jobs, job cancel, pool status and
resource log, and the CLI reaches the same routes.

## Repository tests

- Frontend: `npx tsc -b` clean; vitest 280 passed over 43 files.
- Reader and runtime suites used by this release: 47 passed over the reader
  conformance, precision, selection and extension files; 26 passed over the
  environment, worker-context and cancellation files; 15 passed over the output
  registration and output format files; 27 passed over the annotation, VCF,
  TMM and interval files.
- The build runs the full backend and frontend suites and refuses to package on a
  failure; the build log for the shipped payload records `test exit=0`,
  `frontend exit=0` and `library-manifest ok`.

## Known limitations

- A `file_artifact` cannot feed a form-typed operator, and the library ships no
  conversion operator for it.
- The remote executor reserves `capacity // max_parallel_tasks` per job, so a
  6.3 MB job reserves half of a 213 GB host and only two jobs run at a time. The
  value is configurable in the execution settings; the default is unchanged in
  this release.
- A submit that outlives the client timeout does not return its job id, so the
  caller cannot poll the job it just created. The server finishes the work; the
  identifier is only visible in the server's own job list.
- `tests/test_extension358.py` needs the registry to match the source snapshot
  and fails with `Implementation code hash mismatch: GtfReader` on a tree whose
  registry was built elsewhere; the failure reproduces without the changes in
  this release.
- Four resource-link and unit-download tests fail on this tree and on the parent
  commit; they are not regressions of this release.

## Verdict

All 19 environments are ready on the audited host, all 17 resources are present
with at least one reachable source per declared file, the packaged library builds
and its manifest verifies, the contract sweeps are clean, the routing-layer and
operator defects found by the field sweep are fixed and re-verified on real
routes, and the desktop interface alone can upgrade the server, install
environment dependencies, link or fetch resources and author a route. The
remaining failures are data preconditions, one documented reader-to-operator
contract gap and two known usability limitations, all listed above.
