# Competitor capability gap matrix (Library 5.x)

Status: planning baseline for the 867 → 1001 operator expansion (134 new operators,
batches b49–b75). The matrix is capability-oriented: one row can cover several
operators when they share a competitor, a dataset and an oracle class.

## Method

- Source of truth for existing coverage: `workdir/operator_inventory.txt`
  (867 rows, `category<TAB>id<TAB>title`, generated from
  `library/seed/operator_index.json`).
- A capability is included only when it has (a) a public, redistributable or
  locally cached real dataset and (b) at least two independent oracles, or one
  oracle plus an exact hand calculation. Rows without both are marked `blocked`
  and are not implemented.
- "Existing" lists operator ids that already cover part of the capability.
  Planned ids are new; no existing id is re-implemented.
- Oracles are independent implementations, not two wrappers around the same
  library. Where only the implementation library itself is available, the second
  oracle is an explicit hand calculation with the formula written in the
  operator Markdown.
- Priority: `P0` = data and both oracles already available in this workspace;
  `P1` = one external tool must be installed or one small public dataset fetched;
  `P2` = data or oracle is missing, kept out of the 134 unless it becomes available.
- Dataset sha256 values are recorded per batch in `docs/verification/routes-5.x.md`;
  this matrix records the canonical URL and the local cache name.
- Research-use data only; no clinical or diagnostic claim is made.

## Summary

| Domain | Existing operators (domain total) | Planned new | Priority mix | Strongest oracle pair |
| --- | ---: | ---: | --- | --- |
| Chemistry / ligands | 24 (Docking+Ligand+ML descriptor family) | 10 | P0 | RDKit vs hand SMILES arithmetic |
| Protein sequence properties | 40 (Sequence + Proteomics) | 10 | P0 | ExPASy ProtParam vs hand formula |
| Structure quality | 56 | 5 | P0 | Biopython vs hand geometry |
| Population genetics | 15 | 14 | P0/P1 | plink2 vs hand genotype arithmetic |
| Metagenomics | 2 (`genome_mash_distance`, `genome_kmer_similarity`) | 15 | P1/P2 | Kraken2/CheckM2/Roary CLI vs hand |
| Genome annotation | 8 | 5 | P1 | InterProScan/Bakta TSV vs hand |
| Epigenomics | 7 (ATAC/peak family) | 15 | P1 | MACS3/HOMER/MEME CLI vs hand |
| Single cell | 12 | 10 | P0/P1 | Scanpy/Squidpy vs hand matrix |
| Proteomics MS | 10 | 10 | P0 | pyteomics vs hand spectrum math |
| Metabolomics | 0 | 5 | P1 | hand adduct/formula arithmetic |
| Immunology | 1 (`vhh_humanization_score`) | 5 | P1 | IEDB/Nextclade vs hand motif |
| Epidemiology | 0 | 5 | P0 | R/deSolve vs hand Euler/RK4 |
| Comparative genomics | 2 (k-mer similarity, mash) | 5 | P1 | Roary vs hand gene presence |
| Phylogenetics | 12 | 5 | P0 | Biopython/IQ-TREE vs hand parsimony |
| Transcriptomics | 6 | 10 | P0/P1 | hand PSI/EM vs bedtools |
| Causal inference | 6 | 5 | P0 | R mediation/OLS vs hand algebra |

## Chemistry / ligands (10)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Molecular formula, exact mass, isotope pattern | RDKit 2026.09.1 https://www.rdkit.org/docs/ ; Open Babel https://openbabel.org/ | `rdkit_descriptors` (average MW, logP, TPSA, HBD/HBA, rings, Fsp3) | Hill formula, monoisotopic exact mass and a theoretical isotope envelope are absent; average MW alone is not enough for MS | P0 | 10-compound panel from PubChem (aspirin CID 2244, caffeine CID 2519); local file sha256 c392966d... | RDKit `CalcMolFormula`/`CalcExactMolWt` vs hand atomic-composition sum; pyteomics `isotopologues` vs convolution | `ligand_molecular_formula`, `ligand_exact_mass`, `ligand_isotope_pattern` (implemented b49) |
| Fragmentation and R-group decomposition | RDKit 2026.09.1; DataWarrior 5.5 https://www.openmolecules.org/datawarrior/ | `rdkit_morgan_fingerprint`, `rdkit_murcko_fingerprint`, `rdkit_mcs`, `rdkit_scaffold`, `rdkit_tautomer`, `rdkit_similarity`, `rdkit_smarts_matches`, `rdkit_sa_score` | BRICS retrosynthetic fragments and core-based R-group matrices are absent; the other chem rows in the first draft duplicate these existing operators and were removed | P0 | Same 10-compound panel; RDKit test suite https://github.com/rdkit/rdkit/tree/master/Code/GraphMol | RDKit `BRICSDecompose` / `RGroupDecompose` vs hand fragment and substituent enumeration | `ligand_brics_fragments`, `ligand_rgroup_decomposition` (implemented b49) |
| MS formula and adduct arithmetic | Open Babel 3.1 https://openbabel.org/ ; pyteomics 5.0.2 https://pyteomics.readthedocs.io/ | b49 formula/mass/isotope; b50 formula parser, DBE, adducts, mass fraction, nitrogen rule | Formula-string parsing, DBE, adduct m/z, element mass fractions and the nitrogen rule were absent; ppm error and isotope-pattern similarity need an observed spectrum and remain unimplemented | P1 | Same 10-compound panel; MassBank records https://massbank.eu/ | pyteomics formula/mass vs hand arithmetic; molmass 2026.11.1 cross-check | `ligand_formula_parse`, `ligand_dbe`, `ligand_adduct_mz`, `ligand_mass_fraction`, `ligand_nitrogen_rule` (implemented b50); `ligand_mass_ppm_error`, `ligand_isotope_similarity` remain no-data |

## Protein sequence properties (10)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Global physicochemical indices | ExPASy ProtParam https://web.expasy.org/protparam/ ; Biopython 1.88 `ProtParam` | `protein_properties` (MW, pI, GRAVY, aromaticity), `protein_composition`, `sequence_net_charge`, `sequence_hydrophobic_moment` | Aliphatic index is absent; Boman interaction index and N-end-rule half-life were considered but have no independent oracle | P0 | UniProt P00698 (lysozyme), P01308 (insulin), P69905 (haemoglobin alpha) https://www.uniprot.org/ | ProtParam web vs hand formula (aliphatic index = 100×(A+2.9V+3.9(I+L)) / total) | `protein_aliphatic_index` (b51), `protein_charge_curve` (b52), `protein_gravy_window` (b52) |
| Localization and targeting motifs | PSORTb 3.0 https://www.psort.org/psortb/ ; UniProt annotation | `sequence_signal_peptide`, `sequence_signal_peptide_v2`, `sequence_transmembrane_topology`, `structure_glycosylation_sites` | NLS, PTS1, KDEL/ER-retention and mitochondrial presequence scoring are absent; a GPI-anchor heuristic was dropped for lack of an independent oracle | P0 | UniProt Swiss-Prot entries with curated localization (P00698, P01308, P0DTC2) | Hand motif rules from literature vs PSORTb/UniProt text | `protein_nls_motifs` (b51), `protein_pts1_signal` (b51), `protein_er_retention` (b52), `protein_mitochondrial_targeting` (b52), `protein_nuclear_export_signal` (b52) |
| Modification and kinase motifs | NetPhos 3.1 https://services.healthtech.dtu.dk/service.php?NetPhos-3.1 ; OGPET https://services.healthtech.dtu.dk/service.php?OGPET-1.0 | `sequence_liability_scan`, `structure_glycosylation_sites` | Kinase consensus motif scoring is absent; O-GalNAc sequon prediction lacks an independent oracle | P0 | UniProt phosphosite annotations; 20 reviewed human proteins | Hand regex/consensus table vs NetPhos/OGPET | `protein_kinase_motifs` (b51), `protein_nglyc_sequons` (b51) |

## Structure quality (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Hydrogen bonds and water bridges | HBPLUS http://www.ebi.ac.uk/thornton-srv/software/HBPLUS/ ; PyMOL 3.0 https://pymol.org/ | `structure_md_hbond_occupancy`, `structure_md_hbond_lifetime` (MD only) | Static H-bond energy and water-mediated bridge inventory are absent | P0 | PDB 1MEL (lysozyme, 2.0 Å), 1CRN | Hand Coulomb/Lennard-Jones energy vs PyMOL `find_pairs` | `structure_water_bridges` |
| Ligand contact energetics and pose ensembles | RDKit 2026.09.1; PoseBusters https://github.com/maabuu/posebusters | `structure_ligand_interaction_fingerprint`, `structure_ligand_burial`, `structure_ligand_pose_rmsd`, `structure_ligand_strain` | Per-contact energy decomposition, ligand-buried SASA and pose-ensemble clustering are absent | P0 | PDB 1MEL + 10 Vina-generated poses (synthetic poses explicitly marked `mode=synthetic`) | Hand distance-dependent energy vs RDKit MMFF | `structure_ligand_contact_energy`, `structure_ligand_buried_sasa`, `structure_ligand_pose_ensemble`, `structure_ligand_hbond_count` |

## Population genetics (14)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Homozygosity and relatedness | plink2 2.00a https://www.cog-genomics.org/plink/2.0/ ; bcftools 1.19 https://samtools.github.io/bcftools/ | `vcf_relatedness`, `relatedness`, `ld_decay`, `ld_matrix` | ROH islands, IBD segments and LD-based Ne are absent | P0 | 1000 Genomes chr22 VCF (local `chr22_1000g.vcf.gz`), https://www.internationalgenome.org/data | plink2 `--homozyg`/`--genome` vs hand IBS/IBD arithmetic | `roh_detect`, `ibd_segments`, `effective_population_size` |
| Haplotype and selection statistics | plink2 2.00a; selscan 2.0 https://github.com/szpiech/selscan | `site_frequency_spectrum`, `tajimas_d`, `nucleotide_diversity`, `watterson_theta`, `patterson_fst` | Folded SFS table, haplotype blocks, iHS, XP-EHH, recombination rate and Fst outlier scan are absent | P0 | 1000 Genomes chr22; 1000G phase 3 haplotypes | Hand EHH/XP-EHH formula vs selscan CLI | `recombination_rate` *(b56)*, `fst_outlier_scan` *(b56)*, `genotype_allele_balance` *(b56)*, `haplotype_blocks`, `ihs_selection`, `xpehh_selection` |
| Quantitative and pedigree genetics | R/qtl2 0.34 https://kbroman.org/qtl2/ ; plink2 2.00a | `gwas_association`, `prs`, `hwe` | Interval QTL mapping, RR-BLUP, selection index, pedigree inbreeding, Mendelian errors and allele balance are absent | P0/P1 | 1000G chr22 + small simulated pedigree (marked `mode=synthetic`); A. thaliana 1001G subset https://1001genomes.org/ | R/qtl2 vs hand Haley-Knott regression; plink2 `--mendel` vs hand | `qtl_interval_mapping`, `genomic_selection_rrblup`, `selection_index`, `pedigree_inbreeding`, `genotype_mendelian_error`, `genotype_call_rate_qc` |

## Metagenomics (15)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Taxonomic and functional profiles | Kraken2 2.1.3 https://github.com/DerrickWood/kraken2 ; Bracken 2.9 https://github.com/jenniferlu717/Bracken ; MetaPhlAn 4.1 https://github.com/biobakery/MetaPhlAn ; HUMAnN 3.9 https://huttenhower.sph.harvard.edu/humann/ | none | Report parsing, re-estimation, pathway collapse and profile merge are absent | P1 | Kraken2 tutorial reports https://github.com/DerrickWood/kraken2/wiki/Manual ; MetaPhlAn demo https://github.com/biobakery/metaphlan | Kraken2/Bracken CLI vs hand count arithmetic | `kraken_report_parse`, `bracken_reestimate`, `humann_pathway_collapse`, `metaphlan_profile_merge`, `taxon_abundance_collapse` |
| Genome quality and taxonomy | CheckM2 1.0.2 https://github.com/chklovski/CheckM2 ; GTDB-Tk 2.4.0 https://github.com/Ecogenomics/GTDBTk | none | Quality-report and taxonomy-report parsing are absent | P1 | CheckM2 test outputs https://github.com/chklovski/CheckM2/tree/main/tests ; GTDB-Tk example | CheckM2/GTDB-Tk TSV vs hand aggregation | `checkm_quality_parse`, `gtdb_taxonomy_parse` |
| ANI, pangenome and typing | fastANI 1.34 https://github.com/ParBLiSS/FastANI ; Roary 3.13 https://github.com/sanger-pathogens/Roary ; pubMLST https://pubmlst.org/ | `genome_mash_distance`, `genome_kmer_similarity` | K-mer ANI, pan/core matrix, MLST, plasmid replicon, integron, IS, oriC and prophage detection are absent | P1/P2 | E. coli K-12 GCF_000005845.2 and O157 GCF_000008865.2; 5 E. coli GFFs from NCBI | fastANI vs mash vs hand k-mer Jaccard; Roary vs hand presence matrix | `ani_from_kmers`, `pangenome_matrix`, `mlst_typing`, `plasmid_replicon_typing`, `integron_detect`, `is_element_scan`, `oric_detect`, `prophage_detect` |

## Genome annotation (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Domain and gene-model summaries | InterProScan 5.68 https://github.com/ebi-pf-team/interproscan ; Pfam 37 https://www.ebi.ac.uk/interpro/ ; Bakta 1.10 https://github.com/oschwengers/bakta ; Prokka 1.14 https://github.com/tseemann/prokka | `sequence_hmmer_domains`, `prodigal_genes`, `genome_cds_check`, `gff_feature_stats`, `annotation_gaps` | InterProScan TSV summary, Pfam architecture, annotation completeness, CDS overlap and gene-length profile are absent | P1 | E. coli K-12 GFF3 + InterProScan TSV (public EBI example); Bakta test data | InterProScan/Bakta TSV vs hand counting | `interpro_domain_summary`, `pfam_architecture`, `annotation_completeness`, `annotation_overlap_check`, `annotation_gene_length` |

## Epigenomics (15)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Peak statistics and overlaps | MACS3 3.0.2 https://github.com/macs3-project/MACS ; bedtools 2.31 https://bedtools.readthedocs.io/ ; ChIPseeker 1.38 https://bioconductor.org/packages/ChIPseeker/ | `peak_merge`, `peak_nearest_gene`, `atac_peak_call`, `atac_peak_quality`, `interval_annotate` | Peak width distribution, summit offsets, gap/overlap statistics, strand bias, multi-sample overlap matrix and TSS/exon/intron/UTR annotation are absent | P1 | ENCODE GM12878 peaks (local `peaks.bed`), https://www.encodeproject.org/ | bedtools/pandas vs awk interval arithmetic | `peak_width_stats`, `peak_summit_offset`, `peak_gap_stats`, `peak_signal_stats` (implemented b53); `peak_strand_bias`, `peak_width_signal_correlation`, `peak_chrom_summary` (implemented b54); `peak_overlap_matrix`, `peak_annotate`, `peak_density_profile`, `peak_tss_enrichment`, `peak_peak_distance` |
| Motif enrichment and discovery | HOMER 5.1 http://homer.ucsd.edu/homer/ ; MEME 5.5.7 https://meme-suite.org/ | `motif_scan`, `pwm_scan`, `pwm_information` | Hypergeometric motif enrichment and EM de-novo discovery are absent | P1 | JASPAR 2024 https://jaspar.genereg.net/ ; ENCODE peak sequences | HOMER/MEME vs hand hypergeometric/planted motif | `motif_enrichment`, `motif_discovery_em` |
| Chromatin and methylation | deepTools 3.5 https://deeptools.readthedocs.io/ ; ChromHMM 1.25 https://github.com/compbio/ChromHMM ; Bismark 0.24 https://github.com/FelixKrueger/Bismark | `atac_fragment_size`, `atac_tss_enrichment`, `bam_alignment_summary` | ChIP fingerprint, beta values, DMR calling, nucleosome periodicity and chromatin-state segmentation are absent | P1/P2 | ENCODE GM12878 BAM (local 2.5 GB `ENCFF415FEC.bam`); Bismark test BAM | deepTools/ChromHMM vs hand binning; beta = M/(M+U) by hand | `methylation_beta_value`, `methylation_m_value`, `dmr_window_scan` implemented; `nucleosome_positioning`, `chromatin_state_segmentation` planned |

## Single cell (10)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Graph, clustering and batch metrics | Scanpy 1.12.5 https://scanpy.readthedocs.io/ ; scvi-tools 1.2 https://scvi-tools.org/ | `pseudobulk`, `paga_connectivity`, `sc_rank_genes`, `sc_cluster_profile`, `doublet_detect`, `trajectory_gene_trends` | kNN graph, Leiden clustering, kBET and iLISI batch-mixing metrics are absent | P0 | PBMC3k https://scanpy.readthedocs.io/en/stable/generated/scanpy.datasets.pbmc3k.html | Scanpy vs hand kNN/Leiden on 200 cells | `sc_knn_graph`, `sc_leiden_cluster`, `sc_batch_kbet`, `sc_batch_ilisi`, `sc_pseudobulk_de` (implemented b64) |
| Pseudobulk DE and spatial | Scanpy 1.12.5; Squidpy 1.6 https://squidpy.readthedocs.io/ ; CIBERSORTx https://cibersortx.stanford.edu/ | `pseudobulk` (aggregation only), `combat` | Pseudobulk DE, spatial neighbor graph, spatially variable genes, NNLS deconvolution, CNV score and spatial domains are absent | P1 | PBMC3k; Squidpy seqFISH sample https://squidpy.readthedocs.io/en/stable/api/squidpy.datasets.html | Scanpy/Squidpy vs hand Moran's I and NNLS | `sc_pseudobulk_de`, `sc_spatial_neighbors`, `sc_spatial_variable_genes`, `sc_deconvolution`, `sc_cnv_score`, `sc_spatial_domains` |

## Proteomics MS (10)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Spectrum matching and annotation | pyteomics 4.7 https://pyteomics.readthedocs.io/ ; OpenMS 3.2 https://www.openms.de/ | `peptide_fragment_ions`, `peptide_isotope_envelope`, `peptide_mass`, `peptide_modified_mass` | MS2 cosine, spectral-library match, PTM localization and spectrum annotation are absent | P0 | PRIDE PXD000001 (local mzML subset), https://www.ebi.ac.uk/pride/ | pyteomics vs hand dot-product on 10 peaks | `spectrum_library_match` (b66), `peptide_spectrum_annotation` (b66); `ms2_cosine`, `ptm_localization` (future) |
| Protein inference and quantification | OpenMS 3.2; MaxQuant 2.6 https://www.maxquant.org/ | `protein_rollup`, `peptide_qvalue` | Parsimony protein inference, LFQ median/quantile normalisation, MS1 feature detection, RT alignment and missing-value filter are absent | P0 | PRIDE PXD000001; MaxQuant LFQ benchmark | Hand parsimony set cover vs OpenMS; hand median/quantile | `lfq_median_normalize` (b67), `lfq_quantile_normalize` (b67), `ms_missing_filter` (b67); `protein_inference` (b66), `ms1_feature_detect` (b68), `rt_alignment` (future) |

## Metabolomics (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LC-MS annotation and enrichment | XCMS 4.0 https://bioconductor.org/packages/xcms/ ; METLIN https://metlin.scripps.edu/ ; HMDB 5.0 https://hmdb.ca/ | `ms1_feature_detect`*, `ms1_isotope_pattern`*, `metabolite_mass_match`* | Adduct detection, metabolite-set enrichment, formula annotation, RT prediction and XIC extraction still absent | P1 | MetaboLights MTBLS1 https://www.ebi.ac.uk/metabolights/MTBLS1 | Hand m/z adduct arithmetic vs HMDB; hand hypergeometric | `metabolite_set_enrichment`, `xic_extract`, `metabolite_adduct_annotation` |

## Immunology (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Epitope and repertoire | IEDB 2.12 https://www.iedb.org/ ; NetMHCpan 4.1 https://services.healthtech.dtu.dk/service.php?NetMHCpan-4.1 ; Nextclade 3.0 https://clades.nextstrain.org/ | `vhh_humanization_score` | MHC-binding motif, processing score, TCR diversity, BCR clonotype and viral lineage assignment are absent | P1 | IEDB epitope table; Nextstrain SARS-CoV-2 JSON https://nextstrain.org/ | IEDB/NetMHCpan vs hand PWM; Nextclade vs hand mutation set | `bcr_clonotype` (implemented b69), `tcr_diversity` (implemented b69), `cdr3_properties` (implemented b69), `mhc_binding_motif`, `epitope_conservation` |

## Epidemiology (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Epidemic dynamics | R 4.4 `deSolve` https://cran.r-project.org/package=deSolve ; EpiEstim 2.2 https://cran.r-project.org/package=EpiEstim | none | R0, SIR, SEIR, growth rate and vaccine efficacy are absent | P0 | WHO measles/COVID linelists (public); synthetic outbreaks marked `mode=synthetic` | R/deSolve vs hand Euler/RK4 | `epidemic_growth_rate`, `epidemic_r0`, `epidemic_case_fatality`, `epidemic_sir_fit`, `epidemic_seir_fit` (implemented b70) |

## Comparative genomics (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pangenome and orthology | Roary 3.13 https://github.com/sanger-pathogens/Roary ; OrthoMCL 2.0 https://orthomcl.org/ | `genome_kmer_similarity`, `genome_mash_distance` | Pan-genome curve, core-genome size, ortholog clustering, MRCA and ultrametric checks are absent | P1 | 5 E. coli GFF3 (NCBI); Roary test data | Roary vs hand presence matrix; Biopython vs hand MRCA | `pangenome_curve`, `core_genome_size`, `ortholog_cluster`, `tree_mrca`, `tree_ultrametric` |

## Phylogenetics (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tree inference and comparison | IQ-TREE 2.3.6 http://www.iqtree.org/ ; RAxML-NG 1.2 https://github.com/amkozlov/raxml-ng ; Biopython 1.88 | `phylo_distance_matrix`, `phylo_neighbor_joining`, `tree_balance`, `tree_prune_tips`, `tree_root_midpoint`, `robinson_foulds`, `phylo_bootstrap` | Molecular-clock dating, consensus tree, quartet support, parsimony and likelihood scores are absent | P0 | IQ-TREE example alignment http://www.iqtree.org/doc/Quickstart ; Biopython tutorial trees | IQ-TREE vs hand parsimony; Biopython vs hand consensus | `tree_parsimony_score` (b72), `tree_mrca` (b72), `tree_ultrametric` (b72); `tree_dating`, `tree_consensus`, `tree_quartet_support`, `tree_likelihood_score` (future) |

## Transcriptomics (10)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Isoform and splicing quantification | Salmon 1.10 https://combine-lab.github.io/salmon/ ; RSEM 1.3 https://deweylab.github.io/RSEM/ ; rMATS 4.1 http://rnaseq-mats.sourceforge.net/ | `gene_structure`, `variant_consequence` | Isoform EM, PSI, APA, intron retention and exon skipping are absent | P0 | GENCODE19 GFF (local `gencode19_22.csq.gff`); 1000G chr22 | Hand EM on 3 isoforms vs Salmon; hand PSI vs rMATS | implemented b73: `isoform_quantification_em`, `splicing_psi`, `alternative_polyadenylation`, `intron_retention`, `exon_skipping` |
| RNA modification and structure | MODOMICS https://modomics.genesilico.pl/ ; CircInteractome https://circinteractome.nia.nih.gov/ ; EMBOSS 6.6 https://emboss.sourceforge.net/ | `sequence_rna_fold`, `sequence_rna_accessibility`, `rscu_table` | RNA-editing detection, m6A motif scan, circRNA detection, CpG islands and codon-pair bias are absent | P1 | RMBase 2.0 https://rna.sysu.edu.cn/rmbase/ ; GENCODE | Hand motif/regex vs RMBase; EMBOSS `newcpgreport` vs hand | `rna_editing_detect`, `m6a_motif_scan`, `circrna_detect`, `cpg_island_detect`, `codon_pair_bias` |

## Causal inference (5)

| Capability | Competitor (version / link) | Existing | Gap | Pri | Public data | Oracle A / oracle B | Planned ids |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Quasi-experimental estimators | R `mediation` 4.5 https://cran.r-project.org/package=mediation ; `did` 2.1 https://cran.r-project.org/package=did ; `Synth` 1.1 https://cran.r-project.org/package=Synth | `propensity_score`, `psm_*`, `iv_2sls`, `rdd`, `iptw_effect` | Mediation, difference-in-differences, synthetic control, doubly robust ATE and event study are absent | P0 | Card–Krueger minimum-wage panel (public replication data); California smoking panel | R `mediation`/`did` vs hand OLS algebra | implemented b75: `mediation_analysis`, `difference_in_differences`, `synthetic_control`, `doubly_robust_ate`, `event_study` |

## Rows deliberately not planned

| Capability | Why not planned |
| --- | --- |
| AlphaFold3 / Boltz-2 / Chai inference | Model weights are not redistributable in this environment and are GB-scale; existing `colabfold_predict`, `boltz_predict`, `esm3_fold` already wrap the available paths. |
| MD trajectory producers (GROMACS/AMBER) | Existing `structure_openmm_md_*` family covers the only locally installable engine; no second oracle for long trajectories. |
| Spatial transcriptomics deconvolution at atlas scale | No public dataset small enough for a deterministic route and no second oracle; kept as a single NNLS operator in the single-cell section. |
| Clinical variant interpretation | No licensed evidence source and no oracle; explicitly out of scope. |
| Metagenomic assembly (MEGAHIT/metaSPAdes) | No local binary and no small gold-standard assembly with two independent oracles. |
| GPI-anchor prediction | The C-terminal omega-site heuristic gave a false negative on the curated GPI protein P05186 and no independent predictor is installable; a binary call would overstate evidence. |
| Boman interaction index and N-end-rule half-life | No independent implementation or public per-protein oracle in this environment. |
| O-GalNAc sequon prediction (OGPET) | Service-only oracle with no local implementation; a hand regex would not be independently verifiable. |

## Implementation batches

The 134 ids are assigned to batches b49–b75 in `workdir/plan_134.tsv`
(one batch per 4–5 ids, one shared route per batch). Each batch records:
dataset URL and sha256, two oracle versions and outputs, the WSL route summary,
the three-end md5/number comparison, and the operator Markdown limitations.

## Change log

| Date | Change |
| --- | --- |
| 2026-11-08 | Initial matrix for the 867 → 1001 expansion; 134 planned ids, 16 domains. |
| 2026-11-08 | b50 chem: the planned ppm-error and isotope-similarity ids need observed spectra and are recorded as no-data; mass fraction and the nitrogen rule replace them. |
| 2026-11-08 | b49 chem audit: six planned chem ids already existed as `rdkit_*` operators; chem section now lists the five implemented ids plus five MS-arithmetic ids for b50. Total stays 134. |
