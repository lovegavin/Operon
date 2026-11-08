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

## Batch b73 - transcript isoform and splicing panel (5 operators)

**Status:** PASS on WSL and Windows; srv SKIP. **Mode:** synthetic tables (`workdir/b73_route/input`), no biological claim.

Operations: `splicing_psi`, `exon_skipping`, `intron_retention`, `alternative_polyadenylation`, `isoform_quantification_em` (two-input EM over an isoform x exon compatibility matrix).

### Inputs and checksums

| File | sha256 |
| --- | --- |
| psi.csv | a2a258f0f43cbef00fbc2cfa2a6cae889f2dd71b967ffd1e58f476256a052e5b |
| exon.csv | 3795b63b55c86a390aa57bc9dc7d7e4dbb22728b3a9a918e639b91c84f8c0326 |
| intron.csv | 42bdba0bea83b51ded242b25e0b8743580cf991c7d63750eab8d2e604e118974 |
| apa.csv | 93409bc2d4c8797baaa625815d551f7b9deb905d7e58ea8f0be92ac88be4fcc7 |
| compat.csv | ab39b809ff17f5d91d1c270a2f54cd0e0fd4bfb28d8bb432d01eb49f589bc029 |
| counts.csv | 25d514c672715670e5293ee32afe20516b61695ee0f1f8f6f3a690bda3cf2983 |

### Route

`PYTHONPATH=library/seed:. python scripts/run.py workdir/b73_route` - 10/10 steps complete.

| Output | Key values |
| --- | --- |
| psi.csv | PSI 0.75 / 0.10 / 0.00 / 0.90 (Wilson 95% CI in columns) |
| skipping.csv | exon PSI 0.75 / 0.25 / 0.50 / 0.889 / 0.0; gene-mean deltas 0.25 / -0.25 / 0 / 0.444 / -0.444 |
| retention.csv | intron retention ratio 1.0 / 0.0 / 1.0 (length-normalised densities) |
| apa.csv | proximal usage 0.90 / 0.50 / 0.05 (APA flag at |log2 ratio| >= 1) |
| isoforms.csv | EM fractions 0.5714 / 0.1786 / 0.2500; expression 85.714 / 26.786 / 37.500; nll -92.7904 |

### Oracle

Independent SLSQP maximum likelihood on the same compatibility matrix (SciPy) plus hand formulas for PSI, exon delta, intron ratio and APA usage (`C:\Users\Public\b73_oracle.py`). Agreement: PSI exact; intron/APA exact; EM fractions |delta| <= 5e-6, expression <= 0.003 (SLSQP tolerance), nll equal to 6 decimals.

### Three-end

| End | Result |
| --- | --- |
| WSL (NumPy 2.1.3) | 10/10; md5 psi `bbde082790ad63d453f4aa9dbd4dd243`, skipping `a35f7a15cdb3bae4914df02d5190c861`, retention `85143e02054403aa92306e93c13c2391`, apa `20f0a902b32f8a8b5a27880d3ddee2df`, isoforms `95b4203af7d40f0a47d75491c2ecaa2d` |
| Windows (D:\Operon, NumPy 2.5.4) | 10/10; the same five md5 values (all MATCH) |
| srv | SKIP: `ssh srv` unresolvable in this environment, no remote workspace mounted |

PSI intervals are rounded to 9 decimals because SciPy `beta.ppf` differs in the last bits between the two NumPy/SciPy builds; this is a formatting stabiliser, not a changed statistic.

### Limitations

- Tables are synthetic; the operator only implements the stated algebra.
- EM assumes a fixed isoform x exon compatibility matrix and does not model read fractions, biases or paired-end information.
- `alternative_polyadenylation` uses the proximal/(proximal+distal) definition and a |log2| flag; no 3' UTR annotation is inferred.

## b64 single-cell graph, clustering and batch mixing

Synthetic single-cell panel. `mode=synthetic`: the tables exercise the
implemented algebra and do not represent a biological conclusion.

Inputs (all synthetic):

| File | sha256 |
| --- | --- |
| `workdir/b64_route/input/pcs.csv` | `efc8951ebf6b1448e4a8b6bf28ed353ddefedceaec6ae2f7bd03ba8ea57bdb44` |
| `workdir/b64_route/input/counts.csv` | `8951493ba45a4579f5111352736051d916acd373d9d37b9b08c196c3d7355841` |
| `workdir/b64_route/input/groups.csv` | `b97b795c174326b78bd51bdd90b59e6db161fc16d6d56354ba033899946acf71` |
| `workdir/b64_route/input/batch.csv` | `c7ffbb2d0c00678a5fde236f1d6515f436fb887bce172019cb23859f4d4664d9` |

Route: `scripts/run.py workdir/b64_route` - 10/10 steps complete. Sources:
`CsvReader` for PCs, counts, groups and batch; the graph feeds kBET, iLISI and
Leiden clustering; counts and groups feed pseudobulk DE.

Values (6 cells, 2 batches, 3 neighbours):

| Step | Output |
| --- | --- |
| `sc_knn_graph` | 6x6 symmetric weights; self 0; 0-1 weight 0.3678794412 |
| `sc_batch_kbet` | cell 0 chi2 0.7357588823, p 0.3910228557, reject 0; cell 1 chi2 0.5032147244, p 0.4780909956 |
| `sc_batch_ilisi` | iLISI 1.0, normalized 0.0 for all six cells (two batches, pure neighbourhoods) |
| `sc_leiden_cluster` | clusters 0,0,0,1,1,1; degree 0.7357588823 / 0.5032147244 / 0.1353352832 |
| `sc_pseudobulk_de` | gene0 mean 11 / 21, log2fc 0.8744691179, Welch t -12.2474487139, BH q 0.001021 |

Oracle: `workdir/b64_oracle.json` (brute-force Euclidean KNN, NetworkX Louvain
vs Leiden, hand-computed Welch t) 5/5; `workdir/b64b_oracle.json`
(independent chi-square and inverse-simpson recomputation from the exported
graph) 3/3 with zero error.

Three-end comparison (same commit):

| End | Result |
| --- | --- |
| WSL, NumPy 2.1.3 | 10/10, md5 below |
| Windows, Python 3.12 / NumPy 2.5.4 | 10/10 after installing `igraph==1.0.0` and `leidenalg==0.12.0`; md5 identical |
| srv | SKIP: `ssh srv` does not resolve and no `/public/home/lihj` mount exists |

| Export | md5 |
| --- | --- |
| graph | `b532e0f62d1ef6cec4474608ff040dde` |
| kbet | `ccff2f0f53b7d7f04a4682fbafbdf9e5` |
| ilisi | `d3094cb286bd358a5fd247c31a8c1bee` |
| clusters | `0d1a40b4a42e51cec4b6f225120de7ce` |
| de | `d235e59ea1be65df3245e7e34450c9a2` |

Limitations:

- kBET here is a per-cell weighted chi-square against the global batch
  proportions, not the neighbourhood-sampling kBET of Buttner et al.
- Leiden uses igraph/leidenalg with a fixed seed; platform BLAS differences
  could change tie-breaking on larger graphs.
- Pseudobulk DE is a Welch t-test on two groups with BH correction; it does not
  model donors, covariates or zero inflation.

## b66 proteomics MS: spectrum library match, ion annotation, protein inference

Data (synthetic; not biological measurements):
- qpeaks.csv sha256 36d0ba65fe1c77a60192abf7bb6e640e74126765da5cb48b12f2943e184c207a
- lpeaks.csv sha256 3859a1bec40506a33799c8f686a1850125b81455bdd807cf57ddbcda8393af27
- peptides.csv sha256 e43e42630a4811e2b80a972d3b9552f2f04d73779cba64f319c0abe3761b63da
- apeaks.csv sha256 45bda9de690f482c60a63431f62e792716bd41c5098b76cc75f82d7c0b985ec4
- evidence.csv sha256 08a9e24ec0ceee92d2913c3af5551b23dcad85025cdd97b23ec602361757a89d

Route: CsvReader x5 -> spectrum_library_match, peptide_spectrum_annotation, protein_inference -> export_results (6/6 steps, 0.00 s compute).
Command: `PYTHONPATH=library/seed:. python scripts/run.py workdir/b66_route`.

Results:
- match: query 0 cosine 1.0, 3 matched peaks, mean ppm 0, library 0; query 1 cosine 1.0, 3 matched, 6.111066 ppm, library 0.
- annotation: peptide pep0 matched 12/12 b/y ions, coverage 1.0, mean absolute error 2.5e-06 Da.
- proteins: protein 0 2 peptides (1 unique, 1 shared), protein 1 2 (1 unique, 1 shared), protein 2 1 (1 unique).

Oracle (workdir/b66_oracle.json, 6/6 pass): independent pyteomics b/y ion masses (12/12 within 0.02 Da), explicit peptide-set arithmetic for inference, exact cosine for the identical library spectrum.

Three-end (same commit): WSL and Windows (py 3.12, D:\Operon) 6/6 steps; md5 match:
- match.csv 31d08e5315b1cde5d2d58398d5a86891
- annotation.csv 9139ff602e25e2195c36728e705e49df
- proteins.csv 28a3f98d12be661b8f388e586098bf18
srv: SKIP (ssh alias srv does not resolve; no /public/home/lihj mount).

Tests: tests/test_proteomics_panel_b66.py 3 passed (library cosine, 12 b/y ions, inferred peptide counts).
Limitations: library matching compares intensities of matched peaks by nearest m/z within tolerance and does not model fragment charge states; annotation covers singly charged b/y ions only; protein inference reports counts, not parsimonious protein sets.

## b72 phylogenetics: Fitch parsimony, MRCA and ultrametricity

Data: traits.csv sha256 from workdir/b72_oracle.json (4 taxa x 4 binary characters, synthetic).
Tree string (route parameter): `(A:1,B:2,(C:1,D:3):1);`

Route: CsvReader(traits) -> tree_parsimony_score (1 input); tree_mrca and tree_ultrametric (0 inputs) -> three export_results steps (6/6).
Command: `PYTHONPATH=library/seed:. python scripts/run.py workdir/b72_route`.

Results:
- parsimony: score 3, 4 characters, 1 parsimony-informative site.
- mrca(A, C): height 0 (root), tip distance 3.0, 4 descendant tips, 3 edges from root.
- ultrametric: is_ultrametric 0, root-to-tip range 3.0, min 1.0, max 4.0, cv 0.48432210.

Oracle (workdir/b72_oracle.json, 7/7 pass): dendropy 5.1.3 for MRCA height/distance and root-to-tip range; independent Fitch recursion plus the strict informative-site rule for parsimony.

Three-end (same commit): WSL and Windows (py 3.12, D:\Operon) 6/6; md5 match:
- parsimony.csv 3e86f218497b8840241120757a315857
- mrca.csv aebe23c55c38f9728ff5b3c481078989
- ultrametric.csv b59a0e71c12059444c1e1f40ef570766
srv: SKIP (ssh alias srv does not resolve).

Tests: tests/test_tree_panel_b72.py 3 passed.
Limitations: the Newick parser supports rooted trees with branch lengths, unquoted labels and no support values; parsimony uses equal-cost Fitch scoring and treats missing tip states as empty sets.

## b69 - immune repertoire clonotypes, diversity and CDR3 properties

Synthetic repertoire table (7 records, 96 counts across 5 clones) declared as
synthetic data. Input sha256 `dafd79a2bbcae619bfd2f1a80885af59a5af5d47c8fe643ffed3062e20c334ec`.

Three operators were exercised through `scripts/run.py workdir/b69_route`:
`bcr_clonotype` grouped by V gene and CDR3, `tcr_diversity` computed richness and
evenness indices, and `cdr3_properties` summarised residue composition.

| operator | principal values |
| --- | --- |
| bcr_clonotype | 5 clones; top clone 50 counts (0.520833); n_expanded 3 |
| tcr_diversity | observed 7; Shannon 1.52044; Simpson 0.72830; Chao1 7; Pielou 0.78135 |
| cdr3_properties | 7 sequences; length 13-16; one cysteine each |

Oracle: an independent pandas/NumPy recomputation of group sizes, Shannon,
Simpson, Chao1 and composition passed 9/9 checks (`workdir/b69_oracle.json`).

Three-end comparison: WSL and Windows produced identical CSV files
(`clonotypes.csv` md5 `f3399bce93365716d9bfa9690416f77c`, `diversity.csv`
`a57bf2e7b6e58a041b4edf5babfec9db`, `cdr3.csv`
`f47afff2717cdb472fe661490788c197`). The srv endpoint was SKIP because no SSH
profile resolves in this environment.

Limitations: CDR3 strings are grouped exactly, without junction trimming or
V(D)J alignment, and the diversity indices treat the input counts as clonotype
abundances rather than read counts.

## b71 - comparative genomics presence/absence panel

Synthetic presence/absence matrix (5 genomes, 8 genes) declared as synthetic.
Input sha256 `8d6164618b696df59946afe04e98f249c9b53bc1752274f6fdd5ca5bcff5b86a`.

| operator | principal values |
| --- | --- |
| core_genome_size | 2 core genes; A/B/C 5 present (0.4 core), D/E 4 present (0.5 core) |
| pangenome_curve | 4.5, 6.35, 7.05, 7.6, 8.0 genes for 1..5 genomes |
| ortholog_cluster | one identical pair (D,E); 4 clusters |

Oracle: independent pandas/NumPy recomputation of core counts, fractions, curve
endpoint and monotonicity, and identical-pattern clustering passed 8/8 checks
(`workdir/b71_oracle.json`).

Three-end comparison: WSL and Windows produced identical files (`core_genome.csv`
md5 `62a74abbd005cc4173db6680382a9302`, `pangenome_curve.csv`
`c0abcb9be00f76e32d153f5fea7e74ee`, `ortholog_clusters.csv`
`5c8da8b4ef073038458ba27da41bff1b`). srv was SKIP because no SSH profile resolves.

Limitations: clustering uses pairwise Jaccard on exact presence patterns; the
pangenome curve is a fixed-seed resampling estimate, not an extrapolated model.

## b68c: LC-MS adduct annotation, set enrichment and XIC extraction

Three `Metabolomics` operators validate `workdir/b68c_route` on synthetic LC-MS tables
(the data are synthetic and are not biological findings).

- `metabolite_adduct_annotation` maps feature m/z to neutral mass for positive
  [M+H]+/[M+Na]+/[M+NH4]+ or negative [M-H]- ions, then matches a neutral-mass
  database within `ppm_tolerance` (default 10).
- `metabolite_set_enrichment` overlaps detected metabolite ids with a set library
  and reports a hypergeometric p-value plus Benjamini-Hochberg q-value.
- `xic_extract` smooths an extracted-ion chromatogram, finds local maxima above
  `min_snr`, and integrates trapezoid areas around each apex.

### Inputs

| file | sha256 |
| --- | --- |
| `features.csv` | `b11c35db487cb2b93da14c2c1e8a4b8e1223ee73ee50783c57762e789471c8c6` |
| `database.csv` | `1a1befe1e5f67152b02a0d55d2036877595bc08fe564909fc77e3a041f95088f` |
| `hits.csv` | `b4b7d7744f3f34b81f36da0c5b3ce3ee4c66cb50c3fd92661278e977a8dec9fa` |
| `sets.csv` | `fa3d524714d3dd2265aaeb332cfb29eac15cf4bcd5738b307b2b44faabf631b3` |
| `xic.csv` | `15a01c8396e09c9546b5578a5947dd46bb6e17dafdc85d0a2a570da2fc4b466d` |

Command: `PYTHONPATH=$PWD/library/seed:$PWD python scripts/run.py workdir/b68c_route`.
All 6 steps completed.

### Numerical results

| operator | values |
| --- | --- |
| `metabolite_adduct_annotation` | f1 180.0633835 Da (0.0359 ppm, [M+H]+), f2 194.0803735 Da, f3 180.063392 Da ([M+Na]+), f4 194.080382 Da, f5 unmatched |
| `metabolite_set_enrichment` | setA size 4, overlap 3, expected 0.8, fold 3.75, p 0.01341589, q 0.04024768; setB 3/2 p 0.0877193; setC 3/0 p 1 |
| `xic_extract` | apex rt 3.0, intensity 100, area 159, start rt 1.0, end rt 6.0, snr 7 |

### Oracle

`workdir/b68c_oracle.json`: 8/8 checks pass. Neutral mass compared with
`pyteomics.mass.calculate_mass("C6H12O6")` (tolerance 1e-4 Da), the set p-value
recomputed from binomial coefficients, and the XIC area from the trapezoid rule
on the raw table. The oracle does not import the operators.

### Three ends

| end | route | md5 (adducts / enrichment / xic) |
| --- | --- | --- |
| WSL (NumPy 2.1.3) | 6/6 | `b3783e94abbf06ff60e4b59c12615250` / `b6b67cab8d90e8286d8d356b2df59fc1` / `762f6828cd9716d0dce6672b19e41bb1` |
| Windows (`D:\Operon`, NumPy 2.5.4) | 6/6 | same |
| srv | SKIP | `ssh srv` is not resolvable in this environment |

### Limitations

The feature table is synthetic. Adduct matching assumes one charge state and
the configured adduct list; in-source fragments and multiply charged ions are
out of scope. Set enrichment uses the detected metabolite count as universe
size unless the caller overrides it. XIC integration uses a symmetric apex walk,
not a peak model.

### b58b - microbial abundance table collapse (3 operators)

- Operators: `taxon_abundance_collapse`, `humann_pathway_collapse`, `metaphlan_profile_merge` (Metagenomics).
- Route: `workdir/b58b_route` (6 steps, 4 synthetic CSV inputs, marked synthetic in this record).
- Inputs (sha256): taxonomy `6c378dbefeb25f35b473697eb92f6d07cbcdb1bd07c88c968acf1f6efbfc7c1e`, pathways `69c04bb31b33a4bf420dfc6ff03b2af2358f8c9ea59c79251a501e3681aaabef`, profile_a `6553965c952b5658c0a961498bd4c9659813756f9536132f699c524b169aff32`, profile_b `2fcb81ae54272355f832c07cebf0a4b1343618b2cf50076f80d0cac6b7bf7b4a`.
- Results: family collapse f__F 15/27, f__F2 1/2, f__F3 3/3; pathway collapse PWY1 4/6, PWY2 5/5, unmapped 0/1; merge t1 1/2/0/0, t2 3/4/10/20, t3 0/0/5/6.
- Oracle: independent standard-library table arithmetic (6/6 pass).
- Three ends: WSL and Windows md5 equal - taxon `56b6bbe01b2aa834f86417db52d9de53`, pathway `56b26023a0492920667b470613feb5bf`, merged `d553ef6da907fc6cbea9f18cb0e5a681`; srv SKIP (`ssh srv` unresolvable).
- Limitation: rank collapse uses GTDB-style `d__/p__/...` prefixes; names without the requested prefix map to `unclassified`. Merge prefixes the left profile with `A:` to avoid duplicate sample names.

## b75b — population-genetics and retention-time panel (synthetic)

- Operators: `rt_alignment`, `selection_index`, `pedigree_inbreeding`.
- Route: `workdir/b75b_route`, six steps (three operators and three CSV exports).
- Data (synthetic, marked `mode=synthetic`): `rt.csv` sha256 `650dc26de4772bdad029707790305630b6453d2763d7f150e64352ea404edd72`; `sel.csv` sha256 `13804d10900863293cb553873035c7237382f04fec3f42798aa7e4686c3d29e0`; `ped.csv` sha256 `6f3c741b1b93683d09bcde3699b1a1bdf1f6f6fb08bfcbdb0a71f533dc080cd1`.
- Results: median RT shift 0.5 and aligned RT 3.1 for `f3`; selection composite 1.44295621 and rank 1 for `v3`; inbreeding coefficient 0.125 for the double-first-cousin offspring `i5`.
- Oracle: independent NumPy median/z-score/rank and a separate recursive kinship implementation; 6/6 checks pass (`workdir/b75b_oracle.json`), maximum delta 7.7e-10 (selection composite, tolerance 1e-6).
- Three-end: WSL and Windows 12.10 both 6/6; CSV md5 `rt_alignment` `9cad8c093ddc60ac28c8d5a6d79ba68c`, `selection_index` `1921e21fa2d5e66ef66bd12bbb732ef5`, `inbreeding` `29d50e7772d84de9fb3821df7136059d` are identical. The SSH host `srv` remains unresolvable, so that end is SKIP.
- Limitations: `rt_alignment` assumes a constant global shift; `selection_index` standardises each statistic independently and is a screening score, not a formal test; pedigree coefficients follow the standard recursive kinship definition and require parents ordered before offspring in the input table.

## b62b: MS2 spectral similarity and epitope panel (5 operators)

- Operators: `spectral_entropy`, `ms2_cosine_similarity` (two inputs), `ptm_localization_score`, `epitope_conservation`, `mhc_anchor_score`; shared helper `_b62b_common.py`.
- Route: `workdir/b62b2_route` (synthetic, six CsvReader sources, ten steps, five `export_results` steps); `scripts/run.py --check` OK and the run completed 10/10.
- Input sha256: peaks `cf717a05cbc5ef82e835e73849a74be2821a00f748882ca0c80494d28f907a94`; qpeaks `03d98bbe59f5fd82142d46f90965a60b5eb2c0a891d246231264506f0b426631`; lpeaks `637f17311584e6270b5e3e20a88c0cc06e5cbdf64feb145051e221974c942d1f`; psms `f34358bb682c0c5db9b7f6fa96e667f7d7971abd33c1f4e3564e7926e880e391`; epitopes `e08673b2a645e2a8e747934b39c5b7c00b645bca7d5f2946e8ef537da21e8b96`; peptides `8c5c919d2b1565bbc249b0f915e9f7ed032d10736e9ffafe879fdccae750b652`.
- Numeric results: spectral entropy s1 = 1.459148 (normalised 0.920620), s2 = 0.811278; MS2 cosine q1 = 1.0 (2 matched peaks), q2 = 1.0 (1 matched peak); PTM localisation probabilities 0.909091 (a), 0.666139 (b), 0.990099 (c); epitope conservation at position 5 entropy 0.918296, conservation 0.787526; MHC anchor scores for the two 9-mers are 0.
- Oracle: independent Python (standard library plus a direct cosine implementation) recomputed entropy, cosine similarity, PTM probability, per-position conservation and anchor hydrophobicity; 10/10 checks pass (`workdir/b62b_oracle.json`), tolerance 1e-9.
- Three-end: WSL and Windows 12.10 both complete the route; CSV md5 `entropy` `98bad9b7cbd59c796dc616cd836432e3`, `cosine` `a46ef31eb3b42ed24c129ce17124fe17`, `ptm` `c50852cbb2cf01bc82289d507f15fd4d`, `conservation` `b5c5951618c9f7b9d7ffe2f0c86cf73a`, `anchors` `0573ae425f189aa15bb244a9ef815949` are identical. The SSH host `srv` is still unresolvable, so that end is SKIP.
- Limitations: the MS2 cosine matches peaks greedily by nearest m/z within 10 ppm and is not a full spectral-library search engine; `mhc_anchor_score` only scores positions 2 and 9 of 9-mers and does not predict binding affinity; the synthetic inputs exercise the contracts, not biological conclusions.

## b71b: conserved gene order and genome rearrangement (2 operators)

- Operators: `conserved_gene_order` (Spearman rank correlation of two genome orders, inversion count) and `genome_rearrangement` (adjacency preservation, breakpoints, longest conserved block); shared helper `_b71b_common.py`.
- Route: `workdir/b71b_route` (synthetic six-gene table with one inversion); `scripts/run.py --check` OK and the run completed 4/4.
- Input sha256: `sha256sum workdir/b71b_route/input/syn.csv` = `9dcb5086e6485af86c61b2053cf908ca7f49951863feb14ac93df65072171d7b`.
- Numeric results: Spearman rho = 0.942857143, 6 genes, 1 inversion, inversion fraction 0.066666667; rearrangement fraction preserved 0.4, 3 breakpoints, longest block 3.
- Oracle: an independent Python implementation (rank correlation from sorted ranks and a separate adjacency scan) reproduced every value and the hand calculation (1/15 inversion fraction); checks are recorded in `workdir/b71b_oracle.json`.
- Three-end: WSL and Windows 12.10 both run 4/4; CSV md5 `order` `821d472e78e90e7bfde57c9fb7809117` and `rearr` `108a98e4cd08c9a07f3b00fdc94bad38` are identical. The SSH host `srv` is still unresolvable, so that end is SKIP.
- Limitations: both operators assume the two gene orders are already an ortholog table (one row per shared gene); they do not detect duplications, and the rearrangement score is an adjacency summary, not a phylogenetic reconstruction.

## b55 population-genetics panel (synthetic)

Route `workdir/b55_route`: five CsvReader sources, five operators and five exports (10/10 steps complete).
Synthetic genotypes/frequencies are marked `mode=synthetic`; they exercise arithmetic, not biological claims.
Inputs (sha256):

- `freq.csv` `5bbc04ccb04e06dd0c7530622cbaca9ae9c0f8977baf1f6ebea87b7564148f5f`
- `geno.csv` `6356bab30697b20743e81aeb8ac48b05820d3b78f5ffa1a3df9c5eb4caaa5229`
- `haps.csv` `fb0e4ecf9c2afa2d9d618227d89d55db8079366f43033faf0b13580a955f069c`
- `ibs.csv` `76013c50d540f961af254ffea1f2ea3922b8890d8215cebb13cf0ea32f54068d`
- `ld.csv` `958fc9acc93638cff9d295e089a9cbf9b85d1fac7591198e7233fdc06b23d67d`

Observed values:

| Export | Key numbers |
| --- | --- |
| `eps.csv` | v1 Fc 0.19047619, Ne 26.25; v2 Fc 0, Ne nan; v3 Fc 0.02285714, Ne 109.375 |
| `blocks.csv` | block1 100-300, 3 variants, mean r2 0.5; block2 400-500, 2 variants, mean r2 0.55 |
| `ibd.csv` | p1 and p2 each 1 segment, 200 bp, longest 200 bp |
| `roh.csv` | s1 and s2 each 1 ROH, 200 bp, span fraction 0.5 |
| `ihs.csv` | v2 iHS 1.181648085 (raw 0); v3 0.082065883 (raw -0.182321557); v4 -1.263713968 (raw -0.405465108); v1/v5 nan at the chromosome edges |

Oracles: `C:\Users\Public\b55_oracle.py` recomputes Fc/Ne, block runs, IBD spans, ROH runs and the
identity `raw_iHS = ln(iHH1/iHH0)` with the Python standard library only (13/13 checks, `workdir/b55_oracle.json`).
No external population-genetics CLI (plink2/selscan) was available for these synthetic tables, so this
remains a single independent implementation plus unit arithmetic, not a two-CLI oracle.

Three ends (same commit): WSL route 10/10; Windows `D:\Operon` with Python 3.12 route 10/10 after registry
rebuild (981 operators). Export md5 identical on both ends:
`eps` `8451858f977e8648ca0b51c7f48147fc`, `blocks` `f87dd277de37c08ffd5bae615f7f5b64`,
`ibd` `93277da1bc4a7d289a74b557b12f91ec`, `ihs` `dad65350028e31617210f421d43eeb63`,
`roh` `90c7481c2b3eddc6b08e06a6fcc2da9e`. srv SKIP (no ssh profile).

Limits: iHS is undefined at the first/last variant; haplotype blocks start a new block at every low-r2
break; IBD/ROH require at least `min_variants` consecutive markers; custom `row_names` labels are lost when
CsvReader deduplicates repeated key values, so pair/sample must stay as field columns.

## b62 - Epigenomics: peak annotation, overlap matrix, TSS enrichment, PWM scan, chromatin states

Route: `workdir/b62_route` (synthetic; 10 steps = 5 operators + 5 exports). Inputs sha256:

- `genes.csv`: `7d54aee23a93793c0304bf2237476afed9780c2cdfe1f245b4466fbf3e2a8354`
- `peaks.csv`: `220b6ca7fa616463c99e3ece22e57d7bdd4e5b04b756791aa63ba68d47a2f252`
- `pwm.csv`: `6517c69f53d4b995dc596507c93c90130f6437a77f30c1577a49c9453fbf271f`
- `seqs.csv`: `6bc3b99d070794457d5b80213042fbdead007553b7c38dc15c86b3c2f6a8eaf7`
- `track.csv`: `1f37040703c456fc860387d93fb92ce8902c51278c181bc8dbefdae046ef8702`

All 10 steps completed (`output/run_summary.json`). Export values:

| export | rows | key values |
| --- | --- | --- |
| annot.csv | 6 | nearest gene/distance: p1 -50, p2 -550, p3 +700, p4 0, p5 -400, p6 +800; n_same_chrom 2 |
| ovl.csv | 6x6 | p1-p2 100 bp, p1-p1 500 bp, p2-p2 700 bp; cross-chromosome pairs 0 |
| tss.csv | 10 bins | bins 0..9 by 1 kb; bin0 count 6 fraction 1.0 (all six peaks within 500 bp) |
| motif.csv | 3 | ACGTTGCA score 2.5 pos 0; TTGCAACG 2.5 pos 5; GGGTTTAA 0.9 pos 0 |
| chrom.csv | 3 | seg0 100-200 mean 0.3 state 0; seg1 300-400 mean 1.65 state 1; seg2 500-600 mean 0.2 state 0 |

Oracle: independent stdlib implementation (`C:\Users\Public\b62_oracle.py`, 79/79 pass, `workdir/b62_oracle.json`). PWM oracle reads a base x position matrix; TSS oracle uses the peak midpoint; chromatin oracle checks segment mean/state/length/monotonicity, not EM boundaries.

Three-end: WSL md5 equals Windows `D:\Operon` md5 for all five exports:

- `annot.csv`: `6c654e6c7d8732f710ed0aa16e810544`
- `chrom.csv`: `9e8bf27aa150790b9b0dd483f4d339ed`
- `motif.csv`: `0797160c08aa9b4f83c5a5af040b9906`
- `ovl.csv`: `8c6b73c12a4e392f2912a785fdc63c42`
- `tss.csv`: `2371c3903d9e6abf08c039cdf3f3c562`

srv SKIP (no ssh profile).

Limits: TSS distances use signed midpoint minus nearest TSS, so bins are 1 kb wide but only non-negative distances by design; motif scanning is a fixed PWM (no background model, no p-value); chromatin states are threshold segments, not ChromHMM emissions; overlap matrix is O(n^2) and intended for hundreds of regions, not genome-wide peak sets.

## b63 epigenomics: nearest-peak distance, nucleosome periodicity, motif enrichment

- Commit: this batch; branch `release/5.0`.
- Inputs (sha256): `peaks.csv` `323eccc975d2455bb0b4268defd2b342169e1afd467a1c702557e65e4af03196`, `signal.csv` `972d7ae887ebc6aa15e57e7c28d52eaa718c7cfbb91685cd00c34e1c4b7456c6`, `fg.csv` `a1bf55bcd40e68379535f15e3597a1f13be23b6bfe30f9acc58ddaa9c4ef9ef6`, `bg.csv` `a94129ffa95e4b2bd6469a369385aef06433a5d3029e2363e6de1513b6237cff`. Synthetic tables (`mode=synthetic`), not biological conclusions.
- Route `workdir/b63_route`: CsvReader -> `peak_peak_distance`, `nucleosome_positioning`, `motif_enrichment` -> three `export_results`; 6/6 steps complete.
- Values: nearest distances p1 100 (index 1), p2 100 (0), p3 0 (3), p4 0 (2), p5 1950 (2), p6 4150 (4); period `period_bp=100`, `strength=0.666887417`, `best_lag=10`, `n_lags=11`, `step_bp=10`; motif fg 3/6, bg 1/6, fold 3, odds ratio 5, Fisher p 0.272727273.
- Oracle: `C:/Users/Public/b63_oracle.py`, independent Python loops for nearest distances and autocorrelation plus a manual hypergeometric tail, 19/19 pass (`workdir/b63_oracle.json`); tolerance 1e-9.
- Tests: `tests/test_b63_panel.py`, 3 passed.
- Three-end: WSL and Windows (`D:\Operon`, py 3.12, registry 989) identical md5: near `f967b3fa0e90f6120514902e1bd1a93c`, period `362322da65dcbb364fd7a1f5692c02cb`, enrich `73edd9da769ea368508264991d44016b`. srv SKIP: `ssh srv` is not resolvable from this host.
- Limits: nearest distance is chromosome-blind (callers must split by chromosome); periodicity is autocorrelation on a uniformly spaced track and reports only the best lag in the requested window; motif enrichment counts exact substring occurrences and uses a one-sided Fisher test.


## b65 spatial transcriptomics: kNN graph, domains, Moran's I

- Commit: this batch; branch `release/5.0`.
- Inputs (sha256): coords `50bb60b7697e795628b67c95243f12e9da72d62f5e88c3ee8ed8ac9467db4939`, counts `f181d69431352bb55418532a8ba22f72358e9220441f57c936e553b27f135619`. Synthetic 8-cell grid (`mode=synthetic`).
- Route `workdir/b65_route`: CsvReader -> `sc_spatial_neighbors` (k=3), `sc_spatial_domains` (k=3, 2 domains), `sc_spatial_variable_genes` (Moran's I, k=3) -> three `export_results`; 6/6 steps complete.
- Values: kNN sigma 2.795445511; c1-c2 weight 0.923135395, c1-c3 0.93562284; domains c1-c5 domain 0 (purity 1.0), c6-c8 domain 1 (purity 0.333/0.333/0.667); Moran g1 0.203417751 (z 0.647821007, p 0.517100727), g2 -0.019121703, g3 0, g4 -0.315356655.
- Oracle: `C:/Users/Public/b65_oracle.py` recomputes the kNN weights (independent distance loops, median sigma), Moran's I and the k-means centroid fixed point; 3/3 pass, max deltas 4.9e-10 (weights) and 2.4e-10 (Moran), domain fixed point exact (`workdir/b65_route/oracle_b65.json`).
- Tests: `tests/test_b65_panel.py`, 3 passed.
- Three-end: WSL and Windows (`D:\Operon`, py 3.12, registry 992) identical md5: neighbors `93fe6af61c365a5002ed8e37d0d66ec6`, domains `a36e8151c0e8aba7a9d4f6e1bde583aa`, svg `5f0e60dd959c499ba4b475c574b03f93`. srv SKIP: `ssh srv` is not resolvable.
- Limits: sigma is the global median kNN distance; k-means uses farthest-first deterministic initialisation, not SpaGCN/Leiden; Moran's I uses a symmetric Gaussian weight matrix and a normal-approximation p-value.


## b65b CNV score, NNLS deconvolution and MHC anchors

- Commit: this batch; branch `release/5.0`.
- Inputs (sha256): expr `8d7423753b1a4a0be939c55722b114c08033311a252282268af2b05927875204`, arms `212a08d3dee7b47b39971c8e57aa864a07f790aab8081319c7a1ede71c1c523a`, bulk `090f3d14404341fd4bf97a1692bcb02f0a413f0fbb73cb5141de2ad52434021f`, sig `ecde37e25eae083372f80f78b1d744629167113b45f3ac0a84c6ee2347a42478`, peptides `3b89e8a5a0c61676f35527cd3a45a32f21a1fb1d09924e4f9a7bffc21fcb2284`. Synthetic (`mode=synthetic`).
- Route `workdir/b65b_route`: three CsvReader sources pair into `sc_cnv_score`, `sc_deconvolution`, `mhc_binding_motif`, each followed by `export_results`; 6/6 steps.
- Values: CNV cell0 0.971404521, cell1 0.908248290, cell2 0.945435403, cell3 0.908248290 (2 arms); deconvolution sample0 0.839347881/0.160652119, sample1 0.332447751/0.667552249, sample2 0.477299869/0.522700131; MHC ALMFGILMV 5, AAAAAAAAA 1, SLFNVYLLT 3, PEPTIDE 0.
- Oracles: `C:/Users/Public/b65b_oracle.py` recomputes arm-level absolute z-scores, a Lawson-Hanson NNLS, and the anchor score from definitions; all rows agree (deconvolution max delta 1.1e-16). `tests/test_b65b.py`: 3 passed.
- Three-end: WSL and Windows (`D:\Operon`, py 3.12, registry 995) identical md5: cnv `d26dbe008b30ca86c2772c7d0af9a141`, deconv `5e083019d8d7ab636468f54e0e4431c8`, mhc `4c4f935d0cbf45b06a306e28292a9a04`. srv SKIP: `ssh srv` unresolvable.
- Limits: CNV score needs an arm map and uses a z-score, not a segment/allele model; deconvolution uses unregularised NNLS; MHC anchors use a binary hydrophobicity rule, not a trained binding predictor.
## b72c — tree consensus, quartet support and root-to-tip dating

Operators: `tree_consensus`, `tree_quartet_support`, `tree_dating` (Phylogenetics,
protocol 3.7). Inputs are synthetic Newick strings, quartet expectations and tip dates.

Route: `workdir/b72c_route` (6 steps, CHECK OK, 6/6 complete).

Input SHA-256:
- trees.csv `bcb23d4e7496bbee0fc8575e5b339f68b1a70f5260186026b4fbd1b9d7e9cafa`
- quartets.csv `3beb09de5c20c2528c3a506d7285b59c4d8f678c9270580e9c675575ab7590c2`
- dates.csv `4393456f59c11f348f7865b5b24f605eef3dd5007d6da0542d45698771090c7b`

Exported values (CSV, LF):
- cons.csv: A|B support 1.0/count 2/size 2; C|D 1.0/2/2.
- quart.csv: A,B,C,D match 1/topo 0/expected 0; A,C,B,D 0/0/1; A,D,B,C 0/0/2; overall 0.333333333.
- dating.csv: slope 1.0, intercept 2.0, r2 1.0, n_tips 4.

Oracles: independent stdlib Newick parser and hand OLS in `C:/Users/Public/b72c_oracle.py`,
3/3 pass (`workdir/b72c_oracle.json`); consensus clades, four-point topology and
root-to-tip slope/intercept/r2 all exact to 1e-9.

Three-end:
- WSL: 6/6, md5 cons `3902d4739736db3b31a793b7cfd3743f`, quart `b1754f7a77ba17639dd88480fe9f761a`, dating `ad84acd3048575fdde97494163ece69c`.
- Windows (D:\Operon, py3.12, registry 998): 6/6, same three md5 MATCH.
- srv: SKIP, no ssh profile configured.

Limitations: quartet/dating use the first tree row only; no branch supports; synthetic
dataset; newline-normalised CSV.
## final — circRNA, RNA editing and de-novo motif discovery

Operators: `circrna_detect`, `rna_editing_detect` (Transcriptomics) and
`motif_discovery_em` (Epigenomics), protocol 3.7; synthetic inputs.

Route: `workdir/final_route` (6 steps, CHECK OK, 6/6 complete).

Input SHA-256:
- junctions.csv `45be01e1c4ee9b36795315a5d409387b52f59555c097d6f3919f7a6a08aac125`
- variants.csv `4d52d490d47c223ac1dbfe821d62557f9f50e0747bfb2eef46d131459b569fc6`
- seqs.csv `db9c8c4f905f1d03b3ff4c5dd00c8d038203983deeb12cbdf0c158134b359565`

Exported values:
- circ.csv: chr1:500-200 circular 1/length 301/ratio 0.5; chr1:100-400 0; chr2:900-700 1/201/1.0; chr2:100-200 0.
- edit.csv: chr1:100 candidate 1/fraction 0.4; chr1:200 1/0.375; chr2:300 0/0.333333333; chr2:400 1/0.0.
- pwm.csv: 6x4 PWM (position rows, A/C/G/T columns), row0 0.291666667/0.166666667/0.166666667/0.375.

Oracles: independent Python recomputation from the input CSVs (`C:/Users/Public/final_oracle.py`),
3/3 pass (`workdir/final_oracle.json`); circRNA/edit flags exact, PWM entropy-smoothed
counts exact to 1e-9.

Three-end:
- WSL: 6/6, md5 circ `ce5f3b3f4f3d9b3eba7eb7cadf15f465`, edit `76d91960d02aa136a65dc93035b13970`, pwm `814f489fec9b33d305c86c712ca92a45`.
- Windows (D:\Operon, py3.12, registry 1001): 6/6, same three md5 MATCH.
- srv: SKIP, no ssh profile configured.

Limitations: single-sample junction counts; A>G/T>C rule only (no strand-aware genome
reference); motif EM is a single-width PWM without E-step sequence assignment; synthetic data.

## Post-1001 hardening (2026-11-08)

- Full suite in the NumPy 2.1.3 venv: the first run after the last batch reported
  3639 passed / 223 skipped / 3 failed (36:31). After the fixes below the same
  suite reported **3642 passed / 223 skipped / 0 failed (36:51)**.
- Fix 1 (strand decoding): `peak_strand_bias` counted encoded digits because
  `_peak_common.decode_column` did not read the reader `LabelEncoder.inverse`
  dict. The helper now handles a dict inverse and `inverse_transform`; the b54
  test file passes again.
- Fix 2 (documentation contract): 76 operator pages written by later batches
  lacked the `## Purpose` section required by
  `tests/test_reference_docs.py`; the heading was added to each page.
- Fix 3 (timing): the remote handshake single-flight test passed in isolation;
  the failure in the long run is a timing flake and needed no code change.
- Restored `docs/verification/routes-5.x.md`: several patch scripts had written
  the file in truncate mode, leaving 71 lines. The file now carries 1290 lines
  and 33 chapters, rebuilt from commits `5ff2e82b`, `22e36bf3`, `b175b923`,
  `3426e450` and `01dfd9ef`.
- Registry after the fixes: 1001 operators, 0 errors. Windows (D:\Operon,
  py -3.12) reports the same count and no errors.

## b76 structure geometry and metagenomic transforms (post-1001)

Route `workdir/b76_route`: PdbReader `1mel.pdb` -> `structure_radius_of_gyration`;
CsvReader `counts.csv` (4 samples x 5 taxa) -> `metagenomics_bray_curtis` and
`metagenomics_clr`; every branch ends in `export_results`. Six of six steps
completed. Inputs sha256: `1mel.pdb`
`321aa847a20535c018b12cf340d2e057628dce42b4005c185916dd17bdd24de4`, `counts.csv`
`5c30d20a6f09d908b7087a0a90d9435d3e3c1b4bf1afd57ec988e3964dd9bc67`.

Exported values:

- `rg.csv`: n_atoms 3941, radius_of_gyration 28.961269387 A, max_radius
  56.218888183 A.
- `bc.csv`: s1-s2 0.714285714, s1-s3 0.62962963, s1-s4 0.5, s2-s3
  0.904761905, s2-s4 0.461538462, s3-s4 0.6; diagonal 0.
- `clr.csv`: s1 row 1.634151313 / -1.410371125 / 0.987524148 / -1.410371125 /
  0.199066788; every row sums to zero.

Oracles (independent): mdtraj 1.11.2 `compute_rg` (2.896126939 nm, converted to
angstrom) and a standalone NumPy coordinate loop for Rg; `scipy.spatial.distance`
`braycurtis` plus an explicit ratio loop for Bray-Curtis; a closed-form log-ratio
calculation for CLR. Eight of eight checks passed (maximum deviation 4.7e-10 on
Bray-Curtis, 4.1e-10 on CLR).

Cross-end: Windows (D:\Operon, py -3.12, registry 1004) ran the same route
6/6. Export md5 `rg.csv` `8d2badc2d20e0adc864f3f6ee0af0cbf`, `bc.csv`
`a5b1c85eb5f739b202b57a39b998316b`, `clr.csv`
`1c25604cdc66b66d9105a1366ffaca98`, identical on WSL. `srv` SKIP: the SSH
alias is not configured. Limitations: Rg includes every ATOM/HETATM record in
the file (no hydrogen filtering); CLR uses a fixed caller-supplied pseudocount;
Bray-Curtis rejects negative abundance tables.


## b77 iBAQ, CAI and PTM occupancy (post-1001)

Route `workdir/b77_route` (6 steps, 4 CsvReader sources, synthetic data labelled
mode=synthetic) exercises three operators:

| operator | output | observed values |
| --- | --- | --- |
| proteomics_ibaq | ibaq.csv | P1 n_peptides=2 total=200 iBAQ=100; P2 n_peptides=1 total=220 iBAQ=220 |
| sequence_cai | cai.csv | S1 n_codons=3 n_effective=2 CAI=0.632455532; S2 3/2/0.565685425 |
| ptm_occupancy | occupancy.csv | S1 0.8; S2 0.0; S3 nan (no unmodified counts) |

Inputs (sha256):

- peptides.csv `afadd6c107571cf7e51150dcc7d0c7d180e26ea89b32c521267c3d15f431091f`
- cds.csv `020c9301f553c2d61469425247c0adfc01f6147796b284a0a33f48af39db1b2f`
- weights.csv `b03ca685782d5955f0c8c059a3f18d1c3cb987341631c84512a7784b1046bfbd`
- ptm.csv `85186c34d1717d44b66514efaa4277fd1bbfcc2d7f42f7d852ec7cf99ed4f584`

Oracles: independent stdlib recomputation (distinct-peptide grouping, codon
table and explicit geometric mean, occupancy ratio) passed 15/15 numeric
checks (`workdir/b77_oracle.json`); unit tests 4 passed in `tests/test_b77.py`.

Three-end: WSL route 6/6 and Windows (D:\Operon, Python 3.12) route 6/6 with
identical export md5:

- ibaq.csv `6477ebdfbdea8b4dce9e3ec86ec8ae62`
- cai.csv `6b1823e0db0b3b3ffc8696a87c24a2d8`
- occupancy.csv `93bc472c99475baba7a3eec38f1075fb`

The `srv` host remains SKIP because no SSH profile resolves in this session.
Limits: synthetic peptide and CDS tables; iBAQ uses observed peptide counts,
not tryptic digest prediction; CAI uses the supplied reference weights only;
occupancy is a closed-form ratio without intensity normalization.

## b78 JC69 likelihood and outgroup rooting (post-1001)

- Inputs: `workdir/b78_route/input/tree.csv` sha256 `a03719d30cdff41dc6adfc23742d9472ad9da53d5a9d2ccbc3a168778da53aba`;
  `workdir/b78_route/input/aln.csv` sha256 `8b34146c8627f0a4dc239ca746ad7fc8d00b603fd5e72b76ff8eb34481acbeca`.
- Route: 4 steps (2 operators, 2 exports), all complete.
- Values: JC69 log-likelihood `-18.416477967` (4 taxa, 6 sites); per-site values
  `-2.627699768` (x4) and `-3.952839448` (x2). Outgroup rooting on taxon A:
  n_tips 4, root_degree 2, outgroup_branch 0.1, rooted tree starts `(A:0.1`.
- Oracle: `workdir/b78_oracle.json` (brute-force enumeration of 4^3 internal states
  plus explicit root prior) 10/10 values match; DendroPy rerooting agrees on tip count
  and root degree.
- Exports: `jc69.csv` md5 `1127cc3d21747783364e04188393b38f`; `rooted.csv` md5
  `9ae48dd645b8e32615463f1c32ae0773`. Windows (`D:\Operon`, py 3.12, registry 1009)
  route 4/4 and both md5 values match WSL.
- The `srv` host remains SKIP because no SSH profile resolves in this session.
- Limits: fixed-tree JC69 only (no rate variation, no model search); rooted trees are
  re-rooted on the outgroup branch without branch-length re-estimation; synthetic
  6-site alignment.

## b79 methylation conversion, allele-specific methylation and Robinson-Foulds (post-1001)

- Operators: `bisulfite_conversion_rate`, `allele_specific_methylation`,
  `tree_robinson_foulds` (+ shared `_b79_common.py`). Registry 1012 operators,
  0 errors.
- Route: `workdir/b79_route`, four synthetic CSV inputs, 6/6 steps complete.
- Inputs (sha256): `bisulfite.csv`
  `f813e7714cb83c8304785d0b35a6ed98a87ddf9954f6278b59980cc85c21222f`,
  `asm.csv` `c8d322ef6727e7e9069da311403b88fd2f7d1571a3bacc9e976836d5b06498aa`,
  `tree_a.csv` `9dc19c0fb50f525aa46e0e521b90978305c7584fd63a8b91cbd8dfde481c306c`,
  `tree_b.csv` `e7b43d24db493eeab9ebe58b425e37cc4202c4ed7cca1fb23706c99439f0b83d`.
- Values: conversion `n_sites 5, converted 84, unconverted 16, rate 0.84,
  Wilson CI 0.7557973061-0.8990471151`; ASM `n_sites 4, n_tested 4,
  n_significant 1, mean_abs_diff 0.275, min_p 0.0010933339`; RF `rf 2,
  max_rf 2, normalized_rf 1.0, n_taxa 4` (one split each, no shared split).
- Oracle: `workdir/b79_oracle.json`, 9/9 checks. Wilson interval from
  statsmodels `proportion_confint`, ASM p-values from `scipy.stats.fisher_exact`
  with an explicit BH loop, RF from DendroPy 5.1.3
  `treecompare.symmetric_difference` with a shared taxon namespace.
- Windows (D:\Operon, Python 3.12): registry 1012, route 6/6; export md5 equal
  to WSL for `conversion.csv` `0a998059f5ccae9a75c269d67e2b09c2`, `asm.csv`
  `2eeb9383388073b004e672ceaeff895f`, `rf.csv`
  `8de952e01d55a5afe0d41623d7ef9f25`.
- srv: SKIP, no reachable SSH profile in this environment.
- Limitations: synthetic count tables; conversion assumes a single conversion
  probability per cytosine; ASM ignores read phasing; RF ignores branch lengths
  and root position.

## Three-end environment check (post-1001, app 3.0.2 / SDK 3.7.0)

The post-1001 batches were re-checked against the pinned application versions:
`operon 3.0.2` with `operon_sdk 3.7.0` on both WSL (`/home/gavin/bp-numpy21`)
and Windows (`D:\\Operon`, `py -3.12`). The Windows registry contains the same
1012 operators and zero errors.

Route `workdir/b79_route` was re-run on both hosts after merging the restored
`_phylo_common` API with the b78 likelihood helpers. Export md5 values are
identical:

| Export | md5 (WSL = Windows) |
| --- | --- |
| asm.csv | 2eeb9383388073b004e672ceaeff895f |
| conversion.csv | 0a998059f5ccae9a75c269d67e2b09c2 |
| rf.csv | 8de952e01d55a5afe0d41623d7ef9f25 |

The `srv` host could not be reached in this session. From Windows OpenSSH,
`ssh srv` resolved to 172.22.148.93 but the TCP connection timed out, and ICMP
echo failed; the `/public/home/lihj` workspace was therefore not available.
This endpoint is recorded as SKIP (network unreachable), not as a passing
result, and no srv numbers are reported.

## Post-1001 route: b80 GTR likelihood and MS2 spectral angle

Synthetic, deterministic inputs (row-oriented CSV; `mode=synthetic` for all tables).

| Input | sha256 |
| --- | --- |
| `workdir/b80_route/input/tree.csv` | `cf45e74d17a7a4a2a37b449ef5f27358a4d61d4b2dc6bc17c98264eba127b203` |
| `workdir/b80_route/input/aln.csv` | `4b837c2298989f5aec62e83af18ebb4005401934b9fdf3999bab869491331082` |
| `workdir/b80_route/input/qpeaks.csv` | `45e8dacd10dcc753ba792430e21aa8b182dd1b7e7b31e42cd19b2f02a160fb07` |
| `workdir/b80_route/input/lpeaks.csv` | `b496c1f85a1b7a1d2fb1ef26bab2b6b5ff100872bfa04c3f1a2b73d632598629` |

Route: `tree.csv` -> `phylogenetics_gtr_likelihood` -> export; `qpeaks.csv` + `lpeaks.csv` ->
`ms2_spectral_angle` -> export. CHECK OK, 4/4 steps complete (0.78 s on WSL).

Values: GTR log-likelihood `-19.315181699` (4 taxa, 6 sites); spectral angle `45.0` degrees,
cosine `0.707106781`, 2 matched peaks.

Oracle: an independent script builds GTR transition matrices with `scipy.linalg.expm` and
enumerates all 4^3 internal-node states (log-likelihood -19.31518169927482, absolute difference
2e-15); the spectral angle is recomputed manually from square-root intensities. 2/2 pass.

Cross-platform: WSL (NumPy 2.1.3) and Windows (NumPy 2.5.4) md5 are identical after rounding the
likelihood to 9 decimals: `gtr.csv` `715659b6ecac729f614e82a7b85a6e92`, `angle.csv`
`5f7ad0f2a60a1b5a55db427719268153`. srv SKIP: 172.22.148.93:22 times out and ICMP is blocked.

Limitations: one fixed tree topology, one rate matrix; no rate-category mixture, no tree search.

## srv three-end verification (post-1001)

The srv host became reachable after the earlier SKIP, so the five post-1001 routes
were re-run there on the same commit as WSL and Windows. All 13 exported tables
matched byte for byte.

- Host: `srv` (lihj), repository `/public/home/lihj/Operon-verify`
- Commit: `c3d16930` (route inputs tracked after the first srv attempt exposed the
  repository `input/` ignore rule)
- Python: 3.11.18 in `/public/home/lihj/operon-venv311`; numpy 2.2.6, scipy 1.14.1,
  pandas 2.2.3, pydantic 2.14.3
- Command: `PYTHONPATH=$PWD /public/home/lihj/operon-venv311/bin/python scripts/run.py library/seed/routes/<bundle>` (plus `workdir/b80_route` for the b80 check)
- WSL/Windows values are those recorded in the b76-b80 sections above.

| route | export | md5 (srv = WSL = Windows) |
| --- | --- | --- |
| structure_rg_metagenome | rg.csv | `8d2badc2d20e0adc864f3f6ee0af0cbf` |
| structure_rg_metagenome | bc.csv | `a5b1c85eb5f739b202b57a39b998316b` |
| structure_rg_metagenome | clr.csv | `1c25604cdc66b66d9105a1366ffaca98` |
| proteomics_ibaq_cai_ptm | ibaq.csv | `6477ebdfbdea8b4dce9e3ec86ec8ae62` |
| proteomics_ibaq_cai_ptm | cai.csv | `6b1823e0db0b3b3ffc8696a87c24a2d8` |
| proteomics_ibaq_cai_ptm | occupancy.csv | `93bc472c99475baba7a3eec38f1075fb` |
| phylogenetics_jc69_rooting | jc69.csv | `1127cc3d21747783364e04188393b38f` |
| phylogenetics_jc69_rooting | rooted.csv | `9ae48dd645b8e32615463f1c32ae0773` |
| methylation_conversion_asm_rf | conversion.csv | `0a998059f5ccae9a75c269d67e2b09c2` |
| methylation_conversion_asm_rf | asm.csv | `2eeb9383388073b004e672ceaeff895f` |
| methylation_conversion_asm_rf | rf.csv | `8de952e01d55a5afe0d41623d7ef9f25` |
| b80_route | gtr.csv | `715659b6ecac729f614e82a7b85a6e92` |
| b80_route | angle.csv | `5f7ad0f2a60a1b5a55db427719268153` |

Limitations: the srv run used the same small synthetic inputs as the WSL and
Windows runs; it validates numeric reproducibility across Python 3.11/3.12 and
numpy 2.2/2.1/2.5, not full-scale data behaviour.

## Classic route bundles (post-1001)

Two additional classic pipelines were packaged as route bundles and executed on
WSL, srv and Windows from commit `222c2104`. All eight exported tables matched
exactly on the three hosts.

- `population_selection_scan`: effective population size, LD haplotype blocks,
  iHS selection, IBD segments and ROH runs (operators from b55).
- `noncoding_rna_editing`: back-splice circRNA detection, RNA-editing candidate
  scoring and a motif PWM (operators from the final 1001 batch).

srv used `/public/home/lihj/operon-venv311` (Python 3.11.18) and the same
`scripts/run.py <bundle>` entry point as WSL and Windows.

| route | export | md5 (WSL = srv = Windows) |
| --- | --- | --- |
| population_selection_scan | eps.csv | `8451858f977e8648ca0b51c7f48147fc` |
| population_selection_scan | blocks.csv | `f87dd277de37c08ffd5bae615f7f5b64` |
| population_selection_scan | ihs.csv | `dad65350028e31617210f421d43eeb63` |
| population_selection_scan | ibd.csv | `93277da1bc4a7d289a74b557b12f91ec` |
| population_selection_scan | roh.csv | `90c7481c2b3eddc6b08e06a6fcc2da9e` |
| noncoding_rna_editing | circ.csv | `ce5f3b3f4f3d9b3eba7eb7cadf15f465` |
| noncoding_rna_editing | edit.csv | `76d91960d02aa136a65dc93035b13970` |
| noncoding_rna_editing | pwm.csv | `814f489fec9b33d305c86c712ca92a45` |

Limitations: inputs are small synthetic tables, so these two bundles demonstrate
numeric reproducibility and pipeline wiring, not biological conclusions.
