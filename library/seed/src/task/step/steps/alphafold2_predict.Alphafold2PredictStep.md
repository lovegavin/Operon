# AlphaFold-2 structure prediction

## Purpose

> Predict one structure with a local AlphaFold-2 checkout.

Calls the official `run_alphafold.py` entry point of an existing AlphaFold-2
installation for a single FASTA file and returns the top-ranked model as a PDB
artifact. The operator never imports the `alphafold` package and never downloads
parameters or databases: the installation, the weights and the MSA databases
belong to the caller.

## Inputs and outputs

Kind: `operator`. Operator ID: `alphafold2_predict`. Input count: `0`; the input
FASTA is a parameter, not a port.

The single output port carries a file artifact of format `pdb`. Its `structure`
role is the `ranked_0.pdb` model that AlphaFold-2 ranked first, together with a
`result.json` report that records the FASTA path, the raw output directory, the
model preset, the template date and the reported scores. The raw AlphaFold-2
output tree (`unrelaxed_*.pdb`, `relaxed_*.pdb`, `result_model_*.pkl`,
`ranking_debug.json`, `msas/`) stays in `output_dir`; only the ranked model and
the report are copied into the Operon artifact directory.

## Parameter guidance

| Parameter | Default | Meaning |
| --- | --- | --- |
| `fasta_path` | required | One sequence in FASTA format. Its file name becomes the AlphaFold-2 output subdirectory. |
| `output_dir` | required | Destination of the raw AlphaFold-2 run; `ranked_0.pdb` is looked up in `<output_dir>/<fasta name>/`. |
| `data_dir` | `OPERON_ALPHAFOLD2_DATA`, then `OPERON_ALPHAFOLD_DATA` | `params/` and the MSA database tree. The operator fails when neither source resolves. |
| `runner` | `run_alphafold.py` | Script name or absolute path. A bare name is first looked up under `OPERON_ALPHAFOLD2_HOME`, then on `PATH`. |
| `model_preset` | `monomer_ptm` | `monomer`, `monomer_casp14`, `monomer_ptm` or `multimer`. |
| `max_template_date` | `2022-01-01` | `YYYY-MM-DD`; templates after that date are ignored. |
| `use_gpu` | `false` | Passed as `--use_gpu=true/false`. On `false` the child process runs with an empty `CUDA_VISIBLE_DEVICES`. |
| `python_executable` | `alphafold2` environment | Interpreter that runs the checkout. Leave empty in normal use. |
| `timeout_seconds` | `3600` | Wall-clock limit for one prediction. |
| `output` | `structure` | Name of the output port. |

The operator passes `--fasta_paths`, `--output_dir`, `--data_dir`,
`--model_preset`, `--max_template_date` and `--use_gpu` through unchanged, so
options outside this set are not reachable from the canvas; use the runner
directly when you need `--db_preset`, `--num_multimer_predictions_per_model` and
similar flags.

## Interpretation

`mean_plddt` and `ptm` are copied from `ranking_debug.json` (the `plddts` and
`ptm`/`iptm` entries of the model listed first in `order`). When that file is
missing or unparsable the mean pLDDT falls back to the per-residue `plddt` array
of the first readable `result_model_*.pkl`, and the score is reported as an empty
string when neither source can be read. An empty score therefore means "not
reported", not zero confidence.

A pLDDT above ~90 marks regions AlphaFold-2 itself considers well modelled;
values below ~70 usually indicate disordered or low-confidence regions. pTM only
exists for the `monomer_ptm` and `multimer` presets.

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

Declared memory modes: full. The operator only starts a subprocess, so the memory
estimate covers the Operon side, not the GPU and host RAM the AlphaFold-2 process
actually takes: budget several gigabytes of system memory and the model weights
on the executing machine. AlphaFold-2 writes its full output tree to `output_dir`,
which for a monomer run is far larger than the single model reported here.

The AlphaFold-2 installation, its CUDA and JAX stack, and the 2.7 TB `afdb`
database tree are external prerequisites. The operator fails with a clear error
when the runner, the interpreter or `data_dir` cannot be resolved.

## Scientific limitations

The returned structure is a prediction for the sequence in the FASTA file. It is
not a structure determination, and a high pLDDT does not certify the fold: pLDDT
is the network's own confidence in local geometry, not an error against an
experimental reference. Report it as a per-residue confidence score and validate
any downstream claim against experimental data or an orthogonal method.

A single-sequence run without a precomputed MSA searches the databases in
`data_dir`, and its accuracy depends on the depth of those databases and on the
template cutoff. Lowering `max_template_date` below the date of a relevant PDB
entry removes that template from the search; raising it above the present day
makes the run irreproducible because new entries keep arriving.

The operator returns only the top-ranked model. AlphaFold-2 ranks its five
models by mean pLDDT, so the ranking compares one scalar per model and says
nothing about the spread of plausible conformations. Do not present rank 1 as
the single correct answer, and do not compare pLDDT values across different
`model_preset` values or different database versions.

`multimer` runs require multi-sequence FASTA input and a different weight set;
feeding a single chain to the multimer preset does not test complex formation.

## Examples

```python
from src.core import StepError
from src.task.step.steps.alphafold2_predict import Alphafold2PredictStep

step = Alphafold2PredictStep()
# The operator expects ctx.step_params to carry the values of the parameter JSON:
#   fasta_path, output_dir, data_dir, runner, model_preset, max_template_date,
#   use_gpu, python_executable, timeout_seconds, output
```

`tests/test_alphafold2_operators.py` drives this operator with a stub
`run_alphafold.py` that writes `ranked_0.pdb` and `ranking_debug.json`, and checks
that the command line carries every parameter. That test never needs a real
AlphaFold-2 installation, and no end-to-end AlphaFold-2 prediction was run while
writing this page.

## Source

Implementation: `src/task/step/steps/alphafold2_predict.py` (`Alphafold2PredictStep`).
