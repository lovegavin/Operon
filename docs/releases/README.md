# Release notes

One note per release of the line the tree currently ships, plus the test report
that went with it. Notes are frozen: they describe what was released, not what
is true now.

This directory was pruned to the current line (5.9 onward). Anything older is in
the git history — the same text, reachable by tag.

## Application releases

| Version | Release note | Test report | What it did |
| --- | --- | --- | --- |
| 5.11.2 | [operon-5.11.2.md](operon-5.11.2.md) | [report](operon-5.11.2-test-report.md) | Structure exports keep polymer atoms only; library 2.1.3 metadata |
| 5.11.1 | [operon-5.11.1.md](operon-5.11.1.md) | [report](operon-5.11.1-test-report.md) | Accuracy fixes: structure rows, ColabFold multi-chain FASTA, RFdiffusion interpreter |
| 5.11.0 | [operon-5.11.0.md](operon-5.11.0.md) | [report](operon-5.11.0-test-report.md) | Slurm compute nodes: discover, rank and choose |
| 5.10.1 | [operon-5.10.1.md](operon-5.10.1.md) | [report](operon-5.10.1-test-report.md) | Declarative site-packages patches in environment definitions |
| 5.10.0 | [operon-5.10.0.md](operon-5.10.0.md) | [report](operon-5.10.0-test-report.md) | Compute-node inventory and capacity-aware placement |
| 5.9.5 | [operon-5.9.5.md](operon-5.9.5.md) | [report](operon-5.9.5-test-report.md) | Library version floor corrected |
| 5.9.4 | [operon-5.9.4.md](operon-5.9.4.md) | [report](operon-5.9.4-test-report.md) | Managed source archive carries the library |
| 5.9.3 | [operon-5.9.3.md](operon-5.9.3.md) | [report](operon-5.9.3-test-report.md) | Provider library install on managed servers |
| 5.9.2 | [operon-5.9.2.md](operon-5.9.2.md) | [report](operon-5.9.2-test-report.md) | A managed server works again after upgrade |
| 5.9.1 | [operon-5.9.1.md](operon-5.9.1.md) | [report](operon-5.9.1-test-report.md) | Remote provision retires the old server before replacing it |
| 5.9.0 | [operon-5.9.0.md](operon-5.9.0.md) | [report](operon-5.9.0-test-report.md) | Ports-only transport; 54 operators declare missing ports; library 2.0.0 |

## Library releases

The operator library ships independently of the application. Its bundle tags are
recorded here; the compatibility floor is declared in `library/release.json`, so
read `minimum_application` rather than the note's header text.

| Bundle | Note | Compatibility |
| --- | --- | --- |
| 2026.11.5.2 | [library-v2026.11.5.2.md](library-v2026.11.5.2.md) | declarative metadata update |
| 2026.11.5.1 | [library-v2026.11.5.1.md](library-v2026.11.5.1.md) | operator fixes on the 2026.11 line |
| 2026.11.5 | [library-v2026.11.5.md](library-v2026.11.5.md) | bundle release |
| 2026.11.4 | [library-v2026.11.4.md](library-v2026.11.4.md) | bundle release |

Library 2.x itself is recorded in the application notes that shipped it — for
example 2.0.0 in [operon-5.9.0.md](operon-5.9.0.md) and 2.1.3 in
[operon-5.11.2.md](operon-5.11.2.md). There is no separate `library-v2.*.md`.

## Adding a note

- Name it `operon-<X.Y.Z>.md` for the application, `library-v<bundle>.md` for the
  library.
- Keep the headings: what changed, compatibility, known limits where they exist.
- Add the matching `<name>-test-report.md` with the tree it was tested on.
- Link the new row in the table above; do not rewrite an older note.
