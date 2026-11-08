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
| JC69 likelihood | IQ-TREE, RAxML | distance-only tree utilities | site-pattern likelihood on a fixed tree | high | Newick plus alignment; pruning vs brute-force enumeration | implemented b78 |
| Outgroup rooting | ETE3, DendroPy | midpoint rooting only | root a tree on a named outgroup | medium | rooted/unrooted Newick pair; DendroPy vs manual path walk | implemented b78 |
| iBAQ abundance | MaxQuant | LFQ rollup | intensity divided by observable peptides | medium | peptide table; explicit sum vs MaxQuant formula | implemented b77 |
| Bisulfite conversion rate | Bismark `--directional`, Illumina methylation | none | conversion efficiency with interval | high | synthetic C counts; statsmodels Wilson vs closed form | implemented b79 |
| Allele-specific methylation | Bismark ASM, SNPsplit | none | per-SNP Fisher test with BH | high | synthetic allele counts; scipy Fisher vs explicit loop | implemented b79 |
| Robinson-Foulds distance | DendroPy, ETE3, RAxML | none | split-set distance between two trees | medium | 4-taxon Newick pair; DendroPy symmetric_difference vs bipartition walk | implemented b79 |
| Codon adaptation index | EMBOSS `cai` | codon usage and RSCU | reference-set CAI per sequence | medium | CDS FASTA plus reference weights; Bio.SeqUtils vs explicit geometric mean | implemented b77 |
| PTM occupancy | MaxQuant | ptm_localization_score | site occupancy from modified/unmodified intensities | medium | synthetic peptide intensities; closed-form ratio | implemented b77 |

Blocked rows are not implemented because no public reference dataset and no
independent second implementation are available inside this workspace: GPU
folding (AlphaFold3/Boltz/Chai), long-timescale MD engines (GROMACS/AMBER),
atlas-level deconvolution, clinical variant interpretation, assembler
benchmarks (MEGAHIT/metaSPAdes), GPI-anchor prediction, Boman/N-end sorting
signals and O-GalNAc glycosylation.

## Family coverage (28 competitor families)

The table records, per competitor family, whether the capability is covered by
existing operators, implemented in b76-b81, or blocked with a concrete reason.
"Covered" means an operator already existed before the post-1001 expansion.

| Family | Competitor reference | Representative capability | Operon status | Evidence |
| --- | --- | --- | --- | --- |
| Sequence similarity search | BLAST+ 2.16, DIAMOND 2.1, HMMER 3.4 | local alignment, profile search | covered | sequence alignment and HMM wrapper operators |
| Multiple sequence alignment | MAFFT 7.5, MUSCLE 5 | progressive MSA | blocked | no MSA binary in the environment and no independent aligner oracle |
| Phylogenetics | IQ-TREE 2.3, RAxML-NG 1.2 | substitution-model likelihood, support | implemented b72c-b78/b80 | JC69/GTR likelihood, consensus, quartet support, dating, RF distance |
| Population genetics | PLINK 2.0, ADMIXTURE 1.3 | Fst, PCA, pruning, ROH | implemented b55-b57 | 14 population-genetics operators with PLINK/bcftools oracles |
| Molecular evolution (classical) | PAML 4.10, DnaSP 6.12 | dN/dS, haplotype diversity, mismatch distribution | implemented b81 | Nei-Gojobori + JC dN/dS, haplotype statistics and mismatch distribution with independent oracles |
| Variant annotation | VEP 112, SnpEff 5.2 | transcript consequence annotation | blocked | no cached annotation database; no offline oracle |
| Clinical variant interpretation | ClinVar 2024, ACMG rules | pathogenicity classification | blocked | no labelled clinical truth set; rule engine has no independent oracle |
| Structural bioinformatics | MDTraj 1.11, DSSP 4 | geometry, contacts, SASA | implemented b76/b78 plus existing | Rg, SASA, disulfides, salt bridges, pocket detection |
| Docking | AutoDock Vina 1.2 | pose scoring | blocked | Vina binary and receptor preparation tools are absent |
| Molecular dynamics | GROMACS 2024, OpenMM 8.1 | trajectory analysis | blocked | no MD engine or trajectory data; GPU not available |
| Cheminformatics | RDKit 2026.09 | descriptors, fingerprints, fragmentation | covered | 10 chemistry operators |
| Proteomics quantification | MaxQuant 2.6, Skyline | LFQ, iBAQ, PTM occupancy, spectral similarity | implemented b66/b77/b80 | iBAQ, PTM occupancy, spectrum matching, protein inference, spectral angle |
| Metabolomics | XCMS 4, MZmine 3 | adduct/feature annotation, XIC | implemented b68 | adduct annotation, set enrichment, XIC extraction |
| Metagenomics | Kraken2 2.1, HUMAnN 3.9, MetaPhlAn 4 | taxonomic and pathway profiling | implemented b58-b60 | kreport/bracken/HUMAnN/MetaPhlAn parsers, abundance collapse |
| Metagenome assembly | MEGAHIT 1.2, metaSPAdes 3.15 | contig assembly and binning | blocked | assembler binaries absent and no assembly truth set |
| Single-cell transcriptomics | Scanpy 1.10, Seurat 5 | graph, clustering, markers, spatial | implemented b64-b65 | kNN, Leiden, pseudobulk DE, CNV, deconvolution, spatial domains |
| Epigenomics | MACS3 3.0, Bismark 1.22, TOBIAS 0.16 | peak calling, methylation, footprints | implemented b53-b54/b62-b63/b79 | peak geometry, annotation, nucleosome, ASM, conversion rate |
| Chromatin accessibility | ArchR 1.0, Signac 1.12 | TF footprinting, peak-gene links | blocked | footprinting needs a motif database and an independent footprint caller |
| Genome assembly QC | QUAST 5.2, BUSCO 5.7 | assembly statistics, completeness | blocked | no assemblies or BUSCO lineage data in the workspace |
| Read mapping and QC | BWA-MEM2 2.2, samtools 1.19 | mapping, flagstat, coverage | covered | BAM/FASTQ QC and coverage operators |
| RNA-seq quantification | Salmon 1.10, kallisto 0.50 | transcript abundance | implemented b73 | isoform EM and PSI operators |
| Alternative splicing | rMATS 4.1, SUPPA2 | PSI, differential splicing | implemented b73 | PSI, exon skipping, intron retention, APA |
| Circular RNA and editing | CIRCexplorer2, REDItools 2 | back-splice detection, A-to-G editing | implemented final | circRNA and RNA-editing operators |
| Immunology repertoire | MiXCR 4.6, IEDB | clonotype, epitope conservation | implemented b69/b62b | clonotype, TCR diversity, CDR3 properties, epitope conservation |
| Epidemiology | EpiEstim 2.2, R0 1.3 | growth rate, R0, SIR/SEIR | implemented b70 | five epidemic operators |
| Comparative genomics | Roary 3.13, OrthoFinder 2.5 | pangenome, core genome, synteny | implemented b71/b71b | pangenome curve, ortholog clusters, conserved gene order |
| Causal inference | TwoSampleMR 0.5 | Mendelian randomization | covered | causal operators for IVW/MR-Egger |
| Genome annotation | Prokka 1.14, Bakta 1.9 | ORF and feature annotation | implemented b61 | prokaryotic annotation operators |
