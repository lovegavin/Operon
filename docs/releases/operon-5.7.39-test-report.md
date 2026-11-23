# Operon Studio 5.7.39 acceptance

Release 5.7.39, library main-v1.1.25. Every item below was produced on the
licai-srv deployment (/public/home/lihj/Operon, managed micromamba Python 3.11)
driven through the local desktop service and the MCP tools.

## Environments

19 isolated environments, prepared from the UI: lphafold2 antifold antismash
boltz colabfold core dssp esm2 esm3 esmfold genomics hic hmmer ligandmpnn
openfold openmm81 proteinmpnn rfdiffusion rna. ina is the only optional
binding that cannot be installed (ina==1.2.5 ships no cp311 wheel and the
source build fails; the binary resource is used instead).

## Operator coverage

1055 of 1074 catalog operators have at least one complete job on a real
reader-to-operator route. The 19 remaining are classified below.

| class | operators | why |
| --- | --- | --- |
| weights not present offline | lphafold2_predict, lphafold2_batch_predict, colabfold_predict, esmfold_predict, openfold_predict, ligandmpnn_side_chain_packing, 
ucleotide_transformer_embedding, 
ucleotide_transformer_variant_effect | the upstream checkpoints are not part of the downloadable resource set |
| external binary missing | structure_pocket_detect (pocket) | no build for this host |
| python binding missing | ina_dock_python | ina has no cp311 wheel |
| contract needs a shape no reader produces | stuart_maxwell | wants two inputs with sample/eature dims; the matrix reader path is being worked out |
| fixture still wrong | lye_assemble, oltz_predict, oltz_complex_confidence | protein FASTA instead of nucleotide reads; single-chain FASTA for a complex |

## Fixes verified on this build

- 	RNAscan-SE from genomics runs after the environment is promoted (it used to
  fail with Can't locate tRNAscanSE/Configuration.pm in @INC because its wrapper
  pointed at the staging directory).
- nalyze_contacts runs with the default method=expected (previously
  No module named 'operon_hic.readers.tsv_reader').
- xgboost_regressor resolves its dependency from conda-forge.
- uild_contacts runs with a TAB-separated pairs file and min_mapq=0.
- mlp_classifier, mlp_regressor and utoencoder_anomaly pass the readiness
  probe (previously CXXABI_1.3.9 not found).

## Tests

pytest tests/test_environment_install.py 29 passed, pytest
tests/test_import_autolocate.py tests/test_hic_workflow.py 20 passed (3 skipped
without h5py), pytest tests/test_dependencies.py 11 passed 1 skipped. The
frontend suite and the packaging self-check pass inside uild5739.ps1.
