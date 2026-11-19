# AlphaFold-2 batch structure prediction

## Purpose

> Predict many structures with one local AlphaFold-2 installation.

Runs the same `run_alphafold.py` invocation as `alphafold2_predict` once per FASTA
file, either for every FASTA file in a directory or for an explicit list of
files, and reports one row per input in `summary.csv`. A failing input does not
stop the batch: its row carries the error text and the remaining inputs still
run.

## Inputs and outputs

Kind: `operator`. Operator ID: `alphafold2_batch_predict`. Input count: `0`;
the FASTA files are parameters, not ports.

The single output port carries a file artifact of format `csv`: the
`summary.csv` written into `output_dir`, with the fixed columns `name`, `status`,
`pdb`, `plddt` and `error`. `status` is `ok` or `failed`; `pdb` is the absolute
path of the ranked model inside the raw output tree; `plddt` is the mean pLDDT
reported for that model and stays empty when it cannot be read; `error` is the
operator error text for a failed row and stays empty otherwise.

`output_dir` also keeps the raw AlphaFold-2 output tree of every input. The
directory is never cleaned by the operator, so rerunning a batch reuses the
existing subdirectories named after each FASTA file.

## Parameter guidance

| Parameter | Default | Meaning |
| --- | --- | --- |
| `fasta_dir` | empty | Every `.fasta`, `.fa`, `.faa` and `.fas` file of this directory, in name order. |
| `fasta_paths` | empty | Explicit files, merged with the directory result and de-duplicated. |
| `output_dir` | required | Where the per-input output trees and `summary.csv` go. |
| `data_dir` | `OPERON_ALPHAFOLD2_DATA`, then `OPERON_ALPHAFOLD_DATA` | `params/` and the MSA database tree; resolved once for the whole batch. |
| `runner` | `run_alphafold.py` | Script name or absolute path, resolved once for the whole batch. |
| `model_preset` | `monomer_ptm` | One preset for every input. |
| `max_template_date` | `2022-01-01` | `YYYY-MM-DD`, applied to every input. |
| `use_gpu` | `false` | Passed through; inputs run sequentially, one process at a time. |
| `python_executable` | `alphafold2` environment | Interpreter for every input. |
| `timeout_seconds` | `3600` | Per input, not for the whole batch. |
| `output` | `summary` | Name of the output port. |

At least one of `fasta_dir` or `fasta_paths` must resolve to a file; otherwise
the operator fails before starting any run. When every input fails, the operator
raises an error that names the summary file and the first failure, so an empty
`ok` set is never reported as a completed batch.

## Interpretation

The CSV is the record of the batch. Read `status` before using `pdb`: a `failed`
row has no model, and a `plddt` that is empty means "not reported", not zero
confidence. Because rows are produced by the same code path as
`alphafold2_predict`, the scores have the same meaning as there: mean pLDDT comes
from `ranking_debug.json`, with a fallback to the per-residue `plddt` array of
the first readable `result_model_*.pkl`.

Comparing pLDDT across rows is only meaningful when the rows came from the same
preset, the same database tree and the same template cutoff, which is what this
operator enforces for one run.

## Runtime environment

Declared Python requirements: `alphafold==2.3.2`. Prepare them explicitly in the
selected execution environment; registration and application startup do not
install them.

This operator executes in the dedicated `alphafold2` interpreter; see
docs/large_resources.md for resolution and overrides. `OPERON_ENV_ALPHAFOLD2`
overrides the interpreter path, `OPERON_ALPHAFOLD2_HOME` points at the checkout
and `OPERON_ALPHAFOLD2_DATA` points at the parameter and database tree that the
`alphafold2` resource links into place.

## Limitations

Declared memory modes: full. Inputs are processed sequentially, so the runtime of
a batch is the sum of its inputs and a two-hour monomer run becomes a working
day for a handful of sequences. The memory estimate covers the Operon side only;
each AlphaFold-2 process still needs its own host memory and, when `use_gpu` is
true, the GPU.

The operator inherits every failure mode of a single prediction: a missing
interpreter, a missing runner, an unreadable `data_dir` or a non-zero exit code.
Those are recorded per row for a failing input, but an unresolvable `data_dir`,
`runner` or interpreter fails the whole batch before the first row is written,
because the batch would fail identically for every input.

`output_dir` grows by one full AlphaFold-2 output tree per input and is never
pruned.

## Scientific limitations

A batch of single-sequence predictions is a set of independent models, not a
complex and not a comparative benchmark. Nothing in the operator makes the rows
comparable: inputs of very different length, disorder content or homology depth
produce pLDDT values that are not on a shared accuracy scale, and a row with a
higher pLDDT is not automatically the more reliable structure.

The species or paralogue context of each sequence is not modelled. Sequences
from the same family run through the same databases will share templates and MSA
hits, so their models are correlated and should not be counted as independent
evidence.

`multimer` needs multi-sequence FASTA files; a directory of single-chain FASTA
files run with the multimer preset does not test complex formation, it only
produces a monomer model under multimer weights.

A failed row means the subprocess failed. It does not mean the sequence cannot be
modelled: check the error text, the database tree and the interpreter before
concluding anything about the protein.

## Examples

```python
from src.task.step.steps.alphafold2_batch_predict import Alphafold2BatchPredictStep

step = Alphafold2BatchPredictStep()
# ctx.step_params carries the values of the parameter JSON:
#   fasta_dir (or fasta_paths), output_dir, data_dir, runner, model_preset,
#   max_template_date, use_gpu, python_executable, timeout_seconds, output
```

`tests/test_alphafold2_operators.py` drives this operator with a stub
`run_alphafold.py` and checks the `summary.csv` rows; it needs no real
AlphaFold-2 installation.

## Source

Implementation: `src/task/step/steps/alphafold2_batch_predict.py` (`Alphafold2BatchPredictStep`).
