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

MD5 agreement: molecular_formula `3d76fd93ef72388721114182249472cf`,
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

## Batch b50 - formula and mass-spec arithmetic (5 operators)

- Route: `workdir/b50_route`
- Flow: `SmiReader(ligands.smi)` to `ligand_formula_parse`, `ligand_dbe`,
  `ligand_adduct_mz`, `ligand_mass_fraction`, `ligand_nitrogen_rule`, then six
  `export_results` CSV sinks (formula counts are exported twice: the b49 formula
  operator and the b50 parser).
- Input: `workdir/b50_route/input/ligands.smi`, 10 molecules (same panel as b49),
  sha256 `5090e90025d2bb5ebec9d0fd6c7b7262bdc8fca5f37fd689219f18f8344c6c3a`.
- Command (WSL): `PYTHONPATH=/home/gavin/Operon/library/seed:/home/gavin/Operon /home/gavin/bp-numpy21/bin/python scripts/run.py workdir/b50_route`
- Result: `complete`, 12/12 steps.

### Values read back

| Operator | aspirin | caffeine | ethanol |
| --- | --- | --- | --- |
| formula counts | C9 H8 O4, 21 atoms | C8 H10 N4 O2, 24 atoms | C2 H6 O, 9 atoms |
| dbe / integer | 6 / yes | 6 / yes | 0 / yes |
| [M+H]+ | 181.04953 | 195.08765 | 47.04914 |
| [M-H]- | 179.03499 | 193.07310 | 45.03459 |
| [M+2H]2+ | 91.02840 | 98.04746 | 24.02821 |
| carbon mass fraction | 0.60002 | 0.49480 | 0.52144 |
| nitrogen rule | even mass, even N, ok | even mass, even N, ok | even mass, even N, ok |

`dbe_minus_halogen` treats halogens as hydrogens and adds the same +1 term, so it
equals `dbe` for these neutral closed-shell formulas (6, 6, 0); it is retained as
a cross-check column rather than a second definition.

### Oracles

`workdir/b50_oracle.json` records 270 checks, 0 failures. Oracle A is pyteomics
5.0.2 (`mass.calculate_mass`, `mass.isotopologues` for the parent formula); Oracle
B is independent hand arithmetic with average atomic weights C 12.011, H 1.008,
N 14.007, O 15.999, P 30.974, S 32.06, F 18.998, Cl 35.45, Br 79.904, I 126.904.

| Operator | Oracle A | Oracle B | Result | Tolerance | Pass |
| --- | --- | --- | --- | --- | --- |
| ligand_formula_parse | RDKit `CalcMolFormula` | manual Hill parse of the input SMILES | identical element counts | exact | yes |
| ligand_dbe | pyteomics neutral mass parity | hand DBE `C-(H+X)/2+N/2+1` | all 10 formulas agree | exact | yes |
| ligand_adduct_mz | pyteomics exact mass + proton/Na/NH4 constants | hand adduct arithmetic | max abs error < 1e-4 m/z | 1e-4 | yes |
| ligand_mass_fraction | manual average-weight fractions | sum-to-one and per-element ratio check | max abs error < 1e-6 | 1e-6 | yes |
| ligand_nitrogen_rule | hand nominal mass and N parity | parity table for the 10 molecules | all rows ok | exact | yes |

### Three-end results

| End | Result | Evidence |
| --- | --- | --- |
| WSL (Ubuntu 24.04, bp-numpy21, NumPy 2.1.3) | PASS | 12/12 steps, values above |
| Windows (`D:\Operon`, Python 3.12.10, NumPy 2.5.4) | PASS | same six CSV files, MD5 identical to WSL |
| srv (`/public/home/lihj/...`) | SKIP | no `srv` host in `~/.ssh/config`, no `/public/home/lihj` mount |

MD5 agreement: adduct_mz `6bfe10d65008e3e8c957d4ced3f3310a`,
dbe `0a4363e5df89af2aa57741d1a270ddf7`,
formula_parse `ea8f66beb8cd14ffe8c969373160db1a`,
mass_fraction `d8efda990b0b41a0aa36b5efe330a375`,
molecular_formula `3d76fd93ef72388721114182249472cf`,
nitrogen_rule `cdc06190eb5c10021c6615ecb3613363`.

### Limitations

- Formula strings are echoed in `info["formula"]`; the export is the numeric
  element-count matrix, so a CSV consumer must map columns through the headers.
- Only neutral, closed-shell Hill formulas are parsed. Charges, hydrate dots and
  parentheses raise `StepError` instead of being silently ignored.
- `dbe_minus_halogen` is a cross-check of the same arithmetic; it is not an
  independent estimate and should not be reported as a separate descriptor.
- The panel is a small, curated public-molecule panel intended for arithmetic
  verification, not a biological conclusion.

## Batch b51 - protein sequence motif panel (5 operators)

- Route: `workdir/b51_route`
- Flow: `FastaReader(proteins.fasta)` to `protein_aliphatic_index`,
  `protein_nls_motifs`, `protein_pts1_signal`, `protein_kinase_motifs`,
  `protein_nglyc_sequons`, then five `export_results` CSV sinks.
- Input: `workdir/b51_route/input/proteins.fasta`, 7 UniProt sequences
  (P03070 SV40 large T, P05221 nucleoplasmin, P01308 insulin, P00698 lysozyme,
  P42212 GFP, P02768 albumin, P08659 firefly luciferase),
  sha256 `f5130ba902bfff78f30a15507427547fa14197242c720e322be9d4849b7a4e2f`.
- Command (WSL): `PYTHONPATH=/home/gavin/Operon/library/seed:/home/gavin/Operon /home/gavin/bp-numpy21/bin/python scripts/run.py workdir/b51_route`
- Result: `complete`, 10/10 steps.

### Values read back

| Operator | SV40 T | nucleoplasmin | insulin | lysozyme | GFP | albumin | luciferase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aliphatic_index | 74.93 | 62.00 | 102.91 | 81.70 | 74.87 | 77.57 | 94.65 |
| NLS mono / bipartite / total | 3 / 0 / 3 | 2 / 1 / 3 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 0 / 1 | 2 / 0 / 2 |
| PTS1 signal | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| kinase PKA / CK2 / CDK / total | 0 / 11 / 2 / 13 | 0 / 5 / 2 / 7 | 0 / 1 / 0 / 1 | 0 / 0 / 0 / 0 | 0 / 2 / 0 / 2 | 1 / 7 / 0 / 8 | 0 / 7 / 0 / 7 |
| N-glyc sequons | 1 | 1 | 0 | 0 | 0 | 0 | 3 |

The lysozyme PTS1 hit (`...GCRL`) and the luciferase hit (`...SKL`) show that
the column is a C-terminal motif scan, not a peroxisome predictor. The NLS
column counts motif occurrences, so a protein can carry more than one.

### Oracles

| Operator | Oracle A | Oracle B | Input | Result | Tolerance | Pass |
| --- | --- | --- | --- | --- | --- | --- |
| protein_aliphatic_index | Biopython 1.88 `ProteinAnalysis.count_amino_acids` + Ikai 1980 | manual formula check in unit tests | 7 sequences | max abs delta < 1e-4 | 1e-4 | yes |
| protein_nls_motifs | independent `re` scan | curated positives (SV40, nucleoplasmin) | 7 sequences | 7/7 identical | exact | yes |
| protein_pts1_signal | independent terminal-set check | luciferase SKL positive control | 7 sequences | 7/7 identical | exact | yes |
| protein_kinase_motifs | independent string slicing | curated motif examples in unit tests | 7 sequences | 7/7 identical | exact | yes |
| protein_nglyc_sequons | independent overlap-aware scan | `N[^P][ST]` unit examples | 7 sequences | 7/7 identical | exact | yes |

All 35 checks pass (`workdir/b51_oracle.json`). Motif definitions are literature
consensus patterns; they are deliberately simple and are documented as scans,
not as functional annotations.

### Three-end results

| End | Result | Evidence |
| --- | --- | --- |
| WSL (Ubuntu 24.04, bp-numpy21, NumPy 2.1.3) | PASS | 10/10 steps, values above |
| Windows (`D:\Operon`, Python 3.12.10, NumPy 2.5.4) | PASS | same five CSV files, MD5 identical to WSL |
| srv (`/public/home/lihj/...`) | SKIP | no `srv` host in `~/.ssh/config`, no `/public/home/lihj` mount |

MD5 agreement: aliphatic_index `adc5c3a215bcdd8f1fd3bd5be94d50d5`,
kinase_motifs `f752fcbed306456e45fe080579af31ac`,
nglyc_sequons `7ad8da7f486421d7505ce575a75cbd14`,
nls_motifs `87aa5663d7e4c096f251603c8e390eb4`,
pts1_signal `18399bbc2e874ec708e6f326e5b39390`.

### Limitations

- Motif scans use short consensus regular expressions; they can produce false
  positives (lysozyme PTS1) and do not model species-specific import rules.
- Aliphatic index assumes the full UniProt sequence, including signal peptides
  and propeptides, and is sensitive to unknown residues (sanitized to X).
- The panel is a curated public-sequence panel for arithmetic verification, not
  a biological conclusion.
