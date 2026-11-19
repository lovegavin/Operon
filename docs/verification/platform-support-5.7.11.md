# Windows availability of the bioconda environments

Five bundled environments are declared for Linux and macOS only because their
command line tools are not published for `win-64` by bioconda. The declaration
lives in `library/seed/operon/environments.json` as `"platforms": ["linux",
"darwin"]`; the Windows application therefore shows the environment as
`当前系统不支持`, blocks the prepare button, and records the reason in the
environment error file.

This note records the evidence collected on 2026-11-20 so the platform gate can
be reviewed without re-running the search.

## Method

```
micromamba search --platform win-64 -c conda-forge -c bioconda <package>
```

Binary: `library/environments/micromamba.exe` shipped with the Windows runtime
(micromamba 2.x, repodata fetched live from `conda.anaconda.org`).

## Packages that the five environments need

| Environment | Package | win-64 result |
| --- | --- | --- |
| hmmer | `hmmer` | `No entries matching "hmmer" found` |
| hmmer | `infernal` | `No entries matching "infernal" found` |
| antismash | `antismash` | `No entries matching "antismash" found` |
| rna | `viennarna` | `No entries matching "viennarna" found` |
| hic | `cooler` | `No entries matching "cooler" found` |
| genomics | `prodigal` | `No entries matching "prodigal" found` |
| genomics | `samtools` | `No entries matching "samtools" found` |
| genomics | `blast` | `No entries matching "blast" found` |

Every query above parses the `bioconda/win-64` flat repodata successfully
(`Using Flat Repodata for bioconda/win-64 ✔ Done`) and then returns an empty
match set, so the absence is a property of the channel, not of the local
network or of a stale index.

## Consequence on Windows

- The five environments stay `当前系统不支持` and never enter the prepare queue.
- The operators that belong to them remain visible and their contracts can be
  inspected, but running them reports the environment restriction instead of a
  confusing micromamba error.
- On Linux all five install from the same manifest; see the Linux matrix in
  `docs/releases/operon-5.7.11-test-report.md`.
