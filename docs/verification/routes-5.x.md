# Routes 5.x verification

Incremental route evidence for the 5.x operator expansion. Each batch records the
route, the public data hash, per-step values, independent oracles, and the three
end results. A SKIP always states the missing prerequisite; no value is invented.

## Batch b49 - ligand property panel (5 operators)

- Route: `workdir/b49_route`
- Flow: `SmiReader(ligands.smi)` to `ligand_molecular_formula`,
  `ligand_exact_mass`, `ligand_brics_fragments`, `ligand_rgroup_decomposition`,
  `ligand_isotope_pattern`, then five `export_results` CSV sinks.
- Input: `workdir/b49_route/input/ligands.smi`, 10 molecules,
  sha256 `c392966d677a92f8e55639c47565cecb921d462c990d70dbdf708d9a57fa621b`.
- Command (WSL): `PYTHONPATH=/home/gavin/Operon/library/seed:/home/gavin/Operon /home/gavin/bp-numpy21/bin/python scripts/run.py workdir/b49_route`
- Result: `complete`, 10/10 steps; per-step elapsed 0.001-0.096 s.

### Values read back

| Operator | aspirin | caffeine | ethanol |
| --- | --- | --- | --- |
| formula | C9H8O4, heavy 13, total 21 | C8H10N4O2, heavy 14, total 24 | C2H6O, heavy 3, total 9 |
| exact_mass | 180.04225 | 194.08037 | 46.04187 |
| brics n_fragments | 4 | 1 | 1 |
| isotope base peak m/z | 181.04953 | 195.08765 | 47.04914 |
| isotope M+1 relative | 0.09734 | 0.01477 | 0.02163 |

R-group decomposition with scaffold `c1ccccc1[*:1]` matched 6 of 10 molecules.
The numeric cells are substituent heavy-atom counts (aspirin R1=4, R2=1, R3=3);
substituent SMILES are carried in `info["rgroup_smiles"]`, not in the CSV.

### Oracles

| Operator | Oracle A | Oracle B | Input | Result | Tolerance | Pass |
| --- | --- | --- | --- | --- | --- | --- |
| ligand_molecular_formula | molmass 2026.11.1 | manual Hill string | C9H8O4, C8H10N4O2, C2H6O | identical formulas | exact | yes |
| ligand_exact_mass | pyteomics 5.0.2 | molmass 2026.11.1 | same three formulas | max abs error < 1e-4 Da | 1e-4 Da | yes |
| ligand_isotope_pattern | pyteomics `isotopologues` | manual 13C expectation | C9H8O4 | rel_1 0.0973 vs 0.0993 (pyteomics) | 0.02 | yes |

BRICS fragmentation and R-group decomposition have no independent external oracle
in this environment; both were checked against hand-computed small examples and
RDKit's documented behavior. That limitation is recorded rather than hidden.

### Three-end results

| End | Result | Evidence |
| --- | --- | --- |
| WSL (Ubuntu 24.04, bp-numpy21, NumPy 2.1.3) | PASS | 10/10 steps, values above |
| Windows (`D:\Operon`, Python 3.12.10, NumPy 2.5.4) | PASS | same five CSV files, MD5 identical to WSL; tree reports library 5.0.0 |
| srv (`/public/home/lihj/...`) | SKIP | no `srv` host in `~/.ssh/config`, no `/public/home/lihj` mount; host name and credentials unknown |

MD5 agreement: molecular_formula `df5e087dcf78217c257ce2846a665681`,
exact_mass `44fd7b03bda29e91f14a2629b2d38dc2`,
brics_fragments `5d99cf7d491275c97b73aa723f8779ed`,
rgroup_decomposition `18533212868f5ed840b53045326d0a9a`,
isotope_pattern `5d091e0715086595a31715f9f7afec4a`.

### Limitations

- CSV exports are numeric only. Formula strings and R-group SMILES are in the
  output Form `info` and therefore visible to downstream Form consumers but not
  in the exported CSV.
- The isotope pattern merges theoretical peaks within 1e-6 Da and truncates to
  6 peaks by default; very low-abundance fine structure is intentionally dropped.
- RDKit version 2026.09.1 differs between ends only in the recorded build string;
  it is the same package generation on both ends.
