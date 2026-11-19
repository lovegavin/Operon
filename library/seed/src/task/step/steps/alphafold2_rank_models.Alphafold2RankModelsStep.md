# AlphaFold-2 model ranking

## Purpose

> Rank AlphaFold-2 models by pLDDT and copy the best one.

Reads the PDB models of one AlphaFold-2 output directory, orders them by pLDDT,
copies the best model as `best.pdb` and reports every candidate in
`ranking.csv`. The operator is plain Python: it reads the models, never imports
the `alphafold` package and needs no AlphaFold-2 installation.

## Inputs and outputs

Kind: `operator`. Operator ID: `alphafold2_rank_models`. Input count: `0`; the
models are a parameter, not a port.

The single output port carries a file artifact of format `pdb` whose `structure`
role is the copied `best.pdb`. Its `info` records the selected model name, its
pLDDT, the number of candidates, the original path and the ranking file. The
ranking table is written next to it as `ranking.csv` with the columns `rank`,
`name`, `plddt`, `path` and `selected` (`yes` for the model copied to
`best.pdb`, `no` otherwise). Both files are also registered as native results.

## Parameter guidance

| Parameter | Default | Meaning |
| --- | --- | --- |
| `models_dir` | required | An AlphaFold-2 output directory (searched recursively for `*.pdb`, `best.pdb` excluded) or a single PDB file. |
| `scores_json` | empty | Optional pLDDT table, for example the `ranking_debug.json` of the run. |
| `output` | `best` | Name of the output port. |

Without `scores_json` the pLDDT of a model is the mean B-factor of its C-alpha
atoms, which is the convention AlphaFold-2 writes into its PDB models. With
`scores_json` the table is read and matched to the model files by name, so both
the `{"plddts": {...}}` form of `ranking_debug.json`, a flat `{name: score}` map,
and a list of `{"name": ..., "plddt": ...}` rows are accepted. A model that the
table does not mention still falls back to its B-factor average, and keys such as
`ptm`, `iptm` and `max_pae` are never mistaken for pLDDT.

## Interpretation

Rank 1 is the model with the highest mean pLDDT among the candidates found, not
necessarily the model AlphaFold-2 itself would have ranked first: AlphaFold-2
ranks the five models of one run, while this operator ranks whatever PDB files
it finds, which can include relaxed and unrelaxed variants of every model.

The `plddt` column is a mean over residues, so two models with the same mean can
differ in where confidence is low. Read the per-residue B-factors when that
difference matters.

`selected` marks the single row copied to `best.pdb`. Ties keep the alphabetical
name order, because the sort is stable on `(plddt, name)`.

## Runtime environment

Declared Python requirements: `alphafold==2.3.2`. Prepare them explicitly in the
selected execution environment; registration and application startup do not
install them.

This operator executes in the dedicated `alphafold2` interpreter; see
docs/large_resources.md for resolution and overrides. It only reads PDB and JSON
files with the standard library, so it runs in that environment without the
AlphaFold-2 model code installed.

## Limitations

Declared memory modes: full. Every candidate PDB is read in full to compute its
B-factor average when no score table is available, so a directory of large
multimer models costs one file read per model.

The operator does not run AlphaFold-2, does not relax models and does not
compare against experimental structures. It also does not delete or rewrite the
input directory: `best.pdb` and `ranking.csv` are written into the Operon
artifact directory, not into `models_dir`.

## Scientific limitations

Mean pLDDT is a global summary of a per-residue confidence score. It can be high
for a model that is locally well built and globally wrong, especially when the
domains are correctly folded but arranged incorrectly; a low mean can also come
from a few long disordered termini.

Ranking models from different runs, different presets or different databases
compares confidence scales that are not calibrated against accuracy. Only rank
models that came from the same run and the same preset, and treat the outcome as
a selection heuristic rather than a validation.

The B-factor fallback assumes the AlphaFold-2 convention of writing pLDDT into
the B-factor column. A model from another source, or a relaxed model whose
B-factors were replaced, will produce a meaningless score under that fallback;
pass `scores_json` or inspect the file when the provenance is unknown.

Selecting `best.pdb` discards the alternatives from the artifact. The full set
stays in `models_dir`, and the ranking table keeps the path of every candidate so
the choice can be revisited.

## Examples

```python
from src.task.step.steps.alphafold2_rank_models import Alphafold2RankModelsStep

step = Alphafold2RankModelsStep()
# ctx.step_params carries the values of the parameter JSON:
#   models_dir, scores_json, output
```

`tests/test_alphafold2_operators.py` writes three small PDB files with different
B-factors and checks that `ranking.csv` orders them and that `best.pdb` is the
highest-scoring copy.

## Source

Implementation: `src/task/step/steps/alphafold2_rank_models.py` (`Alphafold2RankModelsStep`).
