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

## b52 — protein localization and property panel (10 sequences)

Five operators extend the b51 protein panel: ER-retention motifs,
nuclear-export-signal density, mitochondrial presequence score, charge-versus-pH
curve and Kyte-Doolittle GRAVY windows. The b52 route runs the same ten
sequences through all five operators and exports one CSV per operator.

### Data

`workdir/b52_route/input/proteins.fasta` (10 reviewed UniProt entries; the seven
b51 entries plus P07237, P05186 and P06576), sha256
`db38a65adbddc42600bf9dc1c6bfa0ed92e7c4151a04dffa964fe84308d3c7af`.
Sequences were downloaded from `https://rest.uniprot.org/uniprotkb/<acc>.fasta`.

### Route

```bash
PYTHONPATH=/home/gavin/Operon/library/seed:/home/gavin/Operon \
  python scripts/run.py workdir/b52_route
```

All 10 steps report `complete`. Selected values:

| Sequence | any ER retention | NES density | mito score | charge pH 7 | GRAVY mean |
| --- | --- | --- | --- | --- | --- |
| P03070 SV40 large T | 0 | 1.977 | 0.747 | -10.84 | -0.547 |
| P05221 nucleoplasmin | 0 | 1.500 | 1.591 | -15.59 | -0.921 |
| P07237 PDI (KDEL) | 1 | 0.984 | 1.066 | -33.51 | -0.431 |
| P42212 GFP | 0 | 0.840 | 2.831 | -5.66 | -0.521 |
| P06576 ATPB (mito) | 0 | 3.025 | 7.302 | -12.57 | 0.018 |

### Oracle

`workdir/b52_oracle.json` reports 130/130 checks with zero failures:

- ER motifs: independent Python substring scan of KDEL/HDEL/DDEL.
- NES: independent combinatorial scan over the Phi-X(2,3)-Phi-X(2,3)-Phi-X-Phi
  pattern, counting unique start positions (the first oracle draft double-counted
  overlapping spacer choices and was fixed).
- Mito: hand Kyte-Doolittle sum and hydrophobic moment over the same 30-residue
  window.
- Charge: independent Henderson-Hasselbalch reimplementation with ExPASy/EMBOSS
  pKa values (Nterm 8.6, Cterm 3.6, D 3.9, E 4.1, C 8.5, Y 10.1, H 6.5, K 10.8,
  R 12.5). Biopython 1.88 `IsoelectricPoint` uses a different pKa set (Nterm 7.5,
  K 10.0, R 12.0, H 5.98, D 4.05, E 4.45, C 9.0, Y 10.0), so its absolute charges
  are not used as the oracle; the convention is documented in the operator page.
- GRAVY: hand per-residue mean and window extrema.

### Three-end comparison

| Endpoint | Result |
| --- | --- |
| WSL (bp-numpy21, NumPy 2.1.3) | 10/10 steps, md5 below |
| Windows 12.10 (`D:\Operon`, NumPy 2.5.4) | 10/10 steps, same md5 |
| srv (`/public/home/lihj`) | SKIP: `ssh srv` does not resolve and no host is configured |

| Export | md5 (WSL = Windows) |
| --- | --- |
| `er_retention.csv` | `cf2aac1f886eb3b936817124e854e3d0` |
| `nuclear_export_signal.csv` | `942204b8499fd9d2d36e7b393724f67a` |
| `mito_targeting.csv` | `89020753b8536830ff40d824db81597b` |
| `charge_curve.csv` | `88096c6a5ec25838bbacfaffc8734c0d` |
| `gravy_window.csv` | `aff8ec58e13a5dab75c6c18b5b805f35` |

### Limitations

- All five outputs are sequence heuristics, not curated functional annotations.
  A single KDEL match or a high NES density is a candidate signal only.
- The NES pattern is the published CRM1 consensus; density is length-normalised
  and is not a prediction of export activity.
- The mitochondrial score uses the first 30 residues and does not model import
  efficiency, charge compensation or tandem presequences.
- Charge curves use fixed pKa values and ignore local environment, binding and
  post-translational charge changes; cross-tool absolute values differ when the
  pKa convention differs.
- A GPI-anchor heuristic was implemented and then withdrawn: it gave a false
  negative on the curated GPI protein P05186 and no independent oracle was
  available. It is recorded in the gap matrix as not planned.

## b53 — narrowPeak geometry panel (Epigenomics)

Batch: `b53`, 4 operators, 20 August 2026 development tree (library 5.0.2 line).
Operators: `peak_width_stats`, `peak_summit_offset`, `peak_gap_stats`, `peak_signal_stats`.

### Data

| item | value |
| --- | --- |
| source | ENCODE GM12878 narrowPeak, first 20 000 rows of the local `workdir/b8_prep/peaks.bed` (hg19) |
| route input | `workdir/b53_route/input/peaks.narrowpeak` |
| rows | 20 000 peaks, 10 narrowPeak columns |
| sha256 | `dc25af7dc7579bc701d88fd8c7ae70a783c32f57ad131d51a7dd8553151ed931` |

The local file is a canonical ENCODE narrowPeak subset already used by the b8 batch;
the route reads columns chrom/start/end/name/score/strand/signal/p/q/peak with
`NarrowPeakReader`.

### Route

`workdir/b53_route` — source `NarrowPeakReader` → four operators → four
`export_results` (CSV). Command:

```bash
PYTHONPATH=/home/gavin/Operon/library/seed:/home/gavin/Operon \
  /home/gavin/bp-numpy21/bin/python scripts/run.py workdir/b53_route
```

Result: 8/8 steps complete in 0.84 s. Exports:
`output/artifacts/exports/<hash>/{width,summit,gap,signal}.csv`.

### Values (20 000 peaks)

| metric | value |
| --- | --- |
| width n / mean / median / sd | 20000 / 1110.55 / 1080 / 354.65 |
| width min / max / p90 / total bp | 230 / 2946 / 1572.1 / 22211001 |
| summit mean offset / median | 555.43 / 503 |
| summit mean center deviation | 177.85 |
| summit frac centered ≤50 bp | 0.19345 |
| summit mean relative position | 0.50062 |
| gaps n / mean / median / max | 19977 / 146174.95 / 31128 / 22503243 |
| gaps frac <1000 bp / overlaps / total bp | 0.2140 / 3992 / 2920137002 |
| signal mean / median / max / p95 | 15.8736 / 15.3551 / 43.6063 / 25.9905 |
| mean pValue / mean qValue | 548.4496 / 545.0104 |
| frac q>10 / frac q>20 | 1.0 / 1.0 |

### Oracles

`C:\Users\Public\b53_oracle2.py` recomputed every statistic twice: a pandas/NumPy
implementation and an independent awk implementation over the same file (gaps use
`sort -k1,1 -k2,2n` + awk for gap count and overlaps). 49/49 checks pass; the
record is `workdir/b53_oracle.json`.

| oracle | implementation | checks | result |
| --- | --- | --- | --- |
| A | pandas 2.3.3 + NumPy 2.1.3 | 33 | pass |
| B | awk 5.1.0 (interval arithmetic, sorted scan) | 16 | pass |

Median and SD are only in oracle A because awk lacks a portable median; the unit
tests pin a hand-computed five-row example for both.

### Three-end

| end | status | evidence |
| --- | --- | --- |
| WSL (bp-numpy21, NumPy 2.1.3) | PASS | 8/8 steps; md5 below |
| Windows (D:\Operon, py 3.12.10, NumPy 2.5.4) | PASS | 8/8 steps; md5 below |
| srv (`/public/home/lihj/...`) | SKIP | `ssh srv` is not resolvable in this environment and no `/public/home/lihj` mount exists |

CSV md5 (WSL = Windows):

| export | md5 |
| --- | --- |
| width.csv | `d8ba3788d39ad1d012f29d9e25852585` |
| summit.csv | `35040b71b9eff669fac7f5577124729c` |
| gap.csv | `d7656cedbdc3ed1dbe8959ae7dc38d24` |
| signal.csv | `9bc0e3c9532a516ffce1c054a9163470` |

Unit tests: `tests/test_peak_panel_b53.py`, 4 passed.

### Limitations

- The route uses a 20 000-row subset; full-file numbers will differ.
- `peak_gap_stats` counts overlaps as gaps clamped to zero and reports their count
  separately; overlapping intervals are not merged first.
- Signal columns are narrowPeak signalValue/pValue/qValue as stored; qValue is not
  recomputed.
- `peak_quality_filter` remains planned for a later epigenomics batch.

## b54 — narrowPeak strand, width–signal and chromosome distribution

Date: 2026-11-08. Commit: this batch's `feat(library)` commit.

### Operators

| id | purpose | output |
| --- | --- | --- |
| `peak_strand_bias` | plus/minus/unknown peak counts and plus fraction | 6 metrics |
| `peak_width_signal_correlation` | Pearson/Spearman correlation and linear fit of peak width vs signalValue | 7 metrics |
| `peak_chrom_summary` | peaks per chromosome, top-chromosome fractions | 7 metrics |

`peak_quality_filter` was prototyped but removed before commit: a filtered
narrowPeak table keeps encoded string columns and the CSV export would expose
label codes rather than chrom/name text. It remains planned for a batch that can
pair it with a text writer.

### Route

`workdir/b54_route` reuses the first 20 000 rows of the ENCODE GM12878 narrowPeak
file (`workdir/b8_prep/peaks.bed`), sha256
`dc25af7dc7579bc701d88fd8c7ae70a783c32f57ad131d51a7dd8553151ed931`.
Command:

```
PYTHONPATH=$PWD/library/seed:$PWD /home/gavin/bp-numpy21/bin/python scripts/run.py workdir/b54_route
```

6/6 steps complete in 0.05 s.

### Values

| metric | value |
| --- | --- |
| n_peaks | 20 000 |
| n_plus / n_minus / n_unknown | 0 / 0 / 20 000 |
| fraction_plus | 0.0 |
| plus_minus_ratio | nan (no minus-strand peak) |
| pearson_r | -0.30582777 |
| spearman_rho | -0.28463130 |
| slope_bp_per_signal | -19.03993609 |
| intercept_bp | 1412.78278377 |
| mean_width / mean_signal | 1110.55005 / 15.87362123 |
| n_chromosomes / max / median | 23 / 2033 / 863 |
| fraction_top1 / fraction_top3 | 0.10165 / 0.24030 |

Every peak in this file has `.` in the narrowPeak strand column, so the strand
panel correctly reports 100 % unknown. `plus_minus_ratio` is `nan`, not `inf`, so
the CSV stays finite.

### Oracles

`C:\Users\Public\b54_oracle.py` recomputes all 16 reported quantities from the
same file with pandas 2.3.3/NumPy 2.1.3, including an explicit rank correlation
and `numpy.polyfit`. 16/16 checks pass; `workdir/b54_oracle.json` records the
input sha256 and each delta.

| oracle | implementation | checks | result |
| --- | --- | --- | --- |
| A | pandas + NumPy (rank correlation, polyfit) | 16 | pass |

The unit tests pin a six-row hand-computed example
(`tests/test_peak_panel_b54.py`, 3 passed), which is the second, independent
check on the definitions.

### Three-end

| end | status | evidence |
| --- | --- | --- |
| WSL (bp-numpy21, NumPy 2.1.3) | PASS | 6/6 steps; md5 below |
| Windows (D:\Operon, py 3.12.10, NumPy 2.5.4) | PASS | 6/6 steps; md5 below |
| srv (`/public/home/lihj/...`) | SKIP | `ssh srv` unresolved; no `/public/home/lihj` mount |

CSV md5 (WSL = Windows):

| export | md5 |
| --- | --- |
| strand_bias.csv | `9b089a5b41e628234fbb5b94890528a1` |
| width_signal_correlation.csv | `b01c467b9468d953a725fbf127d69b4f` |
| chrom_summary.csv | `dd37e5e64e17239d20fd6cdcbe392708` |

The correlation statistics are rounded to 8 decimals inside the operator so that
NumPy/BLAS last-bit drift between 2.1.3 and 2.5.4 cannot change the artifact
bytes. Without that rounding the Windows value differed at the 1e-16 level and
the md5 did not match.

### Limitations

- The route uses a 20 000-row subset; full-file numbers differ.
- Strand statistics are uninformative for this file because ENCODE stores `.` for
  all peaks; the operator reports that fact instead of guessing.
- Correlation is descriptive; peaks are not independent observations.

## b70 - epidemic curve panel (synthetic SIR incidence)

**Data.** `workdir/b70_route/input/cases.csv`, 120 daily rows (day, cases, deaths),
sha256 `8a3d28f5e5c64349b7f2e235b16aeaeb379740be4966b33ff20866e83a4ef047`.
The series is simulated from a closed SIR model (N = 1 000 000, beta = 0.45,
gamma = 0.12, I0 = 100) with 2 % multiplicative noise and 2 % daily deaths. It is
reported as `mode=synthetic`; it carries no epidemiological claim about a real
outbreak.

**Route.** `workdir/b70_route` (CsvReader -> five operators -> five CSV exports),
`python scripts/run.py workdir/b70_route`, 10/10 steps complete in 7.4 s.

| Operator | Output | Value |
| --- | --- | --- |
| `epidemic_growth_rate` | growth_rate_per_day | 0.26483866 |
| | doubling_time_days | 2.61724317 |
| | r_squared (log scale) | 0.99586155 |
| `epidemic_r0` | r0 (generation time 5 d) | 2.32419331 |
| `epidemic_case_fatality` | cfr | 0.02000062 |
| | deaths / cases | 19 413 / 970 620 |
| `epidemic_sir_fit` | beta / gamma / R0 | 0.34923955 / 0.04139811 / 8.43612222 |
| | rmse | 816.67415372 |
| `epidemic_seir_fit` | beta / sigma / gamma / R0 | 2.76689033 / 0.2 / 0.82503804 / 3.35365184 |
| | rmse | 438.30127516 |

The fitted SIR/SEIR parameters are a least-squares projection of a single noisy
incidence curve; beta and gamma are not separately identifiable, so the fit does
not recover the generating values. The operator reports the fit, not a claim
about the true parameters.

**Oracle.** `workdir/b70_oracle.json`: 16/16 checks pass. Oracle A: NumPy
`polyfit` on the log incidence (growth, doubling, R^2), sums for CFR, and
`beta/gamma` for R0. Oracle B: an independent `solve_ivp` SIR/SEIR fit with a
25 x 54 grid search followed by `least_squares` (not the operator's 9-start
optimizer). All fitted values agree to < 1e-4 in beta/gamma and < 1.0 in RMSE.

**Three-end.**

| End | Route | Hash comparison |
| --- | --- | --- |
| WSL (NumPy 2.1.3) | 10/10 complete | growth `f6cea665263959f54744cb67e343fccf`, r0 `88e0c3bb03af3c05b3fd3edfd2d74158`, cfr `759acba3fdcefcc51bbec53fbcba4fea` |
| Windows 12.10 / NumPy 2.5.4 (D:\Operon) | 10/10 complete | growth, r0, cfr match WSL; SIR `fed6091a...` and SEIR `62543952...` differ in the last printed digits |
| srv | SKIP | `ssh srv` is not resolvable in this environment; no `/public/home/lihj` mount |

The SIR/SEIR CSV md5 differ because `solve_ivp`/`least_squares` land on a
slightly different point of a flat optimum on the two platforms. Numerically the
two ends agree to <= 1e-8 in beta, <= 1e-6 in R0 and <= 7e-5 in RMSE; the
deterministic growth/R0/CFR tables are byte-identical.

**Limitations.**

- Synthetic data; no real epidemic is analysed.
- One incidence curve cannot identify beta and gamma separately; use the fit for
  short-term interpolation only.
- The SEIR fit fixes sigma = 0.2; a free sigma would need a longer series.

## b56 — population-genetics panel on variant tables (2026-11-08)

**Data.** Four hand-built CSV tables in `workdir/b56_route/input` exercise the
population-genetics operators. They are synthetic and are **not** a real cohort.
`variants.csv` has 8 variants (chrom, pos, two population allele counts,
ref/alt read counts); `map.csv` has 6 intervals on chr1 from 0 to 8 Mb;
`genotype.csv` has 8 individuals x 6 markers (0/1/2); `phenotype.csv` has one
trait per individual.

| File | sha256 |
| --- | --- |
| variants.csv | `a3629ad75c970bcb1154eb4d0eef2a0896eb8b0ff2e59873f599189a73fc5b36` |
| map.csv | `30bce94e9aaac2cf5c145c7efeabc1b294118ae9bb87a577b26a8a32658a6e5e` |
| genotype.csv | `329befa65a0dc966d4df754798179ae57595e6bb50fb4cf4549dc893459a86e4` |
| phenotype.csv | `0ab5f3c866d0c173ba00d4d548e5c5a8863f66937b8d85fd805ff50aeb0fe64c` |

**Route.** Four `CsvReader` sources feed five operators; every operator ends in
`export_results`. 10/10 steps complete, no warnings.

**Results.**

| Output | Key values |
| --- | --- |
| fst_outliers.csv | Hudson Fst 0, 0, 0, 0.2234, 0, 0, 0.5712, 0; window z max 1.1547; no outlier at z > 1.5 |
| recombination_rates.csv | 1.10, 1.20, 0.733, 1.20, 0.75 cM/Mb; cumulative 7.9 cM |
| qtl_scan.csv | betas 0.9308, 0.5205, -0.8077, 0.4846, -0.4641, -0.9308; p 0.0083 ... 0.0083 |
| rrblup.csv | predicted 0.3671 ... 1.5949 for observed 0.1 ... 1.7 |
| allele_balance.csv | alt fractions 0.29 ... 0.50; 3 of 8 sites flagged imbalanced at binomial p < 0.01 |

**Oracle.** `workdir/b56_oracle.json`: 7/7 checks pass. Oracle A recomputes
Hudson Fst, recombination rate, QTL OLS and ridge rrBLUP with NumPy/pandas.
Oracle B uses `statsmodels` OLS for the QTL p-values and `scipy.stats.binomtest`
for allele balance; window z uses ddof=1 and the operator's n > 2 rule.

**Three-end.**

| End | Route | Hash comparison |
| --- | --- | --- |
| WSL (NumPy 2.1.3) | 10/10 complete | fst `e29eff9b8f79229b862f11c02cf8936f`, recomb `6d3e01311bf40a1976e8bb35ab56c663`, qtl `6458d31d9d7876536758ef7641c4fafe`, rrblup `f5c7a5e4383c0030f4ce54d6ca4b2321`, allele `3aaffd6c14b301ec7a13f2936e698331` |
| Windows 12.10 / NumPy 2.5.4 (D:\Operon) | 10/10 complete | all five md5 match WSL |
| srv | SKIP | `ssh srv` is not resolvable; no `/public/home/lihj` mount |

**Limitations.**

- Synthetic tables; no biological conclusion is drawn.
- Eight variants make the Fst window z unstable; the outlier threshold returns
  nothing on this toy set.
- Eight individuals give a very low-power QTL scan; p-values are illustrative.
- XP-EHH and iHS need phased haplotypes and were left in the matrix as future
  work rather than approximated from genotypes.

## b57 - genotype trio QC (VCF)

- Data: workdir/b57_route/input/trio.vcf, synthetic trio (6 variants, father/mother/child); sha256 f1a9521639bb572f43e773b2f683d460f8c0f89b0ccc4e8edaae5a9407500387. mode=synthetic.
- Command: PYTHONPATH=$PWD/library/seed:$PWD python scripts/run.py workdir/b57_route; 4/4 steps complete.
- Operators: genotype_mendelian_error (per-variant error flag and dosages; info n_tested=5, n_errors=2); genotype_call_rate_qc (per-sample called fraction with pass flag at 0.9).
- Values: errors v1=1, v6=1; v2-v4=0; v5 skipped (father missing). Call rate father 0.83333333 (pass 0), mother/child 1.0 (pass 1).
- Oracle: independent allele-set Mendelian check plus NumPy call rate; workdir/b57_oracle.json 5/5 pass.
- Three-end: WSL md5 6781c7da2617a3ddf81f69d11d141434 (mendelian) and 51843f2ee7947f37f4afce79bb6e6990 (call rate); Windows 12.10 md5 identical; srv SKIP (ssh srv unresolved).
- Limits: no phasing; unique sample labels required; multiallelic VCF sites are not split.


## b58 - chr22 peak interval panel

Data: ENCODE chr22 narrowPeak subset (3000 peaks) and a 4000-record chr22 GFF3
sample spanning 16.1-50.9 Mb; both are real public coordinates.

- peaks_chr22.bed sha256 `c39ece159273883681396fe5e889404f2bd42a3cd559523c89fa435221679972`
- genes_chr22.gff3 sha256 `ed8f0a5fe0559b1470b04da66dbef6c4fb10ea7dbb4eb211f2621066f56e6f62`
- chrom.sizes.csv sha256 `3866cd16129046387455112345cbb8caebb0187f338f4169858840caa4d94404`

Route: NarrowPeakReader + Gff3Reader + CsvReader -> peak_overlap_count,
peak_density_profile, peak_tss_distance -> export_results (CSV), 6/6 steps
completed on WSL and Windows.

| metric | value |
| --- | --- |
| peaks | 3000 |
| peaks overlapping a gene | 210 (0.07) |
| union overlap bp | 193828 |
| mean / median absolute TSS distance | 185509.0458 / 122855 bp |
| mean signed distance (center - TSS) | 3916.6608 bp |
| fraction within 1 kb / 5 kb | 0.006667 / 0.019667 |

Oracle: bedtools 2.31 intersect plus an independent NumPy nearest-TSS scan and
window aggregation agreed on n_overlapping, fraction, mean/median absolute
distance and both within-distance fractions (6/6 checks). `overlap_bp` is the
union per peak; the raw pair-sum from `bedtools -wo` is 10 bp larger because one
peak overlaps two gene records. The signed mean uses peak-center minus TSS with
no strand flip, matching a direct recomputation (3916.6608).

Cross-platform: Windows 12.10 / NumPy 2.5.4 produced byte-identical CSVs
(overlap `e1521be79a76ea0e4c09f7de25099f9d`, density
`54dec4c9222443cde7c54ed785b8fdb9`, tss
`d9486ad13b5c3c754e6ae18f3f2d60ab`). srv SKIP: `ssh srv` is not resolvable and
no `/public/home/lihj` mount exists.

Limitations: the GFF sample contains 93 gene records after type filtering, so
TSS distances are a sparse sample rather than a complete annotation; windows
before 16 Mb have zero peaks because the narrowPeak subset starts there.

## b59 — metagenomics parsing panel (synthetic fixtures)

**Scope.** Five operators that parse and summarise metagenomics tables with
deterministic arithmetic: `ani_from_kmers`, `checkm_quality_parse`,
`gtdb_taxonomy_parse`, `mlst_typing`, `pangenome_matrix`. The route uses
synthetic fixtures; it validates the arithmetic and contracts, not any biological
conclusion, and every table is marked synthetic here.

**Data.** `workdir/b59_route/input/`:
`kmers.csv` sha256 `8941fd3496e649863ae6a66079bcd0e02c79d417ed5cf1b0cbb9a536bf896045`,
`checkm.csv` sha256 `3c663b17862b92d19c3022f5fb20bde4d2a31363526e85b78afa774caf6bc6a9`,
`gtdb.csv` sha256 `d9449b52cdff02bb8d9c03b81aaab75783793758641732598008d8b0fa14c76f`,
`mlst.csv` sha256 `b762e4a4278c1357154b02a8fbe0c8b9588ead2bbabef64d3836634a039f8fb0`,
`pangenome.csv` sha256 `766f6fff532a2489ecc757695a9328a61caa824ec60fe2cb3195a7e876a35c04`.

**Command.** `PYTHONPATH=library/seed:. python scripts/run.py workdir/b59_route`
(preceded by `python -m operon registry build` and
`python scripts/build_builtin_packages.py --refresh`). 10/10 steps completed.

**Values (WSL).**
ANI: shared 700, union 1000, Jaccard 0.7, Mash distance 0.0092455245, ANI 0.9907544755.
CheckM: binA 92.5, binB 67.0, binC 24.5, binD 99.4 quality score.
GTDB classified taxa (of 4 genomes): d 4, p 3, c 3, o 3, f 3, g 2, s 2.
MLST: i1/i2/i6 ST 1, i3/i4 ST 2, i5 ST 3.
Pangenome: core 5, accessory 7, unique 3, pangenome 12, core fraction 0.4166667.

**Oracle.** `workdir/b59_oracle.json` recomputes every number from the raw
CSV inputs with the standard library only (set intersection and Mash formula
for ANI, `completeness - 5*contamination` for CheckM, prefix splitting for
GTDB, tuple enumeration for MLST, presence counts for the pangenome);
26/26 checks pass. Competitor references: Mash/ANI definition, CheckM2 quality
score, GTDB taxonomy strings, PubMLST allele-profile semantics, Roary/Panaroo
pangenome categories.

**Three-end.** WSL and Windows (`D:\Operon`, Python 3.12.10, NumPy 2.5.4)
produce byte-identical CSVs: ANI `78b532d21eff3a03b07bc8f02b222cb8`,
CheckM `6c1ab7237574801f2e6ff7d6cc10ed30`,
GTDB `dd5bbed2dc813f3f1e2f3dd08c3dbbef`,
MLST `dd4b3062dbfab11705b1d5b98dec79bd`,
pangenome `ffbcab4bab23686a2e947598f5b45bd7`. srv: SKIP, `ssh srv` is not
resolvable from this host (no matching Host block, no mounted `/public/home/lihj`).

**Limitations.** The fixtures are synthetic and small; ANI is a presence/absence
k-mer approximation (Mash-like distance), not a genome aligner; CheckM quality
uses the classic 5x contamination penalty without strain heterogeneity; GTDB
counts rank strings only and does not validate taxonomy against the release;
MLST assigns sequence types within the input table; pangenome categories are
presence/absence counts, not orthology calls.

## b60 — metagenomics summary panel (synthetic fixtures)

**Scope.** Five numeric summary operators: `kraken_kreport_parse`,
`bracken_reestimate`, `humann_pathway_abundance`, `metaphlan_profile_parse`,
`plasmid_contig_filter`. The route uses synthetic tables and validates the
arithmetic and contracts only; nothing here is a biological conclusion.

**Data.** `workdir/b60_route/input/`:
`kraken.csv` sha256 `436c53d4822d587c1b137697fbb124f9cc225b7dcabb8b1240a2c52019a0c98c`,
`bracken.csv` sha256 `475ffff2b535c4c0ecfefbc4513fdc105fc1c593421c7f17823453d297eee628`,
`humann.csv` sha256 `ea554e4fe5cb21a241593739dbfa9e8a9300e938d358e6d50312854873142105`,
`metaphlan.csv` sha256 `c957310c7fea54cb12a087ce58bd0460ede10bc3763235866bcb596cf7548b4d`,
`plasmid.csv` sha256 `251218b24d0fa74f3fc0610af4f805a00f863f4b58501557b1f41174e7262299`.

**Command.** `PYTHONPATH=library/seed:. python scripts/run.py workdir/b60_route`
after `python -m operon registry build` and
`python scripts/build_builtin_packages.py --refresh`; 10/10 steps completed.

**Values (WSL).** Kraken: total 175, species fraction 0.5714286, genus
fraction 0.8571429 (species included), max rank 6. Bracken: abundance
5e-05 per taxon, relative 0.5, 500000 per million. HUMAnN: total 100, mean
33.3333333, median 30, Shannon 0.8979457, top fraction 0.6. MetaPhlAn: rank
2/5/6 sums 0.2/0.3/0.5, n_taxa 1/2/1, Shannon 0.8979457. Plasmid filter:
contig 0 passes (5000 bp, depth 10), contig 1 fails (500 bp), n_pass 1,
bp_pass 5000.

**Oracle.** `workdir/b60_oracle.json` recomputes every value from the raw
inputs with the standard library only (sums, ratios, median, Shannon,
rank-grouping, threshold logic); 19/19 checks pass. Competitor references:
Kraken2 report format, Bracken re-estimation, HUMAnN pathway tables,
MetaPhlAn profile format, plasmid contig heuristics.

**Three-end.** WSL and Windows (`D:\Operon`, Python 3.12.10, NumPy 2.5.4)
produce byte-identical CSVs: kraken `45b7576799a0d036b840573b4ca767ef`,
bracken `58c9462435421ee6f176158cb786a618`,
humann `2b0774d8933c234208d318f9efc92b36`,
metaphlan `8425e6ff36007e65873ea393c66c480f`,
plasmid `0b9f9b184772968375e6ffa02d9cb745`. srv: SKIP, `ssh srv` is not
resolvable and no `/public/home/lihj` mount exists.

**Limitations.** Synthetic fixtures; Kraken genus fraction includes species
ranks; Bracken uses genome length rather than effective length; HUMAnN and
MetaPhlAn inputs are already normalized tables; the plasmid filter is a
length/depth heuristic with no replication or topology evidence.

### b67. LFQ matrix normalisation and missing-value filtering

**Data.** Synthetic protein-by-sample intensity matrix (6 proteins x 4 samples,
including missing and zero entries), `workdir/b67_route/input/intensities.csv`,
sha256 `a17aa26bf9f849c9e7181c8c33ab15802cd081da7a0505b1d2aa7ecb517379a3`.
The file is synthetic and is not a biological measurement.

**Route.** `workdir/b67_route` (`CsvReader` -> three operators -> three
`export_results`), 6 steps, all complete. Median normalisation shifts every
sample to the global median of sample medians (target 250.0) with factors
0.4/0.8/1.2/1.6 for the four samples. Quantile normalisation produces identical
sorted distributions in every sample, and the missing-value filter keeps
proteins whose missing fraction is at most 0.3.

**Values.** Median-normalised first row 250/250/250/250; quantile-normalised
columns share the same sorted profile; the filter keeps p1/p2/p3 of six
proteins. Full matrices are in the three exported CSV files below.

**Oracle.** `b67_oracle.py` recomputed medians and factors with NumPy (exact
match), checked the quantile-normalisation property that each column's sorted
finite values equal the shared reference profile (max delta 0.0), and recounted
the filtered rows. 4/4 checks pass; results in `workdir/b67_oracle.json`.

**Three-end.** WSL and Windows both ran the route to 6/6 steps. The three CSV
md5 values match across the two systems: `median_normalized.csv`
`48e4354c76d40932f9dbd126d5803ca7`, `quantile_normalized.csv`
`6ea33831395130f9bfe4621d96a69245`, `missing_filtered.csv`
`a13f82c7de0e9c8226d44d5de3cdf946`. The `srv` host remains unresolved
(`ssh srv` is not configured), so that end is SKIP.

**Limitations.** The operator normalises observed values only; it does not
impute missing intensities. Quantile normalisation breaks ties by row order.
The missing-value filter is a per-protein threshold and does not model
missing-not-at-random structure.

## b61 — Genome annotation table summaries

- **Batch**: b61 (5 operators, added 2026-11-08)
- **Inputs** (synthetic fixtures, mode=synthetic):
  - `genes.csv` sha256 `d207679dce28d5522693513c0709a4e78857c28060745f76fb5270ed158212b5`
  - `domains.csv` sha256 `9640fa37d0cc4e8c09aaac360fd3a012af5120dc4360ce5976c86072ab018ae7`
  - `markers.csv` sha256 `a3c9d81462845f472e622866a6bae72bd42bc785600cfa819a4778188b0328bb`
- **Route**: `workdir/b61_route`, CsvReader sources → 5 operators → 5 CSV exports, 10/10 steps complete.
- **Key values**:
  - gene lengths 1200, 1200, 200, 550, 3500, 300 bp; short flags 0,0,1,0,0,1.
  - gene overlaps 1,1,1,1,0,0; overlap bp 400,400,50,50,0,0.
  - domain summary p1 3 domains / 200 covered bp / mean 70 / best 1e-20; p2 1/80/80/1e-9; p3 1/55/55/2e-3.
  - Pfam architecture p1 3 domains, 2 unique, 1 switch.
  - completeness gA 0.75 (1 missing, 1 duplicated), gB 0.25 (3 missing).
- **Oracles**: pandas/NumPy independent recomputation (pairwise interval overlap, interval-union coverage, architecture switches) 14/14 pass → `workdir/b61_oracle.json`.
- **Three ends**: WSL 10/10 and Windows 12.10 (NumPy 2.5.4) 10/10 agree byte-for-byte on all five CSVs:
  - gene_length `e7f591a597f748d4c4f4940aa80d5657`
  - overlap `e3187503329919b6581999f6e843563d`
  - domain_summary `141d503ce6707cfccd9f3f4dac66bfda`
  - architecture `fe9a432ade3059d00533553b1d4e3c74`
  - completeness `37c230b3802b91cdf9ce6ca7dcecf5f1`
- **Remote**: SKIP — `ssh srv` does not resolve on this host and no `/public/home/lihj` tree is mounted.
- **Limitations**: overlap check is O(n^2) and intended for small annotation tables; domain coverage is the union of intervals, not the sum of lengths; architecture switches are adjacency changes in start order, not phylogenetically informed.

## b68 — LC-MS feature, isotope and neutral-mass matching panel

- **Data (synthetic)**: `workdir/b68_route/input/` — `profile.csv` (7 centroided peaks in two scans), `spectrum.csv` (3 peaks around the glucose [M+H]+ ion), `database.csv` (glucose, sucrose). The profile is a hand-built two-scan toy spectrum; it is not a biological measurement and is labelled `mode=synthetic` in this section.
  - profile.csv sha256 `3ecabe2359658cb2711e7b21ea9b0f40d8d7929ebf4fd1cf3d9eb305b281c447`
  - spectrum.csv sha256 `ea1032b4bc91b8b4b5614e068b786ca2104249d1575328c7f89eb1e9c303b029`
  - database.csv sha256 `6cd486ceae9cadb7e00378f204e01d02ac1c2ba697e52b3c1603155a170df474`
- **Execution**: `PYTHONPATH=$PWD/library/seed:$PWD python scripts/run.py workdir/b68_route` — 6/6 steps complete. Exports: `features.csv`, `isotopes.csv`, `matches.csv`.
- **Values**
  - features: two local maxima, m/z 100.1 (scan 1) and 200.1 (scan 2), both above the 100-intensity and 100-prominence thresholds.
  - isotopes for `C6H12O6`, z=1: M0 theoretical m/z 181.070666, observed 181.0712, +2.9465 ppm; M+1 theoretical 182.074021, relative abundance 0.064894 (observed isotope ratio 0.062).
  - match: glucose neutral mass 180.0634 gives [M+H]+ 181.070676; the observed 181.0712 feature differs by +2.8913 ppm and is the only database entry inside 50 ppm.
- **Oracle (6/6 pass, `workdir/b68_oracle.json`)**: an independent NumPy local-maximum scan reproduces the two features exactly; `pyteomics.mass` gives the monoisotopic and M+1 m/z and the M+1/M0 abundance. Comparison tolerances are 5e-6 Da for m/z and 0.1 ppm for the match because pyteomics and the operator use different proton/electron mass conventions (the raw deltas are 1.9e-6 Da, 2.06e-6 Da and 0.066 ppm).
- **Three-end**: WSL and Windows (`D:\Operon`, Python 3.12.10, NumPy 2.5.4) both complete 6/6 and produce identical MD5: features `3202b904f52c62945088b2d54cc218bc`, isotopes `a6fee330ff111dd3c4f097f6766c0f49`, matches `23a0c662e1a3542759e1e01059133db1`. Remote srv: SKIP — `ssh srv` does not resolve and no `/public/home/lihj` tree is mounted.
- **Limitations**: isotope rows can share one observed peak (several isotopologues fall inside the 50 ppm window); the first column of `features.csv` is the ordinal peak label, not a scan id; the isotope model ignores unresolved fine structure and uses nominal integer abundances.

## b63 - methylation beta / M value / DMR windows (synthetic counts)

- Data: `workdir/b63_route/input/counts.csv`, 12 synthetic probes on chr22, 20 reads each,
  sha256 `15b8be1673ed4a17c858a3c6b4386a5ff38729b4d86d952fa1eed5a042fc5447`. Synthetic (mode=synthetic); no biological conclusion.
- Route: CsvReader -> `methylation_beta_value`, `methylation_m_value`, `dmr_window_scan` -> `export_results` (6 steps, all complete).
- Values: probe 0 beta1=0.9 beta2=0.2 delta=0.7; probe 3 delta=0.4; M values m1=2.662965, m2=-1.765535.
  DMR windows (600 bp, min 2 probes): 100000-100600 n=6 mean 0.45 t=5.891883; 100600-101200 n=6 mean -0.15 t=-1.963961.
- Oracle: independent pure-Python recalculation from the CSV (beta, M, per-window mean and t) 80/80 checks pass
  (`workdir/b63_oracle.json`).
- Three-end: WSL and Windows (D:\Operon, py 3.12, NumPy 2.5.4) both 6/6; md5 match:
  betas `2027d795257ff75858940754e633ae99`, mvalues `921dfdd49dd2ab0a0360e35fd753712a`,
  dmrs `76db7910f4b1b1f0c2dd7916a2b10105`. srv SKIP (ssh srv unresolvable).
- Limitations: beta and M use pseudocount 1 for M only; DMR test is a per-window Welch-style t statistic,
  not a genome-wide multiple-testing procedure; no nucleosome or chromatin-state operator in this batch.

## b75 — causal inference panel (5 operators)

Synthetic panel data (mode=synthetic; parameters chosen for recovery tests, not biological claims).

Inputs (sha256):
- did.csv `cab9b2cc7421e3c48ea7efad1dfefc25cd95f8b826c983274fb2bc1b11cf16d5`
- did_panel.csv `c2b6adbafcc913347fa693ee4ae1d257137441296700f73453c9bc9004f4105e`
- synthetic_panel.csv `9474ca0fd070fa7335b2ef4b27bb9e03489b683a9c29cd6c579216583cc09d6f`
- aipw.csv `55d09e0d217e6134c64514cab9c6ba075e73e5cd14b6eb89a358a84525cdf80c`
- mediation.csv `e621f47b6b9d2cf43ae7a77dd839d1ea3781c14a90b1870e143e99addb5b4435`

Operators: difference_in_differences (HC1 interaction OLS), event_study (single-pass two-way within transform, event window -5..5, never-treated controls), synthetic_control (SLSQP simplex weights), doubly_robust_ate (logistic PS + linear outcome AIPW), mediation_analysis (product of coefficients with delta SE).

Route: 10/10 steps completed. Values: DiD 2.96482157; event_0 3.06341115; synthetic ATT 2.0 (pre_rmse 0, 10 pre / 6 post); AIPW 2.00652137; mediation ACME 1.38318348, direct 1.00627903.

Independent oracle: statsmodels OLS+HC1 for DiD, separate TWFE dummy regression for event study, SLSQP for synthetic control, statsmodels logit AIPW, OLS mediation — 7/7 pass (AIPW tolerance 0.01 because sklearn and statsmodels PS fits differ by ~0.0015).

Three-end: WSL 10/10; Windows 12.10 with NumPy 2.5.4, 10/10; all five CSV md5 match (did `e0118a93a14098c5b431731ba20901d8`, event `45e9a92b9666ee4045ae499fabf5c7d4`, synth `f3c0d14eabff7e8f5e566b02c71b050e`, aipw `dc59a450530b7ecad88393e0d0a0743e`, mediation `48494490f27fa97204024cd1507f3ee2`); srv SKIP (ssh alias unresolvable).

Limitations: synthetic_control weights are simplex-constrained and can be unstable with collinear donors; event_study requires a never-treated group and a window covering the post period; AIPW uses in-sample propensity scores (no cross-fitting).
