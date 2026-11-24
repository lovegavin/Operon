# Operon Studio 5.8.0 acceptance

Release 5.8.0, library main-v1.2.0. The acceptance run installs the released
artifact into a fresh directory, connects the *test* server
(`licai-srv-test`, 172.22.149.42), and performs every step through the desktop
UI first and then through the MCP tools, on the same build.

## Operator coverage

`1074 / 1074` operators reached `complete` at least once. Coverage is counted by
intersecting the operator names recorded in the finished jobs with
`catalog_names.txt`, so a compound or stale name cannot inflate it:

```
rows 9384  catalog 1074  attempted 1074  complete 1074  rate 100.0% (missing 0)
```

Every run used a real reader and public data: PDB entries (1CRN, 1UBQ, 1L2Y,
1AKE, 1CA2, 4HHB, 1MEL), GTEx and PBMC3k matrices, iris, lung, mtcars, ClinVar
chr21 VCF, chr21 GFF3/BED/FASTA, E. coli reads and assemblies, UniProt FASTA,
ClinVar/GO/Pfam/Rfam databases, Hi-C pairs, BiGG `e_colour_core`, and docking
ligands.

## GPU

| environment | torch | CUDA visible |
| --- | --- | --- |
| antifold, boltz, esm2, esm3, esmfold, ligandmpnn, openfold, proteinmpnn, rfdiffusion | 2.3.1+cu121 / 2.6.0+cu124 | yes |
| alphafold2, colabfold | jaxlib 0.4.23+cuda12.cudnn89 | yes (`jax.devices() == [cuda(id=0)]`) |

`esmfold_predict` 538 s → 58 s, `proteinmpnn_design` 83 s,
`ligandmpnn_side_chain_packing` 185 s, `alphafold2_batch_predict` ran with
18.9 GB resident on the RTX 3090. The ten small tabular networks keep
`supports_cuda: false`: they are two-layer models over a few thousand floats,
where a transfer costs more than the arithmetic.

## Environments and resources

Twenty environments are declared. The acceptance report records, per
environment, the prepare request issued from the UI, the time it took, and the
`GET /api/remote/{rid}/environments` answer afterwards; the resource section
records, per resource, the download that was started and stopped and the link
that replaced it.
