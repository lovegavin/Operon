# AlphaFold-2 MSA search

## Purpose

> Build a multiple sequence alignment with jackhmmer or hhblits.

Searches the reference protein databases of an AlphaFold-2 `data_dir` for one
query sequence and returns the alignment as `msa.a3m`. The file follows the a3m
convention AlphaFold-2 expects: match columns in upper case, insert columns in
lower case with insert gaps removed, so it can be placed in a run's `msas/`
directory instead of letting AlphaFold-2 search again.

## Inputs and outputs

Kind: `operator`. Operator ID: `alphafold2_msa_search`. Input count: `0`; the
query is a parameter, not a port.

The single output port carries a file artifact of format `a3m` whose `alignment`
role is `<output_dir>/msa.a3m`. Its `info` records the tool, the database that was
searched, the query path, the query length and the number of alignment sequences
and columns.

A `jackhmmer` run also leaves its raw Stockholm alignment as
`<output_dir>/msa.sto`. An `hhblits` run writes `msa.a3m` directly, because the
tool produces a3m itself. The query string form is written to
`<output_dir>/query.fasta` first.

## Parameter guidance

| Parameter | Default | Meaning |
| --- | --- | --- |
| `sequence` | empty | Query residues; whitespace is stripped. Ignored when `fasta_path` is set. |
| `fasta_path` | empty | Query FASTA; takes precedence and is passed to the tool unchanged. |
| `output_dir` | required | Directory for `msa.a3m`, the query FASTA and any raw alignment. |
| `data_dir` | `OPERON_ALPHAFOLD2_DATA`, then `OPERON_ALPHAFOLD_DATA` | Reference databases. |
| `binary` | `jackhmmer` | Preferred tool. If it is not on `PATH` the other tool is used instead. |
| `threads` | `4` | Passed as `--cpu` (jackhmmer) or `-cpu` (hhblits). |
| `timeout_seconds` | `3600` | Wall-clock limit for one search. |
| `output` | `msa` | Name of the output port. |

`jackhmmer` searches `uniref90/uniref90.fasta` and converts the Stockholm result
to a3m. `hhblits` searches the `uniref30` database prefix
(`UniRef30_2021_03`, falling back to `UniRef30_2021_03_a3m` when only the
`_a3m` index exists) and writes a3m itself. Both reuse the AlphaFold-2 parameter
and database tree: the `data_dir` must be the one the `alphafold2` resource links
or downloads.

When neither tool is on `PATH` the operator fails with
`alphafold2 MSA search requires jackhmmer or hhblits on PATH`. A binary that
cannot be classified as either tool is rejected before any search starts.

## Interpretation

The alignment is the input of a prediction, not a result. Its sequence count and
column count are reported for diagnostics only; a deep alignment with many
columns is not automatically a good alignment, and a shallow alignment over
distant homologues can still fold well.

Distance and coverage are not reported by the search tools in a form this
operator parses, so `info` deliberately omits them. Inspect `msa.a3m` directly
when a prediction behaves unexpectedly.

`jackhmmer` writes a Stockholm alignment that this operator converts using its
`#=GC RF` annotation. Should a Stockholm file arrive without an RF line, every
column is treated as a match column, which keeps the residues but does not
demote insert columns; the resulting a3m is then conservative rather than
wrong, and its column count may exceed what AlphaFold-2 itself would produce.

## Runtime environment

Declared Python requirements: `alphafold==2.3.2`. Prepare them explicitly in the
selected execution environment; registration and application startup do not
install them.

This operator executes in the dedicated `alphafold2` interpreter; see
docs/large_resources.md for resolution and overrides. `OPERON_ALPHAFOLD2_DATA`
points at the parameter and database tree that the `alphafold2` resource links
into place, and `OPERON_ALPHAFOLD_DATA` is accepted as its fallback. The
`jackhmmer` and `hhblits` binaries themselves are not Python packages: they must
be on `PATH` of the executing machine, which the AlphaFold-2 installation
instructions already require.

## Limitations

Declared memory modes: full. The search itself is the memory and time cost:
`jackhmmer` on UniRef90 can take from minutes to hours per query, and the
operator runs one search, not the three-stage pipeline (UniRef90, MGnify,
small BFD) that AlphaFold-2 uses itself. A single `msa.a3m` is therefore not
equivalent to the full MSA tree of a prediction.

The operator does not merge `hhblits` and `jackhmmer` results, does not run
PSI-BLAST or MSA pairing, and does not deduplicate or filter the alignment. It
also does not re-search templates.

Only the `uniref90` and `uniref30` units of the resource are used, so a data
directory that holds only the parameter units fails with a message naming the
missing database file.

## Scientific limitations

A single-database alignment under-samples sequence space: UniRef90 concentrates
on well-studied families, so the alignment for an obscure protein can be thin and
the resulting prediction poor even though the search succeeded. Absence of hits
is not evidence of disorder or of novelty.

The conversion step assumes the standard a3m convention; the nucleotide or
protein character sets, the treatment of ambiguous residues and the meaning of
the query row are AlphaFold-2's, not this operator's. Do not reinterpret the
resulting columns as a phylogenetic alignment.

Sequence identity percentages are not reported, and the alignment contains no
quality annotation. Any downstream claim that depends on alignment quality must
measure it separately, for example with a reference alignment or a
structure-based check.

## Examples

```python
from src.task.step.steps.alphafold2_msa_search import Alphafold2MsaSearchStep

step = Alphafold2MsaSearchStep()
# ctx.step_params carries the values of the parameter JSON:
#   sequence (or fasta_path), output_dir, data_dir, binary, threads,
#   timeout_seconds, output
```

`tests/test_alphafold2_operators.py` checks that a machine without `jackhmmer`
and `hhblits` raises the documented error, so the test suite never searches a
real database.

## Source

Implementation: `src/task/step/steps/alphafold2_msa_search.py` (`Alphafold2MsaSearchStep`).
