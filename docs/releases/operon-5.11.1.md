# Operon 5.11.1 — accuracy fixes for structure, FASTA and model caches

This release fixes six defects found by real user routes, and completes the
AlphaFold-2 parameter set with the multimer weights.

## Structure readers no longer fail on non-polymer rows

`label_seq_id` is `.` for waters, ligands and other HETATM groups in mmCIF
files. Two operators converted that column unconditionally:

- `structure_extract_chain` called `float()` on every value, so a chain could
  not be extracted from a crystal file that contains waters.
- `structure_convert_format` called `int()` on the decoded residue numbers, so
  the cif -> PDB conversion failed on the same rows.

Both now share `residue_numbers()`, which parses each value defensively and
falls back to the sequential position for `.`/`?`/empty entries. Real 3DI3
files convert and extract again.

## ColabFold accepts multi-chain FASTA again

The protein FASTA alphabet treated `:` as an unknown residue, so a complex
input such as `IL-7:IL-7RA` was folded as a single chain and every interface
operator reported that the second chain was missing. The alphabet now keeps
`:` as a chain separator (the unknown code is unchanged), and
`colabfold_predict` forwards the original sequence text when the FASTA reader
provides it.

## RFdiffusion uses its bundled interpreter

The vendored RFdiffusion repository ships a Python 3.9 environment with
`dgl` and `e3nn`. The operator now defaults `python_executable` to
`<repo>/env/bin/python` when present and exports a library path built from both
the bridge prefix and that interpreter, so the bundled modules load on the
compute host instead of failing on the PyPI `dgl` wheel (which requires a
newer glibc than the server provides).

## Boltz uses the local resource cache

`boltz_predict` no longer requires the whole Boltz resource manifest to be
`ok`; it resolves the declared resource root and uses it whenever
`boltz1_conf.ckpt` exists. A partially declared resource therefore no longer
forces an online download on an offline node.

## AlphaFold-2 multimer parameters

The resource manifest now declares all fifteen parameter files, including
`params_model_{1..5}_multimer_v3.npz`. The parameter archive advertised by the
resource (`https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar`)
always contained them; the resource link on the server pointed at a shared
tree that only held the monomer files, so the panel under-reported and multimer
presets could not find their weights. Repointing the `params` unit at the full
set makes `model_preset=multimer` load its weights.

## Library

`operon-builtin-library` 2.1.2 carries the fixes above; the minimum
application version is 5.11.1.
