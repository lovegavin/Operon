# Competitor capability gap matrix, v2 (post-1001)

This follow-up matrix records capabilities that remain absent after the 1001
operator milestone. A row is actionable only when public data and at least two
independent implementations (or one implementation plus a closed-form check)
exist. Rows that cannot meet that bar are marked `blocked` with the reason.

| Capability | Competitor reference | Existing Operon operator | Gap | Priority | Data and oracle | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Radius of gyration | MDTraj `compute_rg` | none | whole-structure Rg and max radius | high | 1mel.pdb; mdtraj vs NumPy loop | implemented b76 |
| Bray-Curtis dissimilarity | scikit-bio `braycurtis`, vegan | none | pairwise sample matrix | high | synthetic 4x5 counts; scipy vs explicit loop | implemented b76 |
| Centered log-ratio | scikit-bio `clr`, vegan | none | compositional transform | high | same count table; closed form vs row-zero check | implemented b76 |
| JC69 likelihood | IQ-TREE, RAxML | distance-only tree utilities | site-pattern likelihood on a fixed tree | high | Newick plus alignment; pruning vs brute-force enumeration | implemented b77 |
| Outgroup rooting | ETE3, DendroPy | midpoint rooting only | root a tree on a named outgroup | medium | rooted/unrooted Newick pair; DendroPy vs manual path walk | implemented b77 |
| iBAQ abundance | MaxQuant | LFQ rollup | intensity divided by observable peptides | medium | peptide table; explicit sum vs MaxQuant formula | implemented b77 |
| Codon adaptation index | EMBOSS `cai` | codon usage and RSCU | reference-set CAI per sequence | medium | CDS FASTA plus reference weights; Bio.SeqUtils vs explicit geometric mean | implemented b77 |
| PTM occupancy | MaxQuant | ptm_localization_score | site occupancy from modified/unmodified intensities | medium | synthetic peptide intensities; closed-form ratio | implemented b77 |

Blocked rows are not implemented because no public reference dataset and no
independent second implementation are available inside this workspace: GPU
folding (AlphaFold3/Boltz/Chai), long-timescale MD engines (GROMACS/AMBER),
atlas-level deconvolution, clinical variant interpretation, assembler
benchmarks (MEGAHIT/metaSPAdes), GPI-anchor prediction, Boman/N-end sorting
signals and O-GalNAc glycosylation.
