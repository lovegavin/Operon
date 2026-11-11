# Operator trust sheets

One page per operator: what the code does, the evidence behind it, its
limits, and how to reproduce the evidence. Generated from the 8.0.1
descriptor set and five-layer coverage ledger.

Trust levels are conservative:

- **A** independent numeric oracle plus a recorded real execution;
- **A-** independent numeric oracle, execution not recorded;
- **B** recorded real execution (local or srv);
- **C** dedicated test reference plus a compiled route;
- **D** dedicated or smoke test reference only;
- **E** static contract only — not behaviourally verified.

`UNIT` means a test file references the operator and the 8.0.1 full suite
passed; it does not mean every operator was independently re-inspected.

## Coverage summary

| Level | Operators |
| --- | ---: |
| A | 1 |
| A- | 10 |
| B | 257 |
| C | 761 |
| D | 24 |
| E | 10 |

Total: **1063** operators.

## By category

| Category | A/A- | B | C | D | E |
| --- | ---: | ---: | ---: | ---: | ---: |
| Analysis | 0 | 0 | 1 | 0 | 0 |
| Antibody | 0 | 1 | 0 | 0 | 0 |
| Causal Inference | 0 | 0 | 4 | 0 | 0 |
| Causal inference | 0 | 0 | 12 | 0 | 0 |
| Chemistry | 0 | 0 | 10 | 0 | 0 |
| Comparative genomics | 0 | 0 | 5 | 0 | 0 |
| Data | 2 | 1 | 13 | 0 | 0 |
| Docking | 0 | 1 | 2 | 0 | 0 |
| Epidemiology | 0 | 0 | 5 | 0 | 0 |
| Epigenomics | 0 | 0 | 24 | 0 | 0 |
| Genome | 0 | 7 | 47 | 0 | 0 |
| Genome annotation | 0 | 0 | 5 | 0 | 0 |
| Genome editing | 0 | 0 | 1 | 0 | 0 |
| Genomics | 0 | 0 | 1 | 0 | 0 |
| Imaging | 1 | 0 | 0 | 0 | 0 |
| Immunology | 0 | 0 | 6 | 0 | 0 |
| Ligand | 0 | 0 | 1 | 0 | 0 |
| Machine Learning | 1 | 77 | 150 | 20 | 4 |
| Metabolic modelling | 0 | 1 | 0 | 0 | 0 |
| Metabolism | 0 | 0 | 3 | 0 | 0 |
| Metabolomics | 0 | 0 | 6 | 0 | 0 |
| Metagenomics | 0 | 1 | 14 | 0 | 0 |
| Network | 0 | 0 | 3 | 0 | 0 |
| Omics | 0 | 29 | 63 | 0 | 1 |
| Phylogenetics | 0 | 2 | 14 | 0 | 0 |
| Population genetics | 1 | 5 | 10 | 0 | 0 |
| Proteomics | 0 | 0 | 19 | 0 | 0 |
| Proteomics MS | 0 | 0 | 3 | 0 | 0 |
| Quality Control | 0 | 0 | 24 | 0 | 1 |
| Sequence | 0 | 18 | 24 | 0 | 0 |
| Single cell | 0 | 4 | 7 | 0 | 0 |
| Statistics | 5 | 58 | 213 | 0 | 0 |
| Structure | 0 | 39 | 16 | 2 | 0 |
| Transcriptomics | 0 | 1 | 6 | 0 | 0 |
| Visualization | 0 | 1 | 0 | 0 | 0 |
| analysis | 0 | 0 | 8 | 1 | 4 |
| data | 0 | 5 | 1 | 0 | 0 |
| data preparation | 0 | 0 | 2 | 0 | 0 |
| visualization | 0 | 0 | 1 | 0 | 0 |
| 可视化 | 0 | 3 | 10 | 0 | 0 |
| 数据整理 | 0 | 2 | 14 | 0 | 0 |
| 统计分析 | 1 | 1 | 10 | 0 | 0 |
| 质量控制 | 0 | 0 | 3 | 1 | 0 |

## All operators

| Operator | Title | Trust | Evidence |
| --- | --- | --- | --- |
| [`acf`](acf.md) | Autocorrelation function | C | L2 UNIT; L3 ROUTE |
| [`ada_boost_classifier`](ada_boost_classifier.md) | AdaBoost classifier | C | L2 UNIT; L3 ROUTE |
| [`ada_boost_regressor`](ada_boost_regressor.md) | AdaBoost regressor | C | L2 UNIT; L3 ROUTE |
| [`additive_glm`](additive_glm.md) | Additive B-spline GLM | C | L2 UNIT; L3 ROUTE |
| [`additive_spline_regression`](additive_spline_regression.md) | Additive B-spline regression | C | L2 UNIT; L3 ROUTE |
| [`adf_test`](adf_test.md) | Augmented Dickey-Fuller test | C | L2 UNIT; L3 ROUTE |
| [`adjusted_mutual_info`](adjusted_mutual_info.md) | Adjusted mutual information | C | L2 UNIT; L3 ROUTE |
| [`adjusted_rand`](adjusted_rand.md) | Adjusted Rand index | C | L2 UNIT; L3 ROUTE |
| [`adjusted_rand_index`](adjusted_rand_index.md) | Adjusted Rand index | C | L2 UNIT; L3 ROUTE |
| [`aft`](aft.md) | Weibull accelerated failure time | C | L2 UNIT; L3 ROUTE |
| [`agglomerative`](agglomerative.md) | Agglomerative clustering | C | L2 UNIT; L3 ROUTE |
| [`aggregate`](aggregate.md) | Aggregate | C | L2 UNIT; L3 ROUTE |
| [`agostino_skewness`](agostino_skewness.md) | D'Agostino skewness test | C | L2 UNIT; L3 ROUTE |
| [`agostino_test`](agostino_test.md) | D'Agostino skewness test | C | L2 UNIT; L3 ROUTE |
| [`aldex2`](aldex2.md) | Compositional differential abundance | C | L2 UNIT; L3 ROUTE |
| [`align_reads`](align_reads.md) | Hi-C read alignment | C | L2 UNIT; L3 ROUTE |
| [`alignment_coverage`](alignment_coverage.md) | alignment_coverage | C | L2 UNIT; L3 ROUTE |
| [`alignment_insert_size`](alignment_insert_size.md) | alignment_insert_size | C | L2 UNIT; L3 ROUTE |
| [`allele_specific_methylation`](allele_specific_methylation.md) | Allele-specific methylation | C | L2 UNIT; L3 ROUTE |
| [`alternative_polyadenylation`](alternative_polyadenylation.md) | Alternative polyadenylation | C | L2 UNIT; L3 ROUTE |
| [`amrfinder_plus`](amrfinder_plus.md) | AMRFinderPlus resistance genes | B | L2 UNIT; L3 EXECUTED |
| [`analyze_contacts`](analyze_contacts.md) | Hi-C structure analysis | C | L2 UNIT; L3 ROUTE |
| [`ancom_bc`](ancom_bc.md) | Log-ratio differential abundance | C | L2 UNIT; L3 ROUTE |
| [`anderson_darling`](anderson_darling.md) | Anderson-Darling normality test | C | L2 UNIT; L3 ROUTE |
| [`ani_from_kmers`](ani_from_kmers.md) | ANI from shared k-mer counts | C | L2 UNIT; L3 ROUTE |
| [`annotate`](annotate.md) | annotate | B | L2 UNIT; L3 EXECUTED |
| [`annotation_completeness`](annotation_completeness.md) | Annotation completeness | C | L2 UNIT; L3 ROUTE |
| [`annotation_gaps`](annotation_gaps.md) | annotation_gaps | C | L2 UNIT; L3 ROUTE |
| [`annotation_gene_length`](annotation_gene_length.md) | Gene length profile | C | L2 UNIT; L3 ROUTE |
| [`annotation_overlap_check`](annotation_overlap_check.md) | Gene overlap check | C | L2 UNIT; L3 ROUTE |
| [`anosim`](anosim.md) | ANOSIM | B | L2 UNIT; L3 EXECUTED |
| [`anova`](anova.md) | one-way ANOVA | C | L2 UNIT; L3 ROUTE |
| [`ansari_bradley`](ansari_bradley.md) | Ansari-Bradley scale test | C | L2 UNIT; L3 ROUTE |
| [`anscombe_glynn`](anscombe_glynn.md) | Anscombe-Glynn kurtosis test | C | L2 UNIT; L3 ROUTE |
| [`anscombe_test`](anscombe_test.md) | Anscombe-Glynn kurtosis test | C | L2 UNIT; L3 ROUTE |
| [`antibody_cdr_graft`](antibody_cdr_graft.md) | CDR grafting | B | L2 UNIT; L3 EXECUTED |
| [`antibody_cdr_hydrophobicity`](antibody_cdr_hydrophobicity.md) | Antibody CDR Hydrophobicity | B | L2 UNIT; L3 EXECUTED |
| [`antibody_cdr_kabat`](antibody_cdr_kabat.md) | Kabat CDR boundaries | C | L2 UNIT; L3 ROUTE |
| [`antibody_cdr_length_profile`](antibody_cdr_length_profile.md) | CDR length profile | B | L2 UNIT; L3 EXECUTED_SRV |
| [`antibody_cdr_motifs`](antibody_cdr_motifs.md) | Antibody CDR Liability Motifs | C | L2 UNIT; L3 ROUTE |
| [`antibody_cdr_physchem`](antibody_cdr_physchem.md) | CDR physicochemical profile | C | L2 UNIT; L3 ROUTE |
| [`antibody_cdr_redesign`](antibody_cdr_redesign.md) | CDR 固定框架重设计 | B | L2 UNIT; L3 EXECUTED |
| [`antibody_developability`](antibody_developability.md) | Antibody developability panel | C | L2 UNIT; L3 ROUTE |
| [`antibody_numbering_imgt`](antibody_numbering_imgt.md) | IMGT numbering | C | L2 UNIT; L3 ROUTE |
| [`antibody_numbering_kabat`](antibody_numbering_kabat.md) | Kabat numbering | B | L2 UNIT; L3 EXECUTED |
| [`antifold_design`](antifold_design.md) | AntiFold 抗体逆折叠设计 | D | L2 UNIT; L3 SKIP |
| [`antifold_score`](antifold_score.md) | AntiFold inverse-folding scores | D | L2 UNIT; L3 SKIP |
| [`antismash_bgc`](antismash_bgc.md) | antiSMASH biosynthetic gene clusters | B | L2 UNIT; L3 EXECUTED |
| [`approx_entropy`](approx_entropy.md) | Approximate entropy | C | L2 UNIT; L3 ROUTE |
| [`arch_lm`](arch_lm.md) | ARCH LM test | C | L2 UNIT; L3 ROUTE |
| [`arch_test`](arch_test.md) | ARCH heteroskedasticity test | C | L2 UNIT; L3 ROUTE |
| [`arima`](arima.md) | ARIMA model | C | L2 UNIT; L3 ROUTE |
| [`assembly_contig_stats`](assembly_contig_stats.md) | Assembly contig statistics | C | L2 UNIT; L3 ROUTE |
| [`assembly_contiguity`](assembly_contiguity.md) | Assembly contiguity metrics | C | L2 UNIT; L3 ROUTE |
| [`assembly_gap_stats`](assembly_gap_stats.md) | Assembly gap statistics | C | L2 UNIT; L3 ROUTE |
| [`assembly_length_bins`](assembly_length_bins.md) | Contig length bins | C | L2 UNIT; L3 ROUTE |
| [`assembly_ngx_curve`](assembly_ngx_curve.md) | Assembly Nx curve | C | L2 UNIT; L3 ROUTE |
| [`assembly_ngx_metrics`](assembly_ngx_metrics.md) | Assembly NGx and auN metrics | C | L2 UNIT; L3 ROUTE |
| [`assembly_stats`](assembly_stats.md) | Assembly quality metrics (QUAST) | B | L2 UNIT; L3 EXECUTED |
| [`atac_fragment_size`](atac_fragment_size.md) | atac_fragment_size | C | L2 UNIT; L3 ROUTE |
| [`atac_peak_call`](atac_peak_call.md) | atac_peak_call | E | L2 SKIP; L3 ROUTE |
| [`atac_peak_quality`](atac_peak_quality.md) | atac_peak_quality | C | L2 UNIT; L3 ROUTE |
| [`atac_tss_enrichment`](atac_tss_enrichment.md) | atac_tss_enrichment | C | L2 UNIT; L3 ROUTE |
| [`attach_info`](attach_info.md) | 附加注释 | C | L2 UNIT; L3 ROUTE |
| [`autoencoder_anomaly`](autoencoder_anomaly.md) | Score rows with a bottleneck autoencoder | B | L2 UNIT; L3 EXECUTED |
| [`bai_perron`](bai_perron.md) | Bai-Perron multiple structural breaks | C | L2 UNIT; L3 ROUTE |
| [`bam_alignment_summary`](bam_alignment_summary.md) | BAM alignment summary | C | L2 UNIT; L3 ROUTE |
| [`bam_flagstat`](bam_flagstat.md) | bam_flagstat | C | L2 UNIT; L3 ROUTE |
| [`bam_gene_bias`](bam_gene_bias.md) | bam_gene_bias | C | L2 UNIT; L3 ROUTE |
| [`bam_gene_counts`](bam_gene_counts.md) | bam_gene_counts | C | L2 UNIT; L3 ROUTE |
| [`bam_mapq_distribution`](bam_mapq_distribution.md) | BAM MAPQ distribution | C | L2 UNIT; L3 ROUTE |
| [`bam_read_length_stats`](bam_read_length_stats.md) | BAM read length statistics | C | L2 UNIT; L3 ROUTE |
| [`barnard_test`](barnard_test.md) | Barnard exact test | C | L2 UNIT; L3 ROUTE |
| [`barplot`](barplot.md) | Composition barplot | C | L2 UNIT; L3 ROUTE |
| [`bartels_rank`](bartels_rank.md) | Bartels rank test | C | L2 UNIT; L3 ROUTE |
| [`bartlett`](bartlett.md) | Bartlett variance test | C | L2 UNIT; L3 ROUTE |
| [`bartlett_sphericity`](bartlett_sphericity.md) | Bartlett sphericity test | C | L2 UNIT; L3 ROUTE |
| [`bayesian_linear_regression`](bayesian_linear_regression.md) | Bayesian linear regression | A- | L2 ORACLE; L3 ROUTE |
| [`bayesian_ridge_regressor`](bayesian_ridge_regressor.md) | Bayesian ridge regressor | C | L2 UNIT; L3 ROUTE |
| [`bcr_clonotype`](bcr_clonotype.md) | BCR clonotype grouping and expansion | C | L2 UNIT; L3 ROUTE |
| [`bds_test`](bds_test.md) | BDS nonlinearity test | C | L2 UNIT; L3 ROUTE |
| [`beta_regression`](beta_regression.md) | Beta regression | C | L2 UNIT; L3 ROUTE |
| [`betadisper`](betadisper.md) | Beta dispersion | C | L2 UNIT; L3 ROUTE |
| [`betadiver`](betadiver.md) | Beta diversity from presence/absence | C | L2 UNIT; L3 ROUTE |
| [`bh_adjust`](bh_adjust.md) | Benjamini-Hochberg FDR | C | L2 UNIT; L3 ROUTE |
| [`bhapkar_test`](bhapkar_test.md) | Bhapkar test | C | L2 UNIT; L3 ROUTE |
| [`bin`](bin.md) | Bin | B | L2 UNIT; L3 EXECUTED |
| [`binomial_test`](binomial_test.md) | Exact binomial test | C | L2 UNIT; L3 ROUTE |
| [`bioenv`](bioenv.md) | Bio-environment matching | B | L2 UNIT; L3 EXECUTED |
| [`birch`](birch.md) | BIRCH clustering | C | L2 UNIT; L3 ROUTE |
| [`bisulfite_conversion_rate`](bisulfite_conversion_rate.md) | Bisulfite conversion rate | C | L2 UNIT; L3 ROUTE |
| [`bland_altman`](bland_altman.md) | Bland-Altman agreement | C | L2 UNIT; L3 ROUTE |
| [`boltz_affinity_summary`](boltz_affinity_summary.md) | Boltz-2 亲和力预测汇总 | D | L2 UNIT; L3 SKIP |
| [`boltz_complex_confidence`](boltz_complex_confidence.md) | Boltz complex prediction confidence | D | L2 UNIT; L3 SKIP |
| [`boltz_predict`](boltz_predict.md) | Boltz co-folding prediction | D | L2 UNIT; L3 SKIP |
| [`bonett_seier`](bonett_seier.md) | Bonett-Seier Geary kurtosis test | C | L2 UNIT; L3 ROUTE |
| [`bonferroni`](bonferroni.md) | Bonferroni correction | C | L2 UNIT; L3 ROUTE |
| [`bootstrap_ci`](bootstrap_ci.md) | Bootstrap confidence interval | C | L2 UNIT; L3 ROUTE |
| [`boschloo_exact`](boschloo_exact.md) | Boschloo exact test | C | L2 UNIT; L3 ROUTE |
| [`box_cox`](box_cox.md) | Box-Cox transform | C | L2 UNIT; L3 ROUTE |
| [`box_m`](box_m.md) | Box's M test | C | L2 UNIT; L3 ROUTE |
| [`box_pierce`](box_pierce.md) | Box-Pierce autocorrelation test | C | L2 UNIT; L3 ROUTE |
| [`boxplot`](boxplot.md) | Boxplot | C | L2 UNIT; L3 ROUTE |
| [`bracken_reestimate`](bracken_reestimate.md) | Bracken genome-length abundance | C | L2 UNIT; L3 ROUTE |
| [`brennan_prediger`](brennan_prediger.md) | Brennan-Prediger coefficient | C | L2 UNIT; L3 ROUTE |
| [`breusch_godfrey`](breusch_godfrey.md) | Breusch-Godfrey serial correlation test | C | L2 UNIT; L3 ROUTE |
| [`breusch_pagan`](breusch_pagan.md) | Breusch-Pagan test | C | L2 UNIT; L3 ROUTE |
| [`brier_score`](brier_score.md) | Brier score (Cox) | C | L2 UNIT; L3 ROUTE |
| [`brown_forsythe`](brown_forsythe.md) | Brown-Forsythe variance test | C | L2 UNIT; L3 ROUTE |
| [`brunner_munzel`](brunner_munzel.md) | Brunner-Munzel test | C | L2 UNIT; L3 ROUTE |
| [`build_contacts`](build_contacts.md) | Build contact map | C | L2 UNIT; L3 ROUTE |
| [`by_adjust`](by_adjust.md) | Benjamini-Yekutieli FDR | C | L2 UNIT; L3 ROUTE |
| [`calibration_curve`](calibration_curve.md) | Calibration curve | B | L2 UNIT; L3 EXECUTED |
| [`calibration_slope`](calibration_slope.md) | Calibration intercept and slope | C | L2 UNIT; L3 ROUTE |
| [`calinski_harabasz`](calinski_harabasz.md) | Calinski-Harabasz index | C | L2 UNIT; L3 ROUTE |
| [`canonical_correlation`](canonical_correlation.md) | Canonical correlation | C | L2 UNIT; L3 ROUTE |
| [`causal_forest_ate`](causal_forest_ate.md) | Causal forest average treatment effect | C | L2 UNIT; L3 ROUTE |
| [`causal_forest_cate`](causal_forest_cate.md) | Causal forest conditional effects | C | L2 UNIT; L3 ROUTE |
| [`causal_forest_importance`](causal_forest_importance.md) | Causal forest feature importance | C | L2 UNIT; L3 ROUTE |
| [`cca`](cca.md) | Canonical correspondence analysis | C | L2 UNIT; L3 ROUTE |
| [`cdr3_properties`](cdr3_properties.md) | CDR3 amino-acid composition and properties | C | L2 UNIT; L3 ROUTE |
| [`cell_communication`](cell_communication.md) | cell_communication | C | L2 UNIT; L3 ROUTE |
| [`cell_cycle_score`](cell_cycle_score.md) | Cell cycle score | B | L2 UNIT; L3 EXECUTED |
| [`chacko_test`](chacko_test.md) | Chacko ordered alternatives test | C | L2 UNIT; L3 ROUTE |
| [`chain_coverage_summary`](chain_coverage_summary.md) | Chain coverage summary | C | L2 UNIT; L3 ROUTE |
| [`changepoint_pelt`](changepoint_pelt.md) | Change-point detection by exact penalised segmentation | C | L2 UNIT; L3 ROUTE |
| [`chao1`](chao1.md) | Chao1 richness estimator | B | L2 UNIT; L3 EXECUTED |
| [`checkm_quality_parse`](checkm_quality_parse.md) | CheckM/CheckM2 genome quality score | C | L2 UNIT; L3 ROUTE |
| [`chi_square`](chi_square.md) | Chi-square test | C | L2 UNIT; L3 ROUTE |
| [`chi_square_gof`](chi_square_gof.md) | Pearson chi-square goodness-of-fit test | C | L2 UNIT; L3 ROUTE |
| [`chisq_gof`](chisq_gof.md) | Chi-square goodness-of-fit test | C | L2 UNIT; L3 ROUTE |
| [`chisq_out_test`](chisq_out_test.md) | Chi-square outlier test | C | L2 UNIT; L3 ROUTE |
| [`chow_test`](chow_test.md) | Chow structural-break test | C | L2 UNIT; L3 ROUTE |
| [`chromatin_state_segmentation`](chromatin_state_segmentation.md) | Threshold-run chromatin segmentation | C | L2 UNIT; L3 ROUTE |
| [`circrna_detect`](circrna_detect.md) | Circular RNA junction detection | C | L2 UNIT; L3 ROUTE |
| [`classification_metrics`](classification_metrics.md) | Classification metrics | C | L2 UNIT; L3 ROUTE |
| [`cliffs_delta`](cliffs_delta.md) | Cliff's delta | C | L2 UNIT; L3 ROUTE |
| [`cluster_axis`](cluster_axis.md) | Clustering | C | L2 UNIT; L3 ROUTE |
| [`cnn_image_classifier`](cnn_image_classifier.md) | CNN image classifier | B | L2 UNIT; L3 EXECUTED |
| [`cochran_armitage`](cochran_armitage.md) | Cochran-Armitage trend test | C | L2 UNIT; L3 ROUTE |
| [`cochran_c_test`](cochran_c_test.md) | Cochran's C outlying variance test | B | L2 UNIT; L3 EXECUTED |
| [`cochran_q`](cochran_q.md) | Cochran's Q test | C | L2 UNIT; L3 ROUTE |
| [`coding_variant_filter`](coding_variant_filter.md) | coding_variant_filter | C | L2 UNIT; L3 ROUTE |
| [`codon_adaptation`](codon_adaptation.md) | Codon adaptation index | C | L2 UNIT; L3 ROUTE |
| [`codon_design_qc`](codon_design_qc.md) | Codon design QC | C | L2 UNIT; L3 ROUTE |
| [`codon_gc_harmonize`](codon_gc_harmonize.md) | Codon GC harmonisation | C | L2 UNIT; L3 ROUTE |
| [`codon_optimize`](codon_optimize.md) | Codon optimisation | C | L2 UNIT; L3 ROUTE |
| [`codon_usage`](codon_usage.md) | Codon usage | C | L2 UNIT; L3 ROUTE |
| [`codon_usage_bias`](codon_usage_bias.md) | Codon usage bias | C | L2 UNIT; L3 ROUTE |
| [`coexpression_modules`](coexpression_modules.md) | Co-expression modules from topological overlap | C | L2 UNIT; L3 ROUTE |
| [`cohens_d`](cohens_d.md) | Cohen's d | C | L2 UNIT; L3 ROUTE |
| [`cohens_h`](cohens_h.md) | Cohen's h | C | L2 UNIT; L3 ROUTE |
| [`cohens_kappa`](cohens_kappa.md) | Cohen's kappa | A | L2 ORACLE; L3 EXECUTED |
| [`colabfold_predict`](colabfold_predict.md) | ColabFold structure prediction | D | L2 UNIT; L3 SKIP |
| [`combat`](combat.md) | Batch correction | C | L2 UNIT; L3 ROUTE |
| [`compare_groups`](compare_groups.md) | Group comparison | C | L2 UNIT; L3 ROUTE |
| [`complement_nb_classifier`](complement_nb_classifier.md) | Complement Naive Bayes classifier | C | L2 UNIT; L3 ROUTE |
| [`concat`](concat.md) | 合并数据 | C | L2 UNIT; L3 ROUTE |
| [`concordance_correlation`](concordance_correlation.md) | Lin's concordance correlation | C | L2 UNIT; L3 ROUTE |
| [`concordance_index`](concordance_index.md) | Concordance index | C | L2 UNIT; L3 ROUTE |
| [`conditional_logistic`](conditional_logistic.md) | Conditional logistic regression | B | L2 UNIT; L3 EXECUTED |
| [`conditional_logit`](conditional_logit.md) | Conditional logistic regression | C | L2 UNIT; L3 ROUTE |
| [`conformal_classification_sets`](conformal_classification_sets.md) | Split conformal prediction sets for binary classification | C | L2 UNIT; L3 ROUTE |
| [`conformal_split_regression`](conformal_split_regression.md) | Split conformal prediction intervals for regression | A- | L2 ORACLE; L3 ROUTE |
| [`confusion_matrix`](confusion_matrix.md) | Confusion matrix | C | L2 UNIT; L3 ROUTE |
| [`conger_kappa`](conger_kappa.md) | Conger's kappa | C | L2 UNIT; L3 ROUTE |
| [`conover_test`](conover_test.md) | Conover post-hoc test | C | L2 UNIT; L3 ROUTE |
| [`consensus_sequence`](consensus_sequence.md) | consensus_sequence | C | L2 UNIT; L3 ROUTE |
| [`conserved_gene_order`](conserved_gene_order.md) | Conserved gene order between two genomes | C | L2 UNIT; L3 ROUTE |
| [`cooks_distance`](cooks_distance.md) | Cook's distance | C | L2 UNIT; L3 ROUTE |
| [`cophenetic_correlation`](cophenetic_correlation.md) | Cophenetic correlation | B | L2 UNIT; L3 EXECUTED |
| [`core_genome_size`](core_genome_size.md) | Core genome size and fractions | C | L2 UNIT; L3 ROUTE |
| [`correction`](correction.md) | FDR | C | L2 UNIT; L3 ROUTE |
| [`correlation`](correlation.md) | Correlation | C | L2 UNIT; L3 ROUTE |
| [`corresp`](corresp.md) | Correspondence analysis | C | L2 UNIT; L3 ROUTE |
| [`correspondence_analysis`](correspondence_analysis.md) | Correspondence analysis | C | L2 UNIT; L3 ROUTE |
| [`counts_normalize`](counts_normalize.md) | counts_normalize | C | L2 UNIT; L3 ROUTE |
| [`covratio`](covratio.md) | COVRATIO | C | L2 UNIT; L3 ROUTE |
| [`cox_regression`](cox_regression.md) | Cox | C | L2 UNIT; L3 ROUTE |
| [`cox_stuart`](cox_stuart.md) | Cox-Stuart trend test | C | L2 UNIT; L3 ROUTE |
| [`cox_stuart_test`](cox_stuart_test.md) | Cox-Stuart trend test | C | L2 UNIT; L3 ROUTE |
| [`cramer_v`](cramer_v.md) | Cramer's V | C | L2 UNIT; L3 ROUTE |
| [`cramer_von_mises`](cramer_von_mises.md) | Cramer-von Mises test | C | L2 UNIT; L3 ROUTE |
| [`crispr_array_detect`](crispr_array_detect.md) | CRISPR array detection | B | L2 UNIT; L3 EXECUTED |
| [`crispr_mit_specificity`](crispr_mit_specificity.md) | CRISPR MIT specificity | C | L2 UNIT; L3 ROUTE |
| [`cronbach_alpha`](cronbach_alpha.md) | Cronbach's alpha | C | L2 UNIT; L3 ROUTE |
| [`cross_correlation`](cross_correlation.md) | Cross-correlation function | C | L2 UNIT; L3 ROUTE |
| [`cumulative_incidence`](cumulative_incidence.md) | Cumulative incidence | C | L2 UNIT; L3 ROUTE |
| [`cusum_chart`](cusum_chart.md) | CUSUM control chart | C | L2 UNIT; L3 ROUTE |
| [`cuzick`](cuzick.md) | Cuzick's trend test | C | L2 UNIT; L3 ROUTE |
| [`cuzick_test`](cuzick_test.md) | Cuzick trend test | B | L2 UNIT; L3 EXECUTED |
| [`davies_bouldin`](davies_bouldin.md) | Davies-Bouldin index | C | L2 UNIT; L3 ROUTE |
| [`dbrda`](dbrda.md) | Distance-based redundancy analysis | B | L2 UNIT; L3 EXECUTED |
| [`dbscan`](dbscan.md) | DBSCAN clustering | C | L2 UNIT; L3 ROUTE |
| [`dca`](dca.md) | Decision curve analysis | C | L2 UNIT; L3 ROUTE |
| [`decision_curve`](decision_curve.md) | Decision curve analysis | C | L2 UNIT; L3 ROUTE |
| [`decision_tree_classifier`](decision_tree_classifier.md) | Decision Tree classifier | C | L2 UNIT; L3 ROUTE |
| [`decision_tree_regressor`](decision_tree_regressor.md) | Decision Tree regressor | C | L2 UNIT; L3 ROUTE |
| [`deep_quantile_regressor`](deep_quantile_regressor.md) | Linear quantile regressor | C | L2 UNIT; L3 ROUTE |
| [`deep_survival`](deep_survival.md) | DeepSurv Cox proportional hazards network | B | L2 UNIT; L3 EXECUTED |
| [`delong_auc`](delong_auc.md) | DeLong AUC | C | L2 UNIT; L3 ROUTE |
| [`deming_regression`](deming_regression.md) | Deming regression | C | L2 UNIT; L3 ROUTE |
| [`describe`](describe.md) | 数据概览 | C | L2 UNIT; L3 ROUTE |
| [`dfbetas`](dfbetas.md) | Standardized DFBETAS | C | L2 UNIT; L3 ROUTE |
| [`dffits`](dffits.md) | DFFITS | C | L2 UNIT; L3 ROUTE |
| [`dfgls`](dfgls.md) | DF-GLS unit-root test | B | L2 UNIT; L3 EXECUTED |
| [`difference_in_differences`](difference_in_differences.md) | Difference-in-differences estimate | C | L2 UNIT; L3 ROUTE |
| [`difference_sign`](difference_sign.md) | Difference-sign test | C | L2 UNIT; L3 ROUTE |
| [`distance_correlation`](distance_correlation.md) | Distance correlation | C | L2 UNIT; L3 ROUTE |
| [`distance_matrix`](distance_matrix.md) | Distance matrix | C | L2 UNIT; L3 ROUTE |
| [`diversity`](diversity.md) | Alpha diversity | C | L2 UNIT; L3 ROUTE |
| [`dmr_window_scan`](dmr_window_scan.md) | Differentially methylated window scan | C | L2 UNIT; L3 ROUTE |
| [`dotplot`](dotplot.md) | Dot plot | B | L2 UNIT; L3 EXECUTED |
| [`doublet_detect`](doublet_detect.md) | Doublet detection | C | L2 UNIT; L3 ROUTE |
| [`doubly_robust_ate`](doubly_robust_ate.md) | Doubly robust ATE (AIPW) | C | L2 UNIT; L3 ROUTE |
| [`drop`](drop.md) | 移除特征 | B | L2 UNIT; L3 EXECUTED |
| [`dunn_index`](dunn_index.md) | Dunn index | C | L2 UNIT; L3 ROUTE |
| [`dunn_test`](dunn_test.md) | Dunn post-hoc test | C | L2 UNIT; L3 ROUTE |
| [`durbin_test`](durbin_test.md) | Durbin test | C | L2 UNIT; L3 ROUTE |
| [`durbin_watson`](durbin_watson.md) | Durbin-Watson statistic | C | L2 UNIT; L3 ROUTE |
| [`dxy`](dxy.md) | Nei's Dxy (between-population divergence) | B | L2 UNIT; L3 EXECUTED |
| [`effective_population_size`](effective_population_size.md) | Effective population size from temporal allele frequencies | C | L2 UNIT; L3 ROUTE |
| [`egger_test`](egger_test.md) | Egger's test | C | L2 UNIT; L3 ROUTE |
| [`elastic_net_regressor`](elastic_net_regressor.md) | Elastic net regressor | C | L2 UNIT; L3 ROUTE |
| [`engle_granger`](engle_granger.md) | Engle-Granger cointegration test | C | L2 UNIT; L3 ROUTE |
| [`enrich_go`](enrich_go.md) | enrich_go | C | L2 UNIT; L3 ROUTE |
| [`enrichment_plot`](enrichment_plot.md) | enrichment_plot | C | L2 UNIT; L3 ROUTE |
| [`envfit`](envfit.md) | Environmental vector fitting | B | L2 UNIT; L3 EXECUTED |
| [`epidemic_case_fatality`](epidemic_case_fatality.md) | Case fatality ratio | C | L2 UNIT; L3 ROUTE |
| [`epidemic_growth_rate`](epidemic_growth_rate.md) | Early epidemic growth rate | C | L2 UNIT; L3 ROUTE |
| [`epidemic_r0`](epidemic_r0.md) | Basic reproduction number from growth | C | L2 UNIT; L3 ROUTE |
| [`epidemic_seir_fit`](epidemic_seir_fit.md) | SEIR model fit | C | L2 UNIT; L3 ROUTE |
| [`epidemic_sir_fit`](epidemic_sir_fit.md) | SIR model fit | C | L2 UNIT; L3 ROUTE |
| [`epitope_conservation`](epitope_conservation.md) | Per-position conservation of aligned epitope sequences | C | L2 UNIT; L3 ROUTE |
| [`esm3_embedding`](esm3_embedding.md) | ESM-3 蛋白嵌入 | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm3_fold`](esm3_fold.md) | ESM-3 结构预测 | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm3_inverse_folding`](esm3_inverse_folding.md) | ESM-3 逆折叠序列设计 | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm3_sasa_prediction`](esm3_sasa_prediction.md) | ESM-3 solvent accessibility prediction | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm3_secondary_structure`](esm3_secondary_structure.md) | ESM-3 secondary structure prediction | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm3_sequence_generation`](esm3_sequence_generation.md) | ESM-3 序列生成 | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_embedding`](esm_embedding.md) | ESM embeddings | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_embedding_autoencoder`](esm_embedding_autoencoder.md) | Embedding autoencoder | B | L2 UNIT; L3 EXECUTED |
| [`esm_embedding_isolation_forest`](esm_embedding_isolation_forest.md) | Embedding isolation forest | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_kmeans_silhouette`](esm_embedding_kmeans_silhouette.md) | Embedding k-means silhouette | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_knn_density`](esm_embedding_knn_density.md) | Embedding kNN density | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_linear_probe`](esm_embedding_linear_probe.md) | ESM embedding linear probe | B | L2 UNIT; L3 EXECUTED |
| [`esm_embedding_mlp_probe`](esm_embedding_mlp_probe.md) | ESM embedding MLP probe | B | L2 UNIT; L3 EXECUTED |
| [`esm_embedding_neighbors`](esm_embedding_neighbors.md) | ESM embedding neighbours | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_outlier_scan`](esm_embedding_outlier_scan.md) | ESM Embedding Outlier Scan | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_pca`](esm_embedding_pca.md) | ESM embedding PCA | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_pca_loadings`](esm_embedding_pca_loadings.md) | Embedding PCA loadings | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_pca_reconstruction`](esm_embedding_pca_reconstruction.md) | Embedding PCA reconstruction | C | L2 UNIT; L3 ROUTE |
| [`esm_embedding_ridge_probe`](esm_embedding_ridge_probe.md) | Embedding ridge regression probe | B | L2 UNIT; L3 EXECUTED |
| [`esm_embedding_umap_projection`](esm_embedding_umap_projection.md) | Embedding spectral projection | C | L2 UNIT; L3 ROUTE |
| [`esm_if_design`](esm_if_design.md) | ESM-IF Design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_if_interface_redesign`](esm_if_interface_redesign.md) | ESM-IF 界面重设计 | D | L2 UNIT; L3 SKIP |
| [`esm_if_masked_region_scan`](esm_if_masked_region_scan.md) | ESM-IF Masked Region Scan | D | L2 UNIT; L3 SKIP |
| [`esm_if_mutation_scan`](esm_if_mutation_scan.md) | ESM-IF Mutation Scan | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_if_position_entropy`](esm_if_position_entropy.md) | ESM-IF Position Entropy | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_if_redesign`](esm_if_redesign.md) | ESM-IF Partial Redesign | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_if_score`](esm_if_score.md) | ESM-IF Score | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_masked_marginal`](esm_masked_marginal.md) | ESM masked marginal | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_pseudo_likelihood`](esm_pseudo_likelihood.md) | ESM masked pseudo-likelihood | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esm_variant_effect`](esm_variant_effect.md) | ESM variant effect scan | B | L2 UNIT; L3 EXECUTED_SRV |
| [`esmfold_predict`](esmfold_predict.md) | ESMFold structure prediction | B | L2 UNIT; L3 EXECUTED |
| [`eta_squared`](eta_squared.md) | Eta squared | C | L2 UNIT; L3 ROUTE |
| [`event_study`](event_study.md) | Event-study coefficients | C | L2 UNIT; L3 ROUTE |
| [`ewma_chart`](ewma_chart.md) | EWMA control chart | C | L2 UNIT; L3 ROUTE |
| [`exon_skipping`](exon_skipping.md) | Exon skipping | C | L2 UNIT; L3 ROUTE |
| [`explode`](explode.md) | explode | B | L2 UNIT; L3 EXECUTED |
| [`export_results`](export_results.md) | Export results | B | L2 UNIT; L3 EXECUTED |
| [`extra_trees_classifier`](extra_trees_classifier.md) | Extra Trees classifier | C | L2 UNIT; L3 ROUTE |
| [`extra_trees_regressor`](extra_trees_regressor.md) | Extra Trees regressor | C | L2 UNIT; L3 ROUTE |
| [`factor_analysis`](factor_analysis.md) | Factor analysis | C | L2 UNIT; L3 ROUTE |
| [`faith_pd`](faith_pd.md) | Faith's phylogenetic diversity | B | L2 UNIT; L3 EXECUTED |
| [`fastq_adapter_scan`](fastq_adapter_scan.md) | fastq_adapter_scan | C | L2 UNIT; L3 ROUTE |
| [`fastq_adapter_trim`](fastq_adapter_trim.md) | fastq_adapter_trim | C | L2 UNIT; L3 ROUTE |
| [`fastq_deduplicate`](fastq_deduplicate.md) | fastq_deduplicate | C | L2 UNIT; L3 ROUTE |
| [`fastq_duplication_profile`](fastq_duplication_profile.md) | fastq_duplication_profile | C | L2 UNIT; L3 ROUTE |
| [`fastq_gc_distribution`](fastq_gc_distribution.md) | fastq_gc_distribution | C | L2 UNIT; L3 ROUTE |
| [`fastq_overrepresented`](fastq_overrepresented.md) | fastq_overrepresented | C | L2 UNIT; L3 ROUTE |
| [`fastq_quality_profile`](fastq_quality_profile.md) | fastq_quality_profile | C | L2 UNIT; L3 ROUTE |
| [`fastq_quality_trim`](fastq_quality_trim.md) | fastq_quality_trim | C | L2 UNIT; L3 ROUTE |
| [`fastq_stats`](fastq_stats.md) | fastq_stats | C | L2 UNIT; L3 ROUTE |
| [`fba_flux_balance`](fba_flux_balance.md) | Flux balance analysis | B | L2 UNIT; L3 EXECUTED |
| [`fba_flux_distribution`](fba_flux_distribution.md) | FBA flux distribution | C | L2 UNIT; L3 ROUTE |
| [`fba_flux_variability`](fba_flux_variability.md) | FBA flux variability | C | L2 UNIT; L3 ROUTE |
| [`fba_gene_knockout`](fba_gene_knockout.md) | FBA gene knockout | C | L2 UNIT; L3 ROUTE |
| [`filter_by`](filter_by.md) | Filter by metrics | C | L2 UNIT; L3 ROUTE |
| [`filter_min`](filter_min.md) | 低表达过滤 | C | L2 UNIT; L3 ROUTE |
| [`find_orfs`](find_orfs.md) | find_orfs | C | L2 UNIT; L3 ROUTE |
| [`fine_gray`](fine_gray.md) | Fine-Gray subdistribution regression | C | L2 UNIT; L3 ROUTE |
| [`fisher_alpha`](fisher_alpha.md) | Fisher's alpha | C | L2 UNIT; L3 ROUTE |
| [`fisher_combined`](fisher_combined.md) | Fisher combined p-value | C | L2 UNIT; L3 ROUTE |
| [`fisher_exact`](fisher_exact.md) | Fisher exact test | C | L2 UNIT; L3 ROUTE |
| [`fleiss_kappa`](fleiss_kappa.md) | Fleiss' kappa | C | L2 UNIT; L3 ROUTE |
| [`fligner_killeen`](fligner_killeen.md) | Fligner-Killeen variance homogeneity test | C | L2 UNIT; L3 ROUTE |
| [`fligner_kruskal`](fligner_kruskal.md) | Fligner-Killeen test | C | L2 UNIT; L3 ROUTE |
| [`fligner_wolfe`](fligner_wolfe.md) | Fligner-Wolfe test | C | L2 UNIT; L3 ROUTE |
| [`flow_compensate`](flow_compensate.md) | Flow cytometry compensation | C | L2 UNIT; L3 ROUTE |
| [`flow_gate`](flow_gate.md) | Flow cytometry rectangular gate | C | L2 UNIT; L3 ROUTE |
| [`flow_transform`](flow_transform.md) | Flow cytometry arcsinh transform | C | L2 UNIT; L3 ROUTE |
| [`flye_assemble`](flye_assemble.md) | Flye de novo assembly | B | L2 UNIT; L3 EXECUTED |
| [`foldseek_align`](foldseek_align.md) | Foldseek structural alignment | B | L2 UNIT; L3 EXECUTED |
| [`foldseek_cluster`](foldseek_cluster.md) | Foldseek structural clustering | B | L2 SKIP; L3 EXECUTED |
| [`foldseek_search`](foldseek_search.md) | Foldseek structural search | B | L2 UNIT; L3 EXECUTED |
| [`forest_plot`](forest_plot.md) | Forest plot | C | L2 UNIT; L3 ROUTE |
| [`fowlkes_mallows`](fowlkes_mallows.md) | Fowlkes-Mallows index | C | L2 UNIT; L3 ROUTE |
| [`friedman`](friedman.md) | Friedman test | C | L2 UNIT; L3 ROUTE |
| [`fst`](fst.md) | Fst | B | L2 UNIT; L3 EXECUTED |
| [`fst_outlier_scan`](fst_outlier_scan.md) | Fst outlier scan | C | L2 UNIT; L3 ROUTE |
| [`g_test`](g_test.md) | G-test of independence | C | L2 UNIT; L3 ROUTE |
| [`games_howell`](games_howell.md) | Games-Howell post-hoc test | C | L2 UNIT; L3 ROUTE |
| [`gamma_regression`](gamma_regression.md) | Gamma regression | C | L2 UNIT; L3 ROUTE |
| [`garch`](garch.md) | GARCH volatility model | B | L2 UNIT; L3 EXECUTED |
| [`gaussian_mixture`](gaussian_mixture.md) | Gaussian mixture clustering | C | L2 UNIT; L3 ROUTE |
| [`gaussian_process_regressor`](gaussian_process_regressor.md) | Gaussian-process regression | C | L2 UNIT; L3 ROUTE |
| [`gaussian_random_projection`](gaussian_random_projection.md) | Gaussian random projection | C | L2 UNIT; L3 ROUTE |
| [`gc_skew_profile`](gc_skew_profile.md) | gc_skew_profile | B | L2 SKIP; L3 EXECUTED |
| [`gcn_node_classifier`](gcn_node_classifier.md) | GCN node classifier | B | L2 UNIT; L3 EXECUTED |
| [`gene_list_to_hits`](gene_list_to_hits.md) | gene_list_to_hits | E | L2 SKIP; L3 ROUTE |
| [`gene_structure`](gene_structure.md) | gene_structure | C | L2 UNIT; L3 ROUTE |
| [`genome_alignment_stats`](genome_alignment_stats.md) | Genome alignment statistics | C | L2 UNIT; L3 ROUTE |
| [`genome_cds_check`](genome_cds_check.md) | CDS translation check | C | L2 UNIT; L3 ROUTE |
| [`genome_gene_density`](genome_gene_density.md) | Windowed gene density | C | L2 UNIT; L3 ROUTE |
| [`genome_intergenic_regions`](genome_intergenic_regions.md) | Intergenic regions | C | L2 UNIT; L3 ROUTE |
| [`genome_kmer_similarity`](genome_kmer_similarity.md) | Genome k-mer Jaccard similarity | C | L2 UNIT; L3 ROUTE |
| [`genome_kmer_spectrum`](genome_kmer_spectrum.md) | Genome k-mer spectrum | C | L2 UNIT; L3 ROUTE |
| [`genome_mash_distance`](genome_mash_distance.md) | Mash distance and ANI | C | L2 UNIT; L3 ROUTE |
| [`genome_promoter_extract`](genome_promoter_extract.md) | Promoter window extraction | C | L2 UNIT; L3 ROUTE |
| [`genome_rearrangement`](genome_rearrangement.md) | Rearrangement breakpoints between two genomes | C | L2 UNIT; L3 ROUTE |
| [`genome_rearrangement_summary`](genome_rearrangement_summary.md) | Genome rearrangement summary | C | L2 UNIT; L3 ROUTE |
| [`genome_synteny_blocks`](genome_synteny_blocks.md) | Genome synteny blocks | C | L2 UNIT; L3 ROUTE |
| [`genomic_selection_rrblup`](genomic_selection_rrblup.md) | Genomic selection (rrBLUP) | B | L2 UNIT; L3 EXECUTED |
| [`genotype_allele_balance`](genotype_allele_balance.md) | Genotype allele balance | C | L2 UNIT; L3 ROUTE |
| [`genotype_call_rate_qc`](genotype_call_rate_qc.md) | Per-sample genotype call rate | A- | L2 ORACLE; L3 ROUTE |
| [`genotype_filter`](genotype_filter.md) | genotype_filter | C | L2 UNIT; L3 ROUTE |
| [`genotype_grm`](genotype_grm.md) | Genotype relationship matrix | C | L2 UNIT; L3 ROUTE |
| [`genotype_mendelian_error`](genotype_mendelian_error.md) | Trio Mendelian error scan | C | L2 UNIT; L3 ROUTE |
| [`genotype_pca`](genotype_pca.md) | Genotype PCA | C | L2 UNIT; L3 ROUTE |
| [`genotype_pca_loadings`](genotype_pca_loadings.md) | Genotype PCA loadings | C | L2 UNIT; L3 ROUTE |
| [`gff_feature_stats`](gff_feature_stats.md) | gff_feature_stats | C | L2 UNIT; L3 ROUTE |
| [`glmm_logistic`](glmm_logistic.md) | Logistic mixed model | B | L2 UNIT; L3 EXECUTED |
| [`go_gene_similarity`](go_gene_similarity.md) | GO gene semantic similarity | C | L2 UNIT; L3 ROUTE |
| [`go_ic_profile`](go_ic_profile.md) | GO information content profile | C | L2 UNIT; L3 ROUTE |
| [`go_term_similarity`](go_term_similarity.md) | GO term semantic similarity | C | L2 UNIT; L3 ROUTE |
| [`goldfeld_quandt`](goldfeld_quandt.md) | Goldfeld-Quandt test | C | L2 UNIT; L3 ROUTE |
| [`goodman_kruskal_gamma`](goodman_kruskal_gamma.md) | Goodman-Kruskal gamma | C | L2 UNIT; L3 ROUTE |
| [`gower_distance`](gower_distance.md) | Gower distance | C | L2 UNIT; L3 ROUTE |
| [`gradient_boosting_classifier`](gradient_boosting_classifier.md) | Gradient Boosting classifier | E | L2 SKIP; L3 ROUTE |
| [`gradient_boosting_regressor`](gradient_boosting_regressor.md) | Gradient Boosting regressor | D | L2 SMOKE; L3 ROUTE |
| [`granger_causality`](granger_causality.md) | Granger causality test | B | L2 UNIT; L3 EXECUTED |
| [`graph_pseudotime`](graph_pseudotime.md) | Graph pseudotime | C | L2 UNIT; L3 ROUTE |
| [`grubbs_test`](grubbs_test.md) | Grubbs outlier test | C | L2 UNIT; L3 ROUTE |
| [`gsea`](gsea.md) | Preranked GSEA | C | L2 UNIT; L3 ROUTE |
| [`gsva_plage`](gsva_plage.md) | GSVA PLAGE scores | C | L2 UNIT; L3 ROUTE |
| [`gtdb_taxonomy_parse`](gtdb_taxonomy_parse.md) | GTDB taxonomy rank completeness | C | L2 UNIT; L3 ROUTE |
| [`gwas_association`](gwas_association.md) | GWAS association testing | C | L2 UNIT; L3 ROUTE |
| [`gwas_inflation`](gwas_inflation.md) | GWAS genomic inflation | C | L2 UNIT; L3 ROUTE |
| [`gwas_top_hits`](gwas_top_hits.md) | GWAS top hits | C | L2 UNIT; L3 ROUTE |
| [`gwet_ac1`](gwet_ac1.md) | Gwet's AC1 | C | L2 UNIT; L3 ROUTE |
| [`haplotype_blocks`](haplotype_blocks.md) | Haplotype blocks from adjacent linkage disequilibrium | C | L2 UNIT; L3 ROUTE |
| [`haplotype_diversity`](haplotype_diversity.md) | Haplotype and nucleotide diversity | B | L2 UNIT; L3 EXECUTED |
| [`hardy_weinberg`](hardy_weinberg.md) | Hardy-Weinberg equilibrium | B | L2 UNIT; L3 EXECUTED |
| [`harvey_collier`](harvey_collier.md) | Harvey-Collier linearity test | C | L2 UNIT; L3 ROUTE |
| [`hdbscan`](hdbscan.md) | HDBSCAN clustering | C | L2 UNIT; L3 ROUTE |
| [`hdbscan_cluster`](hdbscan_cluster.md) | HDBSCAN density clustering | C | L2 UNIT; L3 ROUTE |
| [`heatmap`](heatmap.md) | Heatmap | C | L2 UNIT; L3 ROUTE |
| [`heterozygosity`](heterozygosity.md) | Heterozygosity | B | L2 UNIT; L3 EXECUTED |
| [`hic_contact_matrix`](hic_contact_matrix.md) | hic_contact_matrix | C | L2 UNIT; L3 ROUTE |
| [`hic_distance_decay`](hic_distance_decay.md) | hic_distance_decay | C | L2 UNIT; L3 ROUTE |
| [`hic_pair_stats`](hic_pair_stats.md) | hic_pair_stats | C | L2 UNIT; L3 ROUTE |
| [`hidden_markov_viterbi`](hidden_markov_viterbi.md) | Viterbi decoding for a discrete hidden Markov model | C | L2 UNIT; L3 ROUTE |
| [`hierarchical_clustering`](hierarchical_clustering.md) | Hierarchical clustering | C | L2 UNIT; L3 ROUTE |
| [`histogram`](histogram.md) | 直方图 | C | L2 UNIT; L3 ROUTE |
| [`hmm_baum_welch`](hmm_baum_welch.md) | Baum-Welch HMM training | C | L2 UNIT; L3 ROUTE |
| [`hmmer_domains`](hmmer_domains.md) | HMMER domain annotation | B | L2 UNIT; L3 EXECUTED |
| [`holm_adjust`](holm_adjust.md) | Holm adjustment | C | L2 UNIT; L3 ROUTE |
| [`homogeneity_completeness_v_measure`](homogeneity_completeness_v_measure.md) | Homogeneity, completeness, V-measure | C | L2 UNIT; L3 ROUTE |
| [`hosmer_lemeshow`](hosmer_lemeshow.md) | Hosmer-Lemeshow test | C | L2 UNIT; L3 ROUTE |
| [`hotelling_t2`](hotelling_t2.md) | Hotelling's T-squared | C | L2 UNIT; L3 ROUTE |
| [`huber_regressor`](huber_regressor.md) | Huber regressor | C | L2 UNIT; L3 ROUTE |
| [`humann_pathway_abundance`](humann_pathway_abundance.md) | HUMAnN pathway abundance summary | C | L2 UNIT; L3 ROUTE |
| [`humann_pathway_collapse`](humann_pathway_collapse.md) | Collapse stratified HUMAnN pathways to community totals | C | L2 UNIT; L3 ROUTE |
| [`hurst_exponent`](hurst_exponent.md) | Hurst exponent (simple R/S) | C | L2 UNIT; L3 ROUTE |
| [`hvg`](hvg.md) | Highly variable genes | C | L2 UNIT; L3 ROUTE |
| [`hwe`](hwe.md) | HWE | C | L2 UNIT; L3 ROUTE |
| [`ibd_segments`](ibd_segments.md) | Identity-by-descent segments from IBS calls | C | L2 UNIT; L3 ROUTE |
| [`ica`](ica.md) | ICA | D | L2 SMOKE; L3 ROUTE |
| [`ihs_selection`](ihs_selection.md) | Integrated haplotype score from biallelic haplotypes | C | L2 UNIT; L3 ROUTE |
| [`image_connected_components`](image_connected_components.md) | Connected components | C | L2 UNIT; L3 ROUTE |
| [`image_gaussian_blur`](image_gaussian_blur.md) | Gaussian image blur | A- | L2 ORACLE; L3 ROUTE |
| [`image_histogram_equalization`](image_histogram_equalization.md) | Histogram equalization | C | L2 UNIT; L3 ROUTE |
| [`image_otsu_threshold`](image_otsu_threshold.md) | Otsu image threshold | C | L2 UNIT; L3 ROUTE |
| [`image_sobel_gradient`](image_sobel_gradient.md) | Sobel gradient magnitude | A- | L2 ORACLE; L3 ROUTE |
| [`impute`](impute.md) | 缺失值填补 | C | L2 UNIT; L3 ROUTE |
| [`indicator_species`](indicator_species.md) | Indicator species | C | L2 UNIT; L3 ROUTE |
| [`integrated_brier_score`](integrated_brier_score.md) | Integrated Brier score (Cox) | C | L2 UNIT; L3 ROUTE |
| [`integrated_discrimination_improvement`](integrated_discrimination_improvement.md) | Integrated discrimination improvement | C | L2 UNIT; L3 ROUTE |
| [`interface_alanine_scan`](interface_alanine_scan.md) | Interface alanine scan | B | L2 UNIT; L3 EXECUTED |
| [`interface_bsa`](interface_bsa.md) | Interface buried area | C | L2 UNIT; L3 ROUTE |
| [`interface_contact_map`](interface_contact_map.md) | Interface contact map | C | L2 UNIT; L3 ROUTE |
| [`interface_distance_histogram`](interface_distance_histogram.md) | Interface distance histogram | C | L2 UNIT; L3 ROUTE |
| [`interface_hbond_network`](interface_hbond_network.md) | Interface hydrogen bond network | C | L2 UNIT; L3 ROUTE |
| [`interface_hotspots`](interface_hotspots.md) | Interface hotspots | C | L2 UNIT; L3 ROUTE |
| [`interface_hydrophobic_patch`](interface_hydrophobic_patch.md) | Interface Hydrophobic Patches | C | L2 UNIT; L3 ROUTE |
| [`interface_mmgbsa_delta`](interface_mmgbsa_delta.md) | MM/GBSA binding energy | B | L2 UNIT; L3 EXECUTED |
| [`interpro_domain_summary`](interpro_domain_summary.md) | InterPro domain summary | C | L2 UNIT; L3 ROUTE |
| [`interval_annotate`](interval_annotate.md) | Annotate intervals by feature class | C | L2 UNIT; L3 ROUTE |
| [`interval_censored_regression`](interval_censored_regression.md) | Interval-censored Weibull AFT | C | L2 UNIT; L3 ROUTE |
| [`interval_coverage`](interval_coverage.md) | Coverage of feature classes by intervals | C | L2 UNIT; L3 ROUTE |
| [`interval_jaccard`](interval_jaccard.md) | Jaccard similarity of two interval sets | C | L2 UNIT; L3 ROUTE |
| [`interval_merge`](interval_merge.md) | interval_merge | C | L2 UNIT; L3 ROUTE |
| [`interval_overlap`](interval_overlap.md) | interval_overlap | E | L2 SKIP; L3 ROUTE |
| [`interval_stats`](interval_stats.md) | interval_stats | E | L2 SKIP; L3 ROUTE |
| [`intraclass_correlation`](intraclass_correlation.md) | Intraclass correlation | C | L2 UNIT; L3 ROUTE |
| [`intron_retention`](intron_retention.md) | Intron retention | C | L2 UNIT; L3 ROUTE |
| [`inverse_gaussian_regression`](inverse_gaussian_regression.md) | Inverse Gaussian regression | B | L2 UNIT; L3 EXECUTED |
| [`iptw_effect`](iptw_effect.md) | IPTW treatment effect | C | L2 UNIT; L3 ROUTE |
| [`isoform_quantification_em`](isoform_quantification_em.md) | Isoform quantification (EM) | B | L2 UNIT; L3 EXECUTED |
| [`isolation_forest`](isolation_forest.md) | Isolation Forest | C | L2 UNIT; L3 ROUTE |
| [`isolation_forest_anomaly`](isolation_forest_anomaly.md) | Isolation-forest anomaly scores | C | L2 UNIT; L3 ROUTE |
| [`isomap`](isomap.md) | Isomap | C | L2 UNIT; L3 ROUTE |
| [`isotonic`](isotonic.md) | Isotonic regression | C | L2 UNIT; L3 ROUTE |
| [`iv_2sls`](iv_2sls.md) | Two-stage least squares | C | L2 UNIT; L3 ROUTE |
| [`jarque_bera`](jarque_bera.md) | Jarque-Bera normality test | C | L2 UNIT; L3 ROUTE |
| [`johansen`](johansen.md) | Johansen cointegration test | B | L2 UNIT; L3 EXECUTED |
| [`join`](join.md) | Join | C | L2 UNIT; L3 ROUTE |
| [`jonckheere_terpstra`](jonckheere_terpstra.md) | Jonckheere-Terpstra test | C | L2 UNIT; L3 ROUTE |
| [`kalman_local_level`](kalman_local_level.md) | Kalman filter for a local-level state-space model | A- | L2 ORACLE; L3 ROUTE |
| [`kalman_smoother`](kalman_smoother.md) | Rauch-Tung-Striebel Kalman smoother | C | L2 UNIT; L3 ROUTE |
| [`kaplan_meier`](kaplan_meier.md) | KM | C | L2 UNIT; L3 ROUTE |
| [`kendall_tau`](kendall_tau.md) | Kendall tau | C | L2 UNIT; L3 ROUTE |
| [`kendall_w`](kendall_w.md) | Kendall's W | C | L2 UNIT; L3 ROUTE |
| [`kernel_pca`](kernel_pca.md) | Kernel PCA | C | L2 UNIT; L3 ROUTE |
| [`kernel_shap`](kernel_shap.md) | KernelSHAP linear attribution | C | L2 UNIT; L3 ROUTE |
| [`kmer_count`](kmer_count.md) | kmer_count | D | L2 SMOKE; L3 ROUTE |
| [`kmo_test`](kmo_test.md) | KMO sampling adequacy | C | L2 UNIT; L3 ROUTE |
| [`knn`](knn.md) | k nearest neighbours classifier | C | L2 UNIT; L3 ROUTE |
| [`kpss_test`](kpss_test.md) | KPSS stationarity test | C | L2 UNIT; L3 ROUTE |
| [`kraken_kreport_parse`](kraken_kreport_parse.md) | Kraken kreport rank summary | C | L2 UNIT; L3 ROUTE |
| [`krippendorff_alpha`](krippendorff_alpha.md) | Krippendorff's alpha | C | L2 UNIT; L3 ROUTE |
| [`kruskal`](kruskal.md) | Kruskal-Wallis test | C | L2 UNIT; L3 ROUTE |
| [`ks_2samp`](ks_2samp.md) | Two-sample KS test | C | L2 UNIT; L3 ROUTE |
| [`lasso_regression`](lasso_regression.md) | Lasso regression | D | L2 SMOKE; L3 ROUTE |
| [`ld_decay`](ld_decay.md) | LD decay | C | L2 UNIT; L3 ROUTE |
| [`ld_matrix`](ld_matrix.md) | ld_matrix | C | L2 UNIT; L3 ROUTE |
| [`ld_prune`](ld_prune.md) | LD pruning | D | L2 SMOKE; L3 ROUTE |
| [`lda`](lda.md) | Linear discriminant analysis | C | L2 UNIT; L3 ROUTE |
| [`lda_classifier`](lda_classifier.md) | Linear Discriminant Analysis classifier | C | L2 UNIT; L3 ROUTE |
| [`leave_one_out`](leave_one_out.md) | Leave-one-out meta-analysis | B | L2 UNIT; L3 EXECUTED |
| [`levene`](levene.md) | Levene variance test | C | L2 UNIT; L3 ROUTE |
| [`levene_test`](levene_test.md) | Levene variance homogeneity test | C | L2 UNIT; L3 ROUTE |
| [`leverage`](leverage.md) | OLS leverage | B | L2 UNIT; L3 EXECUTED |
| [`lfq_median_normalize`](lfq_median_normalize.md) | Median-normalize an LFQ matrix | C | L2 UNIT; L3 ROUTE |
| [`lfq_quantile_normalize`](lfq_quantile_normalize.md) | Quantile-normalize an LFQ matrix | C | L2 UNIT; L3 ROUTE |
| [`liftover_intervals`](liftover_intervals.md) | liftOver intervals | C | L2 UNIT; L3 ROUTE |
| [`liftover_variants`](liftover_variants.md) | liftOver variants | C | L2 UNIT; L3 ROUTE |
| [`ligand_adduct_mz`](ligand_adduct_mz.md) | Ligand adduct m/z | C | L2 UNIT; L3 ROUTE |
| [`ligand_brics_fragments`](ligand_brics_fragments.md) | Ligand BRICS fragments | C | L2 UNIT; L3 ROUTE |
| [`ligand_contact_profile`](ligand_contact_profile.md) | Ligand contact profile | B | L2 UNIT; L3 EXECUTED |
| [`ligand_dbe`](ligand_dbe.md) | Ligand double-bond equivalents | C | L2 UNIT; L3 ROUTE |
| [`ligand_efficiency`](ligand_efficiency.md) | Ligand efficiency metrics | C | L2 UNIT; L3 ROUTE |
| [`ligand_exact_mass`](ligand_exact_mass.md) | Ligand exact mass | C | L2 UNIT; L3 ROUTE |
| [`ligand_formula_parse`](ligand_formula_parse.md) | Ligand formula parse | C | L2 UNIT; L3 ROUTE |
| [`ligand_isotope_pattern`](ligand_isotope_pattern.md) | Ligand isotope pattern | C | L2 UNIT; L3 ROUTE |
| [`ligand_mass_fraction`](ligand_mass_fraction.md) | Ligand element mass fraction | C | L2 UNIT; L3 ROUTE |
| [`ligand_molecular_formula`](ligand_molecular_formula.md) | Ligand molecular formula | C | L2 UNIT; L3 ROUTE |
| [`ligand_nitrogen_rule`](ligand_nitrogen_rule.md) | Ligand nitrogen rule | C | L2 UNIT; L3 ROUTE |
| [`ligand_pdbqt_flexible`](ligand_pdbqt_flexible.md) | 柔性配体 PDBQT 准备（扭转树） | C | L2 UNIT; L3 ROUTE |
| [`ligand_pdbqt_prepare`](ligand_pdbqt_prepare.md) | Ligand PDBQT preparation | C | L2 UNIT; L3 ROUTE |
| [`ligand_rgroup_decomposition`](ligand_rgroup_decomposition.md) | Ligand R-group decomposition | C | L2 UNIT; L3 ROUTE |
| [`ligandmpnn_active_site_design`](ligandmpnn_active_site_design.md) | LigandMPNN Active Site Design | B | L2 UNIT; L3 EXECUTED |
| [`ligandmpnn_design`](ligandmpnn_design.md) | LigandMPNN Design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`ligandmpnn_score`](ligandmpnn_score.md) | LigandMPNN Score | B | L2 UNIT; L3 EXECUTED_SRV |
| [`ligandmpnn_side_chain_packing`](ligandmpnn_side_chain_packing.md) | LigandMPNN side-chain packing | D | L2 UNIT; L3 SKIP |
| [`lightgbm_classifier`](lightgbm_classifier.md) | LightGBM binary classifier | C | L2 UNIT; L3 ROUTE |
| [`lillie_test`](lillie_test.md) | Lilliefors normality test | C | L2 UNIT; L3 ROUTE |
| [`lilliefors_test`](lilliefors_test.md) | Lilliefors normality test | C | L2 UNIT; L3 ROUTE |
| [`limma_de`](limma_de.md) | Moderated t differential analysis | C | L2 UNIT; L3 ROUTE |
| [`line`](line.md) | 折线图 | B | L2 UNIT; L3 EXECUTED |
| [`linear_mixed_model`](linear_mixed_model.md) | Linear mixed model | C | L2 UNIT; L3 ROUTE |
| [`linear_regression`](linear_regression.md) | Linear regression | C | L2 UNIT; L3 ROUTE |
| [`ljung_box`](ljung_box.md) | Ljung-Box autocorrelation test | C | L2 UNIT; L3 ROUTE |
| [`locally_linear_embedding`](locally_linear_embedding.md) | Locally linear embedding | C | L2 UNIT; L3 ROUTE |
| [`lof_outlier_score`](lof_outlier_score.md) | Local outlier factor | C | L2 UNIT; L3 ROUTE |
| [`log_transform`](log_transform.md) | Log | C | L2 UNIT; L3 ROUTE |
| [`logistic_regression`](logistic_regression.md) | Logistic regression | E | L2 SKIP; L3 ROUTE |
| [`logrank_test`](logrank_test.md) | Log-rank | C | L2 UNIT; L3 ROUTE |
| [`lowess`](lowess.md) | LOWESS smoother | C | L2 UNIT; L3 ROUTE |
| [`ma_plot`](ma_plot.md) | MA plot | C | L2 UNIT; L3 ROUTE |
| [`mack_wolfe`](mack_wolfe.md) | Mack-Wolfe umbrella test | B | L2 UNIT; L3 EXECUTED |
| [`maf`](maf.md) | MAF | C | L2 UNIT; L3 ROUTE |
| [`mahalanobis_distance`](mahalanobis_distance.md) | Mahalanobis distance | B | L2 UNIT; L3 EXECUTED |
| [`manhattan`](manhattan.md) | 曼哈顿图 | C | L2 UNIT; L3 ROUTE |
| [`mann_kendall`](mann_kendall.md) | Mann-Kendall trend | C | L2 UNIT; L3 ROUTE |
| [`mann_whitney`](mann_whitney.md) | Mann-Whitney U test | C | L2 UNIT; L3 ROUTE |
| [`manova`](manova.md) | One-way MANOVA | B | L2 UNIT; L3 EXECUTED |
| [`mantel`](mantel.md) | Mantel test | C | L2 UNIT; L3 ROUTE |
| [`mantel_haenszel`](mantel_haenszel.md) | Mantel-Haenszel test | C | L2 UNIT; L3 ROUTE |
| [`mardia_test`](mardia_test.md) | Mardia multivariate normality test | B | L2 UNIT; L3 EXECUTED |
| [`marker_score`](marker_score.md) | Signature score | C | L2 UNIT; L3 ROUTE |
| [`mauchly_test`](mauchly_test.md) | Mauchly's sphericity test | B | L2 UNIT; L3 EXECUTED |
| [`mcnemar`](mcnemar.md) | McNemar test | C | L2 UNIT; L3 ROUTE |
| [`mds`](mds.md) | Multidimensional scaling | C | L2 UNIT; L3 ROUTE |
| [`mediation_analysis`](mediation_analysis.md) | Mediation analysis | C | L2 UNIT; L3 ROUTE |
| [`meta_analysis`](meta_analysis.md) | Meta-analysis | C | L2 UNIT; L3 ROUTE |
| [`meta_regression`](meta_regression.md) | Meta-regression | B | L2 UNIT; L3 EXECUTED |
| [`metabolite_adduct_annotation`](metabolite_adduct_annotation.md) | Metabolite adduct annotation | C | L2 UNIT; L3 ROUTE |
| [`metabolite_mass_match`](metabolite_mass_match.md) | Metabolite mass match | C | L2 UNIT; L3 ROUTE |
| [`metabolite_set_enrichment`](metabolite_set_enrichment.md) | Metabolite set enrichment | C | L2 UNIT; L3 ROUTE |
| [`metagenomics_bray_curtis`](metagenomics_bray_curtis.md) | Bray-Curtis dissimilarity | C | L2 UNIT; L3 ROUTE |
| [`metagenomics_clr`](metagenomics_clr.md) | Centered log-ratio transform | C | L2 UNIT; L3 ROUTE |
| [`metaphlan_profile_merge`](metaphlan_profile_merge.md) | Merge two MetaPhlAn profiles | C | L2 UNIT; L3 ROUTE |
| [`metaphlan_profile_parse`](metaphlan_profile_parse.md) | MetaPhlAn rank profile summary | C | L2 UNIT; L3 ROUTE |
| [`methylation_beta_value`](methylation_beta_value.md) | Methylation beta values | C | L2 UNIT; L3 ROUTE |
| [`methylation_m_value`](methylation_m_value.md) | Methylation M values | C | L2 UNIT; L3 ROUTE |
| [`mhc_anchor_score`](mhc_anchor_score.md) | Heuristic MHC-I anchor score for 9-mer peptides | C | L2 UNIT; L3 ROUTE |
| [`mhc_binding_motif`](mhc_binding_motif.md) | MHC anchor binding score | C | L2 UNIT; L3 ROUTE |
| [`min_max_scale`](min_max_scale.md) | Min-max scaling | A- | L2 ORACLE; L3 ROUTE |
| [`minibinder_interface`](minibinder_interface.md) | Minibinder interface residues | C | L2 UNIT; L3 ROUTE |
| [`mismatch_distribution`](mismatch_distribution.md) | Mismatch distribution | B | L2 UNIT; L3 EXECUTED |
| [`missing`](missing.md) | 缺失值过滤 | C | L2 UNIT; L3 ROUTE |
| [`ml_feature_ablation`](ml_feature_ablation.md) | ml_feature_ablation | C | L2 UNIT; L3 ROUTE |
| [`ml_grid_search`](ml_grid_search.md) | ml_grid_search | C | L2 UNIT; L3 ROUTE |
| [`ml_learning_curve`](ml_learning_curve.md) | ml_learning_curve | C | L2 UNIT; L3 ROUTE |
| [`ml_logistic_fit`](ml_logistic_fit.md) | ml_logistic_fit | C | L2 UNIT; L3 ROUTE |
| [`ml_partial_dependence`](ml_partial_dependence.md) | Partial dependence curve | B | L2 UNIT; L3 EXECUTED |
| [`ml_stratified_folds`](ml_stratified_folds.md) | ml_stratified_folds | C | L2 UNIT; L3 ROUTE |
| [`ml_train_test_split`](ml_train_test_split.md) | ml_train_test_split | C | L2 UNIT; L3 ROUTE |
| [`mlp_classifier`](mlp_classifier.md) | Train a small MLP classifier | B | L2 UNIT; L3 EXECUTED |
| [`mlp_regressor`](mlp_regressor.md) | Train a small MLP regressor | B | L2 UNIT; L3 EXECUTED |
| [`mlst_typing`](mlst_typing.md) | MLST sequence type assignment | B | L2 UNIT; L3 EXECUTED |
| [`module_eigengenes`](module_eigengenes.md) | Module eigengenes | C | L2 UNIT; L3 ROUTE |
| [`module_trait_correlation`](module_trait_correlation.md) | Module-trait correlations | C | L2 UNIT; L3 ROUTE |
| [`mood_median`](mood_median.md) | Mood two-sample scale test | C | L2 UNIT; L3 ROUTE |
| [`mood_median_test`](mood_median_test.md) | Mood's median test | C | L2 UNIT; L3 ROUTE |
| [`mood_scale`](mood_scale.md) | Mood two-sample scale test | B | L2 UNIT; L3 EXECUTED |
| [`moran`](moran.md) | Moran's I | B | L2 UNIT; L3 EXECUTED |
| [`morisita`](morisita.md) | Morisita dispersal index | C | L2 UNIT; L3 ROUTE |
| [`moses_test`](moses_test.md) | Moses extreme reactions test | B | L2 UNIT; L3 EXECUTED |
| [`motif_discovery_em`](motif_discovery_em.md) | Motif discovery by EM | C | L2 UNIT; L3 ROUTE |
| [`motif_enrichment`](motif_enrichment.md) | Motif enrichment | C | L2 UNIT; L3 ROUTE |
| [`motif_scan`](motif_scan.md) | motif_scan | E | L2 SKIP; L3 ROUTE |
| [`motif_scan_pwm`](motif_scan_pwm.md) | Scan sequences with a position weight matrix | C | L2 UNIT; L3 ROUTE |
| [`mrpp`](mrpp.md) | MRPP | B | L2 UNIT; L3 EXECUTED |
| [`ms1_feature_detect`](ms1_feature_detect.md) | MS1 feature detection | C | L2 UNIT; L3 ROUTE |
| [`ms1_isotope_pattern`](ms1_isotope_pattern.md) | MS1 isotope pattern | C | L2 UNIT; L3 ROUTE |
| [`ms2_cosine_similarity`](ms2_cosine_similarity.md) | MS2 cosine similarity against a library spectrum | C | L2 UNIT; L3 ROUTE |
| [`ms2_spectral_angle`](ms2_spectral_angle.md) | MS2 spectral angle | C | L2 UNIT; L3 ROUTE |
| [`ms_missing_filter`](ms_missing_filter.md) | Filter proteins by missing-value fraction | C | L2 UNIT; L3 ROUTE |
| [`msa_column_stats`](msa_column_stats.md) | Alignment column statistics | C | L2 UNIT; L3 ROUTE |
| [`msa_consensus`](msa_consensus.md) | Alignment consensus sequence | C | L2 UNIT; L3 ROUTE |
| [`msa_identity_matrix`](msa_identity_matrix.md) | Alignment identity matrix | C | L2 UNIT; L3 ROUTE |
| [`msa_trim`](msa_trim.md) | Trim alignment columns and rows | C | L2 UNIT; L3 ROUTE |
| [`multinomial_logit`](multinomial_logit.md) | Multinomial logistic regression | C | L2 UNIT; L3 ROUTE |
| [`multinomial_nb_classifier`](multinomial_nb_classifier.md) | Multinomial Naive Bayes classifier | C | L2 UNIT; L3 ROUTE |
| [`mutational_signature_decomposition`](mutational_signature_decomposition.md) | Mutational signature decomposition | C | L2 UNIT; L3 ROUTE |
| [`mutual_information`](mutual_information.md) | Mutual information | C | L2 UNIT; L3 ROUTE |
| [`negative_binomial_regression`](negative_binomial_regression.md) | Negative-binomial regression | C | L2 UNIT; L3 ROUTE |
| [`neighbor_joining`](neighbor_joining.md) | Neighbor joining tree | B | L2 UNIT; L3 EXECUTED |
| [`nelson_aalen`](nelson_aalen.md) | Nelson-Aalen cumulative hazard | C | L2 UNIT; L3 ROUTE |
| [`nemenyi_test`](nemenyi_test.md) | Nemenyi post-hoc test | B | L2 UNIT; L3 EXECUTED |
| [`nestedness`](nestedness.md) | NODF nestedness | C | L2 UNIT; L3 ROUTE |
| [`net_reclassification_improvement`](net_reclassification_improvement.md) | Continuous net reclassification improvement | C | L2 UNIT; L3 ROUTE |
| [`network_centrality`](network_centrality.md) | Network centrality | C | L2 UNIT; L3 ROUTE |
| [`network_communities`](network_communities.md) | Network communities | C | L2 UNIT; L3 ROUTE |
| [`network_summary`](network_summary.md) | Network topology summary | C | L2 UNIT; L3 ROUTE |
| [`nmds`](nmds.md) | Non-metric multidimensional scaling | B | L2 UNIT; L3 EXECUTED |
| [`nmf`](nmf.md) | NMF | C | L2 UNIT; L3 ROUTE |
| [`normalize`](normalize.md) | 归一化 | C | L2 UNIT; L3 ROUTE |
| [`normalized_mutual_info`](normalized_mutual_info.md) | Normalized mutual information | C | L2 UNIT; L3 ROUTE |
| [`normalizing_flow_density`](normalizing_flow_density.md) | RealNVP normalizing flow density | B | L2 UNIT; L3 EXECUTED |
| [`normaltest`](normaltest.md) | D'Agostino-Pearson normality test | C | L2 UNIT; L3 ROUTE |
| [`nucleosome_positioning`](nucleosome_positioning.md) | Nucleosome positioning periodicity | C | L2 UNIT; L3 ROUTE |
| [`nucleotide_diversity`](nucleotide_diversity.md) | Nucleotide diversity | B | L2 UNIT; L3 EXECUTED |
| [`nucleotide_transformer_embedding`](nucleotide_transformer_embedding.md) | Nucleotide Transformer embeddings | B | L2 UNIT; L3 EXECUTED_SRV |
| [`nucleotide_transformer_variant_effect`](nucleotide_transformer_variant_effect.md) | Nucleotide Transformer variant effect | B | L2 UNIT; L3 EXECUTED_SRV |
| [`odds_ratio`](odds_ratio.md) | Odds ratio | C | L2 UNIT; L3 ROUTE |
| [`openfold_predict`](openfold_predict.md) | OpenFold 结构预测 | D | L2 UNIT; L3 SKIP |
| [`optics`](optics.md) | OPTICS clustering | C | L2 UNIT; L3 ROUTE |
| [`ora`](ora.md) | Gene-set ORA | B | L2 UNIT; L3 EXECUTED |
| [`order_axis`](order_axis.md) | order_axis | B | L2 UNIT; L3 EXECUTED |
| [`ordinal_logistic`](ordinal_logistic.md) | Ordinal logistic regression | C | L2 UNIT; L3 ROUTE |
| [`ortholog_cluster`](ortholog_cluster.md) | Ortholog clustering by presence-pattern similarity | C | L2 UNIT; L3 ROUTE |
| [`pacf`](pacf.md) | Partial autocorrelation function | C | L2 UNIT; L3 ROUTE |
| [`paga_connectivity`](paga_connectivity.md) | paga_connectivity | C | L2 UNIT; L3 ROUTE |
| [`page_test`](page_test.md) | Page test for ordered alternatives | B | L2 UNIT; L3 EXECUTED |
| [`pains_filter`](pains_filter.md) | PAINS alert filter | C | L2 UNIT; L3 ROUTE |
| [`pair_confusion_matrix`](pair_confusion_matrix.md) | Pair confusion matrix | C | L2 UNIT; L3 ROUTE |
| [`pairwise_alignment`](pairwise_alignment.md) | Pairwise alignment | B | L2 UNIT; L3 EXECUTED |
| [`pam`](pam.md) | Partitioning around medoids | B | L2 UNIT; L3 EXECUTED |
| [`pangenome_curve`](pangenome_curve.md) | Pangenome accumulation curve | C | L2 UNIT; L3 ROUTE |
| [`pangenome_matrix`](pangenome_matrix.md) | Pangenome core and accessory summary | C | L2 UNIT; L3 ROUTE |
| [`partial_correlation`](partial_correlation.md) | Partial correlation | B | L2 UNIT; L3 EXECUTED |
| [`partial_mantel`](partial_mantel.md) | Partial Mantel test | B | L2 UNIT; L3 EXECUTED |
| [`particle_filter_bootstrap`](particle_filter_bootstrap.md) | Bootstrap particle filter | C | L2 UNIT; L3 ROUTE |
| [`passing_bablok`](passing_bablok.md) | Passing-Bablok regression | C | L2 UNIT; L3 ROUTE |
| [`patristic_distance`](patristic_distance.md) | Patristic distance | B | L2 UNIT; L3 EXECUTED |
| [`patterson_fst`](patterson_fst.md) | Patterson's Fst | B | L2 UNIT; L3 EXECUTED |
| [`pca`](pca.md) | PCA | A- | L2 ORACLE; L3 ROUTE |
| [`pca_loadings`](pca_loadings.md) | PCA loadings | C | L2 UNIT; L3 ROUTE |
| [`pcnm`](pcnm.md) | Principal coordinates of neighbourhood matrices | B | L2 UNIT; L3 EXECUTED |
| [`pcoa`](pcoa.md) | Principal coordinates analysis | B | L2 UNIT; L3 EXECUTED |
| [`peak_annotate`](peak_annotate.md) | Annotate peaks with the nearest same-chromosome gene | C | L2 UNIT; L3 ROUTE |
| [`peak_chrom_summary`](peak_chrom_summary.md) | Peak chromosome concentration | C | L2 UNIT; L3 ROUTE |
| [`peak_density_profile`](peak_density_profile.md) | Peak density in fixed windows | C | L2 UNIT; L3 ROUTE |
| [`peak_gap_stats`](peak_gap_stats.md) | Inter-peak gap statistics | C | L2 UNIT; L3 ROUTE |
| [`peak_merge`](peak_merge.md) | peak_merge | C | L2 UNIT; L3 ROUTE |
| [`peak_nearest_gene`](peak_nearest_gene.md) | peak_nearest_gene | E | L2 SKIP; L3 ROUTE |
| [`peak_overlap_count`](peak_overlap_count.md) | Count peaks overlapping genes | C | L2 UNIT; L3 ROUTE |
| [`peak_overlap_matrix`](peak_overlap_matrix.md) | Pairwise peak overlap matrix | C | L2 UNIT; L3 ROUTE |
| [`peak_peak_distance`](peak_peak_distance.md) | Nearest peak distance | C | L2 UNIT; L3 ROUTE |
| [`peak_signal_stats`](peak_signal_stats.md) | Peak signal and confidence summary | C | L2 UNIT; L3 ROUTE |
| [`peak_strand_bias`](peak_strand_bias.md) | Peak strand balance | C | L2 UNIT; L3 ROUTE |
| [`peak_summit_offset`](peak_summit_offset.md) | Peak summit offset | C | L2 UNIT; L3 ROUTE |
| [`peak_tss_distance`](peak_tss_distance.md) | Distance from peaks to nearest TSS | C | L2 UNIT; L3 ROUTE |
| [`peak_tss_enrichment`](peak_tss_enrichment.md) | Distance-to-TSS bin enrichment | C | L2 UNIT; L3 ROUTE |
| [`peak_width_signal_correlation`](peak_width_signal_correlation.md) | Peak width versus signal | C | L2 UNIT; L3 ROUTE |
| [`peak_width_stats`](peak_width_stats.md) | Peak width distribution | C | L2 UNIT; L3 ROUTE |
| [`pearson_test`](pearson_test.md) | Pearson chi-square normality test | C | L2 UNIT; L3 ROUTE |
| [`pedigree_inbreeding`](pedigree_inbreeding.md) | Inbreeding coefficients from a numeric pedigree | B | L2 UNIT; L3 EXECUTED |
| [`peptide_coverage`](peptide_coverage.md) | Peptide coverage | C | L2 UNIT; L3 ROUTE |
| [`peptide_fragment_ions`](peptide_fragment_ions.md) | Peptide fragment ions | C | L2 UNIT; L3 ROUTE |
| [`peptide_isotope_envelope`](peptide_isotope_envelope.md) | Peptide isotope envelope | C | L2 UNIT; L3 ROUTE |
| [`peptide_mass`](peptide_mass.md) | Peptide mass and m/z | C | L2 UNIT; L3 ROUTE |
| [`peptide_modified_mass`](peptide_modified_mass.md) | Modified peptide mass | C | L2 UNIT; L3 ROUTE |
| [`peptide_qvalue`](peptide_qvalue.md) | Peptide q-values | C | L2 UNIT; L3 ROUTE |
| [`peptide_spectrum_annotation`](peptide_spectrum_annotation.md) | Peptide spectrum annotation | C | L2 UNIT; L3 ROUTE |
| [`periodogram`](periodogram.md) | Periodogram | C | L2 UNIT; L3 ROUTE |
| [`permanova`](permanova.md) | PERMANOVA | C | L2 UNIT; L3 ROUTE |
| [`permutation_test`](permutation_test.md) | Permutation test | B | L2 UNIT; L3 EXECUTED |
| [`pettitt_test`](pettitt_test.md) | Pettitt change-point test | C | L2 UNIT; L3 ROUTE |
| [`pfam_architecture`](pfam_architecture.md) | Pfam architecture | C | L2 UNIT; L3 ROUTE |
| [`phillips_perron`](phillips_perron.md) | Phillips-Perron unit-root test | C | L2 UNIT; L3 ROUTE |
| [`phylo_ancestral`](phylo_ancestral.md) | phylo_ancestral | C | L2 UNIT; L3 ROUTE |
| [`phylo_bootstrap`](phylo_bootstrap.md) | phylo_bootstrap | C | L2 UNIT; L3 ROUTE |
| [`phylo_contrasts`](phylo_contrasts.md) | phylo_contrasts | C | L2 UNIT; L3 ROUTE |
| [`phylo_distance_matrix`](phylo_distance_matrix.md) | Phylogenetic distance matrix | C | L2 UNIT; L3 ROUTE |
| [`phylo_lambda`](phylo_lambda.md) | phylo_lambda | C | L2 UNIT; L3 ROUTE |
| [`phylo_neighbor_joining`](phylo_neighbor_joining.md) | Neighbour-joining tree | C | L2 UNIT; L3 ROUTE |
| [`phylo_support_filter`](phylo_support_filter.md) | phylo_support_filter | C | L2 UNIT; L3 ROUTE |
| [`phylo_support_summary`](phylo_support_summary.md) | phylo_support_summary | C | L2 UNIT; L3 ROUTE |
| [`phylo_tree_distance`](phylo_tree_distance.md) | Tree topology distance | C | L2 UNIT; L3 ROUTE |
| [`phylogenetics_gtr_likelihood`](phylogenetics_gtr_likelihood.md) | GTR tree likelihood | B | L2 UNIT; L3 EXECUTED |
| [`phylogenetics_jc69_likelihood`](phylogenetics_jc69_likelihood.md) | JC69 tree likelihood | C | L2 UNIT; L3 ROUTE |
| [`pileup_variants`](pileup_variants.md) | pileup_variants | C | L2 UNIT; L3 ROUTE |
| [`pivot`](pivot.md) | pivot | C | L2 UNIT; L3 ROUTE |
| [`plasmid_contig_filter`](plasmid_contig_filter.md) | Plasmid-like contig filter | C | L2 UNIT; L3 ROUTE |
| [`pls_regression`](pls_regression.md) | PLS regression | C | L2 UNIT; L3 ROUTE |
| [`poisson_means_test`](poisson_means_test.md) | Exact two-sample Poisson rate test | B | L2 UNIT; L3 EXECUTED |
| [`poisson_regression`](poisson_regression.md) | Poisson regression | C | L2 UNIT; L3 ROUTE |
| [`poisson_test`](poisson_test.md) | Exact Poisson rate test | C | L2 UNIT; L3 ROUTE |
| [`power_anova`](power_anova.md) | ANOVA power | C | L2 UNIT; L3 ROUTE |
| [`power_prop_test`](power_prop_test.md) | Two-proportion power | B | L2 UNIT; L3 EXECUTED |
| [`power_t_test`](power_t_test.md) | t-test power | C | L2 UNIT; L3 ROUTE |
| [`power_transform`](power_transform.md) | Power transform | C | L2 UNIT; L3 ROUTE |
| [`precision_recall_curve`](precision_recall_curve.md) | Precision-recall curve | B | L2 UNIT; L3 EXECUTED |
| [`press`](press.md) | Prediction error sum of squares | B | L2 UNIT; L3 EXECUTED |
| [`primer_design`](primer_design.md) | Primer pair design | C | L2 UNIT; L3 ROUTE |
| [`primer_specificity`](primer_specificity.md) | Primer specificity (in-silico PCR) | C | L2 UNIT; L3 ROUTE |
| [`primer_tm`](primer_tm.md) | Primer melting temperature | C | L2 UNIT; L3 ROUTE |
| [`prioritize`](prioritize.md) | prioritize | B | L2 UNIT; L3 EXECUTED |
| [`probit_regression`](probit_regression.md) | Probit regression | C | L2 UNIT; L3 ROUTE |
| [`procrustes`](procrustes.md) | Procrustes analysis | C | L2 UNIT; L3 ROUTE |
| [`prodigal_genes`](prodigal_genes.md) | Prodigal gene prediction | B | L2 UNIT; L3 EXECUTED |
| [`propensity_score`](propensity_score.md) | propensity_score | C | L2 UNIT; L3 ROUTE |
| [`propensity_score_matching`](propensity_score_matching.md) | Propensity-score ATT matching | C | L2 UNIT; L3 ROUTE |
| [`proportion_ci`](proportion_ci.md) | Binomial proportion confidence interval | C | L2 UNIT; L3 ROUTE |
| [`prosite_scan`](prosite_scan.md) | Motif scan | C | L2 UNIT; L3 ROUTE |
| [`protein_aliphatic_index`](protein_aliphatic_index.md) | Protein aliphatic index | C | L2 UNIT; L3 ROUTE |
| [`protein_charge_curve`](protein_charge_curve.md) | Protein charge versus pH | C | L2 UNIT; L3 ROUTE |
| [`protein_composition`](protein_composition.md) | Protein amino-acid composition | C | L2 UNIT; L3 ROUTE |
| [`protein_digest`](protein_digest.md) | Protein digest | C | L2 UNIT; L3 ROUTE |
| [`protein_er_retention`](protein_er_retention.md) | Protein ER retention motif | C | L2 UNIT; L3 ROUTE |
| [`protein_extinction`](protein_extinction.md) | Protein A280 extinction coefficients | C | L2 UNIT; L3 ROUTE |
| [`protein_gravy_window`](protein_gravy_window.md) | Protein GRAVY sliding window | C | L2 UNIT; L3 ROUTE |
| [`protein_inference`](protein_inference.md) | Protein inference | C | L2 UNIT; L3 ROUTE |
| [`protein_instability`](protein_instability.md) | Protein instability index | C | L2 UNIT; L3 ROUTE |
| [`protein_kinase_motifs`](protein_kinase_motifs.md) | Protein kinase motifs | C | L2 UNIT; L3 ROUTE |
| [`protein_mitochondrial_targeting`](protein_mitochondrial_targeting.md) | Protein mitochondrial presequence score | C | L2 UNIT; L3 ROUTE |
| [`protein_nglyc_sequons`](protein_nglyc_sequons.md) | Protein N-glycosylation sequons | C | L2 UNIT; L3 ROUTE |
| [`protein_nls_motifs`](protein_nls_motifs.md) | Protein NLS motifs | C | L2 UNIT; L3 ROUTE |
| [`protein_nuclear_export_signal`](protein_nuclear_export_signal.md) | Protein nuclear export signal | C | L2 UNIT; L3 ROUTE |
| [`protein_properties`](protein_properties.md) | Protein properties | B | L2 UNIT; L3 EXECUTED_SRV |
| [`protein_pts1_signal`](protein_pts1_signal.md) | Protein PTS1 signal | C | L2 UNIT; L3 ROUTE |
| [`protein_rollup`](protein_rollup.md) | Peptide to protein rollup | C | L2 UNIT; L3 ROUTE |
| [`proteinmpnn_bias_matrix`](proteinmpnn_bias_matrix.md) | ProteinMPNN bias matrix | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_bias_scan`](proteinmpnn_bias_scan.md) | ProteinMPNN Bias Scan | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_design`](proteinmpnn_design.md) | ProteinMPNN design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_design_cluster`](proteinmpnn_design_cluster.md) | Cluster ProteinMPNN designs | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_design_diversity`](proteinmpnn_design_diversity.md) | ProteinMPNN design diversity | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_design_profile`](proteinmpnn_design_profile.md) | ProteinMPNN design profile | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_ensemble_score`](proteinmpnn_ensemble_score.md) | ProteinMPNN ensemble score | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_hotspot_masked_design`](proteinmpnn_hotspot_masked_design.md) | Hotspot-masked design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_interface_design`](proteinmpnn_interface_design.md) | ProteinMPNN interface design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_interface_redesign`](proteinmpnn_interface_redesign.md) | Interface Redesign | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_interface_scan`](proteinmpnn_interface_scan.md) | ProteinMPNN interface scan | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_interface_temperature_scan`](proteinmpnn_interface_temperature_scan.md) | Interface temperature scan | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_masked_design`](proteinmpnn_masked_design.md) | Masked ProteinMPNN design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_masked_interface_design`](proteinmpnn_masked_interface_design.md) | Interface-masked ProteinMPNN design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_masked_interface_score`](proteinmpnn_masked_interface_score.md) | ProteinMPNN interface score | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_multi_model_consensus`](proteinmpnn_multi_model_consensus.md) | ProteinMPNN 多模型共识 | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_native_recovery_scan`](proteinmpnn_native_recovery_scan.md) | ProteinMPNN Native Recovery Scan | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_noise_robustness`](proteinmpnn_noise_robustness.md) | ProteinMPNN noise robustness | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_omit_design`](proteinmpnn_omit_design.md) | ProteinMPNN constrained design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_perplexity`](proteinmpnn_perplexity.md) | ProteinMPNN Perplexity | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_position_entropy`](proteinmpnn_position_entropy.md) | ProteinMPNN position entropy | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_probability_profile`](proteinmpnn_probability_profile.md) | ProteinMPNN probability profile | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_score`](proteinmpnn_score.md) | ProteinMPNN sequence score | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_temperature_ladder`](proteinmpnn_temperature_ladder.md) | ProteinMPNN 温度梯度 | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteinmpnn_tied_design`](proteinmpnn_tied_design.md) | ProteinMPNN tied-position design | B | L2 UNIT; L3 EXECUTED_SRV |
| [`proteomics_ibaq`](proteomics_ibaq.md) | iBAQ protein abundance | C | L2 UNIT; L3 ROUTE |
| [`prs`](prs.md) | Polygenic risk score | C | L2 UNIT; L3 ROUTE |
| [`prs_af_filter`](prs_af_filter.md) | prs_af_filter | C | L2 UNIT; L3 ROUTE |
| [`prs_harmonize`](prs_harmonize.md) | prs_harmonize | C | L2 UNIT; L3 ROUTE |
| [`prs_ld_clump`](prs_ld_clump.md) | prs_ld_clump | C | L2 UNIT; L3 ROUTE |
| [`pseudobulk`](pseudobulk.md) | Pseudobulk aggregation | C | L2 UNIT; L3 ROUTE |
| [`pseudotime_dpt`](pseudotime_dpt.md) | pseudotime_dpt | C | L2 UNIT; L3 ROUTE |
| [`psm_balance`](psm_balance.md) | psm_balance | C | L2 UNIT; L3 ROUTE |
| [`psm_effect`](psm_effect.md) | psm_effect | C | L2 UNIT; L3 ROUTE |
| [`psm_match`](psm_match.md) | psm_match | C | L2 UNIT; L3 ROUTE |
| [`ptm_localization_score`](ptm_localization_score.md) | Phospho-site localization probability from delta scores | C | L2 UNIT; L3 ROUTE |
| [`ptm_occupancy`](ptm_occupancy.md) | PTM site occupancy | C | L2 UNIT; L3 ROUTE |
| [`pwm_from_counts`](pwm_from_counts.md) | pwm_from_counts | C | L2 UNIT; L3 ROUTE |
| [`pwm_information`](pwm_information.md) | pwm_information | C | L2 UNIT; L3 ROUTE |
| [`pwm_scan`](pwm_scan.md) | pwm_scan | C | L2 UNIT; L3 ROUTE |
| [`qc_metrics`](qc_metrics.md) | qc_metrics | C | L2 UNIT; L3 ROUTE |
| [`qda`](qda.md) | Quadratic discriminant analysis | C | L2 UNIT; L3 ROUTE |
| [`qtl_interval_mapping`](qtl_interval_mapping.md) | QTL interval mapping | B | L2 UNIT; L3 EXECUTED |
| [`quade_test`](quade_test.md) | Quade test | C | L2 UNIT; L3 ROUTE |
| [`quantile_regression`](quantile_regression.md) | Quantile regression | C | L2 UNIT; L3 ROUTE |
| [`quantile_transform`](quantile_transform.md) | Quantile transform | C | L2 UNIT; L3 ROUTE |
| [`rainbow_test`](rainbow_test.md) | Rainbow test | B | L2 UNIT; L3 EXECUTED |
| [`random_forest_classifier`](random_forest_classifier.md) | Random Forest classifier | E | L2 SKIP; L3 ROUTE |
| [`random_forest_regressor`](random_forest_regressor.md) | Random Forest regressor | D | L2 SMOKE; L3 ROUTE |
| [`rank_axis`](rank_axis.md) | Rank features | C | L2 UNIT; L3 ROUTE |
| [`rank_biserial`](rank_biserial.md) | Rank-biserial correlation | C | L2 UNIT; L3 ROUTE |
| [`rank_test`](rank_test.md) | Mann-Kendall rank test | C | L2 UNIT; L3 ROUTE |
| [`rank_transform`](rank_transform.md) | Rank transform | C | L2 UNIT; L3 ROUTE |
| [`rarefaction`](rarefaction.md) | Individual-based rarefaction | B | L2 UNIT; L3 EXECUTED |
| [`rda`](rda.md) | Redundancy analysis | C | L2 UNIT; L3 ROUTE |
| [`rdd`](rdd.md) | Regression discontinuity | C | L2 UNIT; L3 ROUTE |
| [`rdkit_admet_rules`](rdkit_admet_rules.md) | RDKit drug-likeness rules | C | L2 UNIT; L3 ROUTE |
| [`rdkit_atom_environment_histogram`](rdkit_atom_environment_histogram.md) | Atom environment histogram | C | L2 UNIT; L3 ROUTE |
| [`rdkit_charge_profile`](rdkit_charge_profile.md) | RDKit charge profile | C | L2 UNIT; L3 ROUTE |
| [`rdkit_conformer_cluster`](rdkit_conformer_cluster.md) | Conformer clustering | C | L2 UNIT; L3 ROUTE |
| [`rdkit_conformer_energy`](rdkit_conformer_energy.md) | RDKit conformer energies | C | L2 UNIT; L3 ROUTE |
| [`rdkit_descriptors`](rdkit_descriptors.md) | RDKit molecular descriptors | C | L2 UNIT; L3 ROUTE |
| [`rdkit_esol`](rdkit_esol.md) | RDKit ESOL Solubility | C | L2 UNIT; L3 ROUTE |
| [`rdkit_fragment_overlap`](rdkit_fragment_overlap.md) | RDKit fragment overlap | B | L2 UNIT; L3 EXECUTED |
| [`rdkit_fragment_profile`](rdkit_fragment_profile.md) | Fragment profile | C | L2 UNIT; L3 ROUTE |
| [`rdkit_functional_group_counts`](rdkit_functional_group_counts.md) | Functional group counts | C | L2 UNIT; L3 ROUTE |
| [`rdkit_mcs`](rdkit_mcs.md) | Maximum common substructure | C | L2 UNIT; L3 ROUTE |
| [`rdkit_mcs_cluster`](rdkit_mcs_cluster.md) | RDKit MCS cluster | C | L2 UNIT; L3 ROUTE |
| [`rdkit_morgan_fingerprint`](rdkit_morgan_fingerprint.md) | Morgan fingerprint | C | L2 UNIT; L3 ROUTE |
| [`rdkit_murcko_fingerprint`](rdkit_murcko_fingerprint.md) | Murcko scaffold fingerprint | C | L2 UNIT; L3 ROUTE |
| [`rdkit_oral_bioavailability`](rdkit_oral_bioavailability.md) | RDKit Oral Bioavailability Rules | C | L2 UNIT; L3 ROUTE |
| [`rdkit_pharmacophore_features`](rdkit_pharmacophore_features.md) | Pharmacophore Features | C | L2 UNIT; L3 ROUTE |
| [`rdkit_qed`](rdkit_qed.md) | RDKit QED | C | L2 UNIT; L3 ROUTE |
| [`rdkit_reaction_pairwise_enumerate`](rdkit_reaction_pairwise_enumerate.md) | Pairwise reaction enumeration | B | L2 UNIT; L3 EXECUTED |
| [`rdkit_reaction_smarts_apply`](rdkit_reaction_smarts_apply.md) | Reaction SMARTS application | C | L2 UNIT; L3 ROUTE |
| [`rdkit_ring_systems`](rdkit_ring_systems.md) | RDKit ring systems | C | L2 UNIT; L3 ROUTE |
| [`rdkit_sa_score`](rdkit_sa_score.md) | RDKit Synthetic Accessibility | C | L2 UNIT; L3 ROUTE |
| [`rdkit_scaffold`](rdkit_scaffold.md) | RDKit Bemis-Murcko scaffolds | C | L2 UNIT; L3 ROUTE |
| [`rdkit_scaffold_diversity`](rdkit_scaffold_diversity.md) | RDKit Scaffold Diversity | C | L2 UNIT; L3 ROUTE |
| [`rdkit_scaffold_tree`](rdkit_scaffold_tree.md) | Murcko scaffold tree | C | L2 UNIT; L3 ROUTE |
| [`rdkit_similarity`](rdkit_similarity.md) | Molecular similarity matrix | C | L2 UNIT; L3 ROUTE |
| [`rdkit_smarts_matches`](rdkit_smarts_matches.md) | RDKit SMARTS Matches | C | L2 UNIT; L3 ROUTE |
| [`rdkit_smiles_augment`](rdkit_smiles_augment.md) | RDKit SMILES Augment | C | L2 UNIT; L3 ROUTE |
| [`rdkit_tautomer`](rdkit_tautomer.md) | Tautomer canonicalization | C | L2 UNIT; L3 ROUTE |
| [`recombination_rate`](recombination_rate.md) | Recombination rate from a genetic map | C | L2 UNIT; L3 ROUTE |
| [`reduce`](reduce.md) | PCA / PCoA / UMAP / t-SNE | C | L2 UNIT; L3 ROUTE |
| [`reduce_axis`](reduce_axis.md) | Axis statistics | B | L2 UNIT; L3 EXECUTED |
| [`redundancy_analysis`](redundancy_analysis.md) | Redundancy analysis | B | L2 UNIT; L3 EXECUTED |
| [`regress`](regress.md) | 回归分析 | C | L2 UNIT; L3 ROUTE |
| [`regression_discontinuity`](regression_discontinuity.md) | Sharp regression discontinuity | C | L2 UNIT; L3 ROUTE |
| [`relatedness`](relatedness.md) | Relatedness | C | L2 UNIT; L3 ROUTE |
| [`remove_batch_effect`](remove_batch_effect.md) | Remove batch effect | B | L2 UNIT; L3 EXECUTED |
| [`rename_dim`](rename_dim.md) | 重命名维度 | C | L2 UNIT; L3 ROUTE |
| [`renyi`](renyi.md) | Renyi diversity profiles | B | L2 UNIT; L3 EXECUTED |
| [`reset_test`](reset_test.md) | RESET functional-form test | C | L2 UNIT; L3 ROUTE |
| [`resource_preflight`](resource_preflight.md) | Large-resource preflight | C | L2 UNIT; L3 ROUTE |
| [`restriction_digest`](restriction_digest.md) | restriction_digest | C | L2 UNIT; L3 ROUTE |
| [`restriction_fragment_stats`](restriction_fragment_stats.md) | restriction_fragment_stats | C | L2 UNIT; L3 ROUTE |
| [`restriction_sites`](restriction_sites.md) | Restriction sites | C | L2 UNIT; L3 ROUTE |
| [`reverse_complement`](reverse_complement.md) | Reverse complement | C | L2 UNIT; L3 ROUTE |
| [`rfam_scan`](rfam_scan.md) | Rfam ncRNA family scan | B | L2 UNIT; L3 EXECUTED |
| [`rfdiffusion_design`](rfdiffusion_design.md) | RFdiffusion backbone design | D | L2 UNIT; L3 SKIP |
| [`ridge_regression`](ridge_regression.md) | Ridge regression | D | L2 SMOKE; L3 ROUTE |
| [`risk_ratio`](risk_ratio.md) | Risk ratio | C | L2 UNIT; L3 ROUTE |
| [`rmst`](rmst.md) | Restricted mean survival | C | L2 UNIT; L3 ROUTE |
| [`rna_editing_detect`](rna_editing_detect.md) | RNA editing candidate detection | C | L2 UNIT; L3 ROUTE |
| [`rna_structure_consensus`](rna_structure_consensus.md) | RNA 结构共识 (RNAsubopt 集合) | C | L2 UNIT; L3 ROUTE |
| [`rna_structure_distance`](rna_structure_distance.md) | RNA 二级结构距离 (RNAfold 双温度) | C | L2 UNIT; L3 ROUTE |
| [`rna_structure_features`](rna_structure_features.md) | RNA 二级结构特征 (环与茎) | C | L2 UNIT; L3 ROUTE |
| [`robinson_foulds`](robinson_foulds.md) | Robinson-Foulds distance | B | L2 UNIT; L3 EXECUTED |
| [`robust_regression`](robust_regression.md) | Robust linear regression | C | L2 UNIT; L3 ROUTE |
| [`robust_scale`](robust_scale.md) | Robust scaling | C | L2 UNIT; L3 ROUTE |
| [`roc_comparison`](roc_comparison.md) | Paired ROC comparison | B | L2 UNIT; L3 EXECUTED |
| [`roc_curve`](roc_curve.md) | ROC curve | B | L2 UNIT; L3 EXECUTED |
| [`roh_detect`](roh_detect.md) | Runs of homozygosity per sample | C | L2 UNIT; L3 ROUTE |
| [`rscu_table`](rscu_table.md) | Relative synonymous codon usage | C | L2 UNIT; L3 ROUTE |
| [`rt_alignment`](rt_alignment.md) | Align retention times between runs | C | L2 UNIT; L3 ROUTE |
| [`runs_test`](runs_test.md) | Runs test | C | L2 UNIT; L3 ROUTE |
| [`sarima`](sarima.md) | Seasonal ARIMA model | C | L2 UNIT; L3 ROUTE |
| [`sarimax_forecast`](sarimax_forecast.md) | SARIMAX time-series forecast | C | L2 UNIT; L3 ROUTE |
| [`sasa_per_residue`](sasa_per_residue.md) | Per-Residue SASA | C | L2 UNIT; L3 ROUTE |
| [`sc_batch_ilisi`](sc_batch_ilisi.md) | Single-cell iLISI batch mixing | C | L2 UNIT; L3 ROUTE |
| [`sc_batch_kbet`](sc_batch_kbet.md) | Single-cell kBET batch mixing | B | L2 UNIT; L3 EXECUTED |
| [`sc_cluster_profile`](sc_cluster_profile.md) | sc_cluster_profile | C | L2 UNIT; L3 ROUTE |
| [`sc_cnv_score`](sc_cnv_score.md) | Per-cell CNV score | C | L2 UNIT; L3 ROUTE |
| [`sc_deconvolution`](sc_deconvolution.md) | NNLS cell-type deconvolution | C | L2 UNIT; L3 ROUTE |
| [`sc_knn_graph`](sc_knn_graph.md) | Single-cell kNN graph | C | L2 UNIT; L3 ROUTE |
| [`sc_leiden_cluster`](sc_leiden_cluster.md) | Leiden clustering | B | L2 UNIT; L3 EXECUTED |
| [`sc_marker_specificity`](sc_marker_specificity.md) | sc_marker_specificity | C | L2 UNIT; L3 ROUTE |
| [`sc_pseudobulk_de`](sc_pseudobulk_de.md) | Pseudo-bulk differential expression | B | L2 UNIT; L3 EXECUTED |
| [`sc_rank_genes`](sc_rank_genes.md) | sc_rank_genes | C | L2 UNIT; L3 ROUTE |
| [`sc_spatial_domains`](sc_spatial_domains.md) | Spatial domain assignment | C | L2 UNIT; L3 ROUTE |
| [`sc_spatial_neighbors`](sc_spatial_neighbors.md) | Spatial k-nearest-neighbour graph | C | L2 UNIT; L3 ROUTE |
| [`sc_spatial_variable_genes`](sc_spatial_variable_genes.md) | Spatially variable genes (Moran's I) | B | L2 UNIT; L3 EXECUTED |
| [`scale_features`](scale_features.md) | scale_features | C | L2 UNIT; L3 ROUTE |
| [`scatter`](scatter.md) | 散点图 | C | L2 UNIT; L3 ROUTE |
| [`scheffe_test`](scheffe_test.md) | Scheffe post-hoc test | C | L2 UNIT; L3 ROUTE |
| [`seasonal_decompose`](seasonal_decompose.md) | Classical seasonal decomposition | B | L2 UNIT; L3 EXECUTED |
| [`select`](select.md) | 选择特征 | C | L2 UNIT; L3 ROUTE |
| [`selection_index`](selection_index.md) | Composite selection score from Fst, iHS and XP-EHH | C | L2 UNIT; L3 ROUTE |
| [`sen_slope`](sen_slope.md) | Sen's slope | C | L2 UNIT; L3 ROUTE |
| [`sequence_aggregation_propensity`](sequence_aggregation_propensity.md) | Aggregation propensity | B | L2 UNIT; L3 EXECUTED |
| [`sequence_beta_propensity`](sequence_beta_propensity.md) | Beta-sheet propensity | B | L2 UNIT; L3 EXECUTED |
| [`sequence_cai`](sequence_cai.md) | Codon adaptation index | C | L2 UNIT; L3 ROUTE |
| [`sequence_codon_adaptation`](sequence_codon_adaptation.md) | Codon adaptation index | C | L2 UNIT; L3 ROUTE |
| [`sequence_complexity`](sequence_complexity.md) | Sequence Complexity | C | L2 UNIT; L3 ROUTE |
| [`sequence_cpg_island`](sequence_cpg_island.md) | CpG island scan | C | L2 UNIT; L3 ROUTE |
| [`sequence_cysteine_pairing`](sequence_cysteine_pairing.md) | Cysteine pairing | B | L2 UNIT; L3 EXECUTED |
| [`sequence_disorder_predictor`](sequence_disorder_predictor.md) | Sequence disorder predictor | B | L2 UNIT; L3 EXECUTED |
| [`sequence_dnds`](sequence_dnds.md) | dN/dS ratio (Nei-Gojobori) | B | L2 UNIT; L3 EXECUTED |
| [`sequence_g4_quadruplex_scan`](sequence_g4_quadruplex_scan.md) | G-quadruplex tract scan | C | L2 UNIT; L3 ROUTE |
| [`sequence_gc_profile`](sequence_gc_profile.md) | Sequence GC Profile | C | L2 UNIT; L3 ROUTE |
| [`sequence_gc_skew_profile`](sequence_gc_skew_profile.md) | GC skew profile | C | L2 UNIT; L3 ROUTE |
| [`sequence_hydrophobic_moment`](sequence_hydrophobic_moment.md) | Helical hydrophobic moment | B | L2 UNIT; L3 EXECUTED |
| [`sequence_hydrophobicity_profile`](sequence_hydrophobicity_profile.md) | Sequence hydrophobicity profile | C | L2 UNIT; L3 ROUTE |
| [`sequence_isoelectric_point`](sequence_isoelectric_point.md) | Isoelectric point | B | L2 UNIT; L3 EXECUTED |
| [`sequence_kmer_enrichment`](sequence_kmer_enrichment.md) | Sequence k-mer enrichment | C | L2 UNIT; L3 ROUTE |
| [`sequence_kmer_profile`](sequence_kmer_profile.md) | K-mer composition profile | C | L2 UNIT; L3 ROUTE |
| [`sequence_liability_scan`](sequence_liability_scan.md) | Sequence liability scan | C | L2 UNIT; L3 ROUTE |
| [`sequence_net_charge`](sequence_net_charge.md) | Protein net charge | B | L2 UNIT; L3 EXECUTED |
| [`sequence_orf_finder`](sequence_orf_finder.md) | Six-frame ORF finder | C | L2 UNIT; L3 ROUTE |
| [`sequence_repeat_finder`](sequence_repeat_finder.md) | Tandem repeat finder | B | L2 UNIT; L3 EXECUTED |
| [`sequence_restriction_sites`](sequence_restriction_sites.md) | Restriction site scan | C | L2 UNIT; L3 ROUTE |
| [`sequence_rna_accessibility`](sequence_rna_accessibility.md) | RNA 可及性 | B | L2 UNIT; L3 EXECUTED |
| [`sequence_rna_cofold`](sequence_rna_cofold.md) | RNA 二聚体共折叠平衡 | B | L2 UNIT; L3 EXECUTED |
| [`sequence_rna_cofold_ensemble`](sequence_rna_cofold_ensemble.md) | RNA 双链系综 | B | L2 UNIT; L3 EXECUTED |
| [`sequence_rna_duplex`](sequence_rna_duplex.md) | RNA-RNA 杂交位点 | B | L2 UNIT; L3 EXECUTED |
| [`sequence_rna_ensemble`](sequence_rna_ensemble.md) | RNA 系综统计 (RNAfold -p) | B | L2 UNIT; L3 EXECUTED |
| [`sequence_rna_fold`](sequence_rna_fold.md) | RNA 二级结构折叠 (ViennaRNA) | B | L2 UNIT; L3 EXECUTED |
| [`sequence_signal_peptide`](sequence_signal_peptide.md) | Signal peptide detection | C | L2 UNIT; L3 ROUTE |
| [`sequence_signal_peptide_v2`](sequence_signal_peptide_v2.md) | Signal peptide typing | C | L2 UNIT; L3 ROUTE |
| [`sequence_stats`](sequence_stats.md) | sequence_stats | C | L2 UNIT; L3 ROUTE |
| [`sequence_tm_segments`](sequence_tm_segments.md) | Transmembrane helix segments | B | L2 UNIT; L3 EXECUTED |
| [`sequence_transmembrane_topology`](sequence_transmembrane_topology.md) | Transmembrane topology | B | L2 UNIT; L3 EXECUTED |
| [`sgd_classifier`](sgd_classifier.md) | SGD classifier | C | L2 UNIT; L3 ROUTE |
| [`sgd_regressor`](sgd_regressor.md) | SGD regressor | C | L2 UNIT; L3 ROUTE |
| [`shapiro`](shapiro.md) | Shapiro-Wilk test | C | L2 UNIT; L3 ROUTE |
| [`shapiro_francia`](shapiro_francia.md) | Shapiro-Francia normality test | C | L2 UNIT; L3 ROUTE |
| [`shapiro_wilk`](shapiro_wilk.md) | Shapiro-Wilk normality test | C | L2 UNIT; L3 ROUTE |
| [`siegel_tukey`](siegel_tukey.md) | Siegel-Tukey rank dispersion test | B | L2 UNIT; L3 EXECUTED |
| [`sign_test`](sign_test.md) | Paired sign test | C | L2 UNIT; L3 ROUTE |
| [`silhouette`](silhouette.md) | Silhouette score | C | L2 UNIT; L3 ROUTE |
| [`silhouette_samples`](silhouette_samples.md) | Silhouette samples | C | L2 UNIT; L3 ROUTE |
| [`silhouette_score`](silhouette_score.md) | Silhouette score | C | L2 UNIT; L3 ROUTE |
| [`simper`](simper.md) | SIMPER | B | L2 UNIT; L3 EXECUTED |
| [`site_frequency_spectrum`](site_frequency_spectrum.md) | Site frequency spectrum | B | L2 UNIT; L3 EXECUTED |
| [`skillings_mack`](skillings_mack.md) | Skillings-Mack test | C | L2 UNIT; L3 ROUTE |
| [`smiles_standardize`](smiles_standardize.md) | Standardize SMILES | B | L2 UNIT; L3 EXECUTED |
| [`snk_test`](snk_test.md) | Student-Newman-Keuls test | B | L2 UNIT; L3 EXECUTED |
| [`softmax`](softmax.md) | Softmax | C | L2 UNIT; L3 ROUTE |
| [`somers_d`](somers_d.md) | Somers' D | C | L2 UNIT; L3 ROUTE |
| [`specaccum`](specaccum.md) | Species accumulation | C | L2 UNIT; L3 ROUTE |
| [`specpool`](specpool.md) | Species pool estimators | C | L2 UNIT; L3 ROUTE |
| [`spectral_embedding`](spectral_embedding.md) | Spectral embedding | C | L2 UNIT; L3 ROUTE |
| [`spectral_entropy`](spectral_entropy.md) | Spectral entropy and peak complexity | C | L2 UNIT; L3 ROUTE |
| [`spectrum_library_match`](spectrum_library_match.md) | Spectrum library match | C | L2 UNIT; L3 ROUTE |
| [`splicing_psi`](splicing_psi.md) | Splicing PSI | C | L2 UNIT; L3 ROUTE |
| [`spline_regression`](spline_regression.md) | B-spline regression | C | L2 UNIT; L3 ROUTE |
| [`ssgsea`](ssgsea.md) | ssGSEA | C | L2 UNIT; L3 ROUTE |
| [`standardized_residuals`](standardized_residuals.md) | Standardized residuals | B | L2 UNIT; L3 EXECUTED |
| [`stats_fdr`](stats_fdr.md) | stats_fdr | C | L2 UNIT; L3 ROUTE |
| [`storey_qvalue`](storey_qvalue.md) | Storey q-values | B | L2 UNIT; L3 EXECUTED |
| [`structure_altloc_inventory`](structure_altloc_inventory.md) | Alternate conformer inventory | C | L2 UNIT; L3 ROUTE |
| [`structure_amide_pi_bonds`](structure_amide_pi_bonds.md) | Amide-pi interactions | C | L2 UNIT; L3 ROUTE |
| [`structure_anm_modes`](structure_anm_modes.md) | ANM 模式分析 | C | L2 UNIT; L3 ROUTE |
| [`structure_aromatic_stacking`](structure_aromatic_stacking.md) | Aromatic stacking | C | L2 UNIT; L3 ROUTE |
| [`structure_bfactor_profile`](structure_bfactor_profile.md) | Structure B-factor Profile | C | L2 UNIT; L3 ROUTE |
| [`structure_ca_distance_matrix`](structure_ca_distance_matrix.md) | CA distance matrix | C | L2 UNIT; L3 ROUTE |
| [`structure_cation_pi`](structure_cation_pi.md) | Cation-pi interactions | C | L2 UNIT; L3 ROUTE |
| [`structure_cavity_druggability`](structure_cavity_druggability.md) | Cavity druggability | C | L2 UNIT; L3 ROUTE |
| [`structure_cavity_lining`](structure_cavity_lining.md) | Cavity lining residues | C | L2 UNIT; L3 ROUTE |
| [`structure_cavity_scan`](structure_cavity_scan.md) | Buried cavity scan | C | L2 UNIT; L3 ROUTE |
| [`structure_chi_angles`](structure_chi_angles.md) | Side-chain chi angles | C | L2 UNIT; L3 ROUTE |
| [`structure_cis_peptides`](structure_cis_peptides.md) | Cis peptide bonds from omega dihedrals | C | L2 UNIT; L3 ROUTE |
| [`structure_contact_order`](structure_contact_order.md) | Structure contact order | C | L2 UNIT; L3 ROUTE |
| [`structure_contacts`](structure_contacts.md) | Residue contact network | C | L2 UNIT; L3 ROUTE |
| [`structure_disorder_profile`](structure_disorder_profile.md) | Structure disorder profile | C | L2 UNIT; L3 ROUTE |
| [`structure_disulfide_bonds`](structure_disulfide_bonds.md) | Structure disulfide bonds | C | L2 UNIT; L3 ROUTE |
| [`structure_dockq`](structure_dockq.md) | DockQ 复合物质量评分 | B | L2 UNIT; L3 EXECUTED |
| [`structure_domain_boundary`](structure_domain_boundary.md) | Structure domain boundary | C | L2 UNIT; L3 ROUTE |
| [`structure_dssp_segments`](structure_dssp_segments.md) | DSSP secondary-structure segments | B | L2 UNIT; L3 EXECUTED |
| [`structure_glycosylation_sites`](structure_glycosylation_sites.md) | Glycosylation sites | C | L2 UNIT; L3 ROUTE |
| [`structure_gnm_flexibility`](structure_gnm_flexibility.md) | GNM 柔性分析 | C | L2 UNIT; L3 ROUTE |
| [`structure_halogen_bond_scan`](structure_halogen_bond_scan.md) | Halogen bond scan | B | L2 UNIT; L3 EXECUTED |
| [`structure_hbonds`](structure_hbonds.md) | Backbone Hydrogen Bonds | C | L2 UNIT; L3 ROUTE |
| [`structure_helix_bend`](structure_helix_bend.md) | Helix axis bend | C | L2 UNIT; L3 ROUTE |
| [`structure_helix_geometry`](structure_helix_geometry.md) | Structure Helix Geometry | C | L2 UNIT; L3 ROUTE |
| [`structure_helix_helix_angle`](structure_helix_helix_angle.md) | Helix-helix angle and spacing | C | L2 UNIT; L3 ROUTE |
| [`structure_interface_core`](structure_interface_core.md) | Interface core residues | C | L2 UNIT; L3 ROUTE |
| [`structure_interface_residue_energy`](structure_interface_residue_energy.md) | 界面残基能量分解 | B | L2 UNIT; L3 EXECUTED |
| [`structure_lddt`](structure_lddt.md) | lDDT 局部距离差异检验 | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_burial`](structure_ligand_burial.md) | Ligand burial | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_clash`](structure_ligand_clash.md) | Ligand steric clashes | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_geometry_qc`](structure_ligand_geometry_qc.md) | 配体几何与碰撞质检 | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_interaction_fingerprint`](structure_ligand_interaction_fingerprint.md) | Ligand interaction fingerprint | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_pose_qc`](structure_ligand_pose_qc.md) | 配体姿态 PoseBusters 体检 | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_pose_rmsd`](structure_ligand_pose_rmsd.md) | Ligand pose RMSD | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_redock_qc`](structure_ligand_redock_qc.md) | 配体 redock 几何校验 | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_residue_map`](structure_ligand_residue_map.md) | Ligand residue contact map | B | L2 UNIT; L3 EXECUTED |
| [`structure_ligand_strain`](structure_ligand_strain.md) | Ligand internal strain | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_communication_path`](structure_md_communication_path.md) | 动态通讯路径 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_conformational_clusters`](structure_md_conformational_clusters.md) | 构象聚类 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_contact_occupancy`](structure_md_contact_occupancy.md) | MD 残基接触占有率 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_dihedral_occupancy`](structure_md_dihedral_occupancy.md) | MD 主链二面角占有率 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_dssp_transitions`](structure_md_dssp_transitions.md) | 二级结构状态转换 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_free_energy_landscape`](structure_md_free_energy_landscape.md) | 自由能景观 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_hbond_lifetime`](structure_md_hbond_lifetime.md) | 氢键寿命 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_hbond_occupancy`](structure_md_hbond_occupancy.md) | MD 氢键占有率 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_interface_occupancy`](structure_md_interface_occupancy.md) | MD interface occupancy | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_ligand_rmsd`](structure_md_ligand_rmsd.md) | MD 配体位移 RMSD | D | L2 UNIT; L3 SKIP |
| [`structure_md_markov_states`](structure_md_markov_states.md) | 马尔可夫状态模型 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_pca`](structure_md_pca.md) | 轨迹主成分分析 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_quasiharmonic_entropy`](structure_md_quasiharmonic_entropy.md) | 准谐振熵 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_rotamer_states`](structure_md_rotamer_states.md) | 侧链旋转异构状态 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_salt_bridge_occupancy`](structure_md_salt_bridge_occupancy.md) | MD 盐桥占有率 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_sasa_occupancy`](structure_md_sasa_occupancy.md) | MD 残留溶剂可及面积统计 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_ss_occupancy`](structure_md_ss_occupancy.md) | MD 轨迹二级结构占有率 | B | L2 UNIT; L3 EXECUTED |
| [`structure_md_tica`](structure_md_tica.md) | TICA 慢成分分析 | B | L2 UNIT; L3 EXECUTED |
| [`structure_metal_coordination`](structure_metal_coordination.md) | Metal coordination shells | B | L2 UNIT; L3 EXECUTED |
| [`structure_missing_residues`](structure_missing_residues.md) | Missing residues between chain segments | C | L2 UNIT; L3 ROUTE |
| [`structure_openmm_energy`](structure_openmm_energy.md) | OpenMM potential energy | B | L2 UNIT; L3 EXECUTED |
| [`structure_openmm_md_rmsf`](structure_openmm_md_rmsf.md) | 短程 OpenMM MD 与残基柔性 (RMSF) | B | L2 UNIT; L3 EXECUTED |
| [`structure_openmm_md_stability`](structure_openmm_md_stability.md) | OpenMM 短程分子动力学稳定性 | B | L2 UNIT; L3 EXECUTED |
| [`structure_packing_density`](structure_packing_density.md) | Structure packing density | C | L2 UNIT; L3 ROUTE |
| [`structure_pae_summary`](structure_pae_summary.md) | PAE matrix summary | B | L2 UNIT; L3 EXECUTED |
| [`structure_paratope_predict`](structure_paratope_predict.md) | Paratope prediction | C | L2 UNIT; L3 ROUTE |
| [`structure_pdbqt_flexible_receptor`](structure_pdbqt_flexible_receptor.md) | 柔性受体 PDBQT（刚性 + 柔性残基） | C | L2 UNIT; L3 ROUTE |
| [`structure_phi_psi`](structure_phi_psi.md) | Backbone phi/psi and Ramachandran regions | C | L2 UNIT; L3 ROUTE |
| [`structure_plddt_profile`](structure_plddt_profile.md) | Per-residue pLDDT profile | C | L2 UNIT; L3 ROUTE |
| [`structure_pocket_detect`](structure_pocket_detect.md) | fpocket 口袋检测 | B | L2 UNIT; L3 EXECUTED |
| [`structure_protonation_pka`](structure_protonation_pka.md) | PROPKA protonation states | C | L2 UNIT; L3 ROUTE |
| [`structure_protonation_sites`](structure_protonation_sites.md) | Protonation sites | C | L2 UNIT; L3 ROUTE |
| [`structure_radius_of_gyration`](structure_radius_of_gyration.md) | Radius of gyration | C | L2 UNIT; L3 ROUTE |
| [`structure_rmsd`](structure_rmsd.md) | Structure RMSD | B | L2 UNIT; L3 EXECUTED |
| [`structure_salt_bridges`](structure_salt_bridges.md) | Structure salt bridges | C | L2 UNIT; L3 ROUTE |
| [`structure_secondary_structure`](structure_secondary_structure.md) | Structure secondary structure | C | L2 UNIT; L3 ROUTE |
| [`structure_ss_bridge_network`](structure_ss_bridge_network.md) | SSE bridge network | C | L2 UNIT; L3 ROUTE |
| [`structure_surface_hydrophobicity`](structure_surface_hydrophobicity.md) | Per-residue surface hydrophobicity | C | L2 UNIT; L3 ROUTE |
| [`structure_tm_score`](structure_tm_score.md) | TM-score 结构相似度 | B | L2 UNIT; L3 EXECUTED |
| [`structure_zinc_sites`](structure_zinc_sites.md) | Structural zinc sites | B | L2 UNIT; L3 EXECUTED |
| [`stuart_maxwell`](stuart_maxwell.md) | Stuart-Maxwell test | B | L2 UNIT; L3 EXECUTED |
| [`stuart_maxwell_test`](stuart_maxwell_test.md) | Stuart-Maxwell marginal homogeneity test | B | L2 UNIT; L3 EXECUTED |
| [`studentized_residuals`](studentized_residuals.md) | Studentized residuals | B | L2 UNIT; L3 EXECUTED |
| [`svm_classifier`](svm_classifier.md) | Linear SVM classifier | E | L2 SKIP; L3 ROUTE |
| [`svm_regressor`](svm_regressor.md) | Linear SVM regressor | D | L2 SMOKE; L3 ROUTE |
| [`synthetic_control`](synthetic_control.md) | Synthetic control ATT | C | L2 UNIT; L3 ROUTE |
| [`tajimas_d`](tajimas_d.md) | Tajima's D | B | L2 UNIT; L3 EXECUTED |
| [`tamhane_t2`](tamhane_t2.md) | Tamhane T2 test | B | L2 UNIT; L3 EXECUTED |
| [`taxon_abundance_collapse`](taxon_abundance_collapse.md) | Collapse a taxonomic abundance table to one rank | C | L2 UNIT; L3 ROUTE |
| [`tcr_diversity`](tcr_diversity.md) | TCR repertoire diversity indices | C | L2 UNIT; L3 ROUTE |
| [`theil_sen_regressor`](theil_sen_regressor.md) | Theil-Sen regressor | C | L2 UNIT; L3 ROUTE |
| [`theil_u`](theil_u.md) | Theil's uncertainty coefficient | C | L2 UNIT; L3 ROUTE |
| [`time_dependent_auc`](time_dependent_auc.md) | Time-dependent AUC | B | L2 UNIT; L3 EXECUTED |
| [`tmm_normalize`](tmm_normalize.md) | TMM normalization | C | L2 UNIT; L3 ROUTE |
| [`tobit`](tobit.md) | Tobit censored regression | C | L2 UNIT; L3 ROUTE |
| [`topic_lda`](topic_lda.md) | Topic LDA | C | L2 UNIT; L3 ROUTE |
| [`tost_equivalence`](tost_equivalence.md) | TOST equivalence test | C | L2 UNIT; L3 ROUTE |
| [`trajectory_gene_trends`](trajectory_gene_trends.md) | trajectory_gene_trends | C | L2 UNIT; L3 ROUTE |
| [`transformer_classifier`](transformer_classifier.md) | Transformer classifier | B | L2 UNIT; L3 EXECUTED |
| [`translate`](translate.md) | Translate sequences | C | L2 UNIT; L3 ROUTE |
| [`transpose`](transpose.md) | 维度转置 | C | L2 UNIT; L3 ROUTE |
| [`tree_balance`](tree_balance.md) | Tree shape statistics | C | L2 UNIT; L3 ROUTE |
| [`tree_consensus`](tree_consensus.md) | Tree split consensus | C | L2 UNIT; L3 ROUTE |
| [`tree_dating`](tree_dating.md) | Root-to-tip dating | C | L2 UNIT; L3 ROUTE |
| [`tree_mrca`](tree_mrca.md) | Most recent common ancestor of two tips | B | L2 UNIT; L3 EXECUTED |
| [`tree_outgroup_root`](tree_outgroup_root.md) | Outgroup rooting | C | L2 UNIT; L3 ROUTE |
| [`tree_parsimony_score`](tree_parsimony_score.md) | Fitch parsimony score of a tree and character matrix | C | L2 UNIT; L3 ROUTE |
| [`tree_prune_tips`](tree_prune_tips.md) | Prune tree tips | C | L2 UNIT; L3 ROUTE |
| [`tree_quartet_support`](tree_quartet_support.md) | Quartet topology support | C | L2 UNIT; L3 ROUTE |
| [`tree_robinson_foulds`](tree_robinson_foulds.md) | Robinson-Foulds distance | C | L2 UNIT; L3 ROUTE |
| [`tree_root_midpoint`](tree_root_midpoint.md) | Midpoint root a tree | C | L2 UNIT; L3 ROUTE |
| [`tree_ultrametric`](tree_ultrametric.md) | Ultrametricity check for a dated tree | C | L2 UNIT; L3 ROUTE |
| [`trnascan_se`](trnascan_se.md) | tRNAscan-SE tRNA genes | B | L2 UNIT; L3 EXECUTED_SRV |
| [`truncated_svd`](truncated_svd.md) | Truncated SVD | C | L2 UNIT; L3 ROUTE |
| [`tsallis`](tsallis.md) | Tsallis diversity profiles | B | L2 UNIT; L3 EXECUTED |
| [`tsne`](tsne.md) | t-SNE | C | L2 UNIT; L3 ROUTE |
| [`ttest_one_sample`](ttest_one_sample.md) | One-sample t-test | A- | L2 ORACLE; L3 ROUTE |
| [`ttest_paired`](ttest_paired.md) | Paired t-test | C | L2 UNIT; L3 ROUTE |
| [`tukey_hsd`](tukey_hsd.md) | Tukey HSD | C | L2 UNIT; L3 ROUTE |
| [`tukey_test`](tukey_test.md) | Tukey HSD test | B | L2 UNIT; L3 EXECUTED |
| [`turning_point`](turning_point.md) | Turning point test | C | L2 UNIT; L3 ROUTE |
| [`turning_point_test`](turning_point_test.md) | Turning point randomness test | C | L2 UNIT; L3 ROUTE |
| [`umap`](umap.md) | UMAP | C | L2 UNIT; L3 ROUTE |
| [`unweighted_unifrac`](unweighted_unifrac.md) | Unweighted UniFrac | B | L2 UNIT; L3 EXECUTED |
| [`upgma`](upgma.md) | UPGMA tree | B | L2 UNIT; L3 EXECUTED |
| [`uplift_qini_curve`](uplift_qini_curve.md) | Uplift Qini curve | C | L2 UNIT; L3 ROUTE |
| [`uplift_t_learner`](uplift_t_learner.md) | Uplift T-learner | C | L2 UNIT; L3 ROUTE |
| [`vae_anomaly`](vae_anomaly.md) | Variational autoencoder anomaly score | B | L2 UNIT; L3 EXECUTED |
| [`van_waerden`](van_waerden.md) | Van der Waerden test | B | L2 UNIT; L3 EXECUTED |
| [`var_model`](var_model.md) | Vector autoregression | B | L2 UNIT; L3 EXECUTED |
| [`var_test`](var_test.md) | Two-sample F test for variances | C | L2 UNIT; L3 ROUTE |
| [`variance_ratio`](variance_ratio.md) | Variance ratio F test | C | L2 UNIT; L3 ROUTE |
| [`variant_consequence`](variant_consequence.md) | variant_consequence | C | L2 UNIT; L3 ROUTE |
| [`variant_impact_summary`](variant_impact_summary.md) | variant_impact_summary | C | L2 UNIT; L3 ROUTE |
| [`variation_of_information`](variation_of_information.md) | Variation of information | C | L2 UNIT; L3 ROUTE |
| [`varimax_rotation`](varimax_rotation.md) | Varimax rotation | C | L2 UNIT; L3 ROUTE |
| [`varpart`](varpart.md) | Variance partitioning | C | L2 UNIT; L3 ROUTE |
| [`vcf_concat`](vcf_concat.md) | vcf_concat | C | L2 UNIT; L3 ROUTE |
| [`vcf_concordance`](vcf_concordance.md) | vcf_concordance | C | L2 UNIT; L3 ROUTE |
| [`vcf_filter`](vcf_filter.md) | vcf_filter | C | L2 UNIT; L3 ROUTE |
| [`vcf_hardy_weinberg`](vcf_hardy_weinberg.md) | Hardy-Weinberg exact test | C | L2 UNIT; L3 ROUTE |
| [`vcf_merge`](vcf_merge.md) | vcf_merge | C | L2 UNIT; L3 ROUTE |
| [`vcf_normalize`](vcf_normalize.md) | VCF normalise | C | L2 UNIT; L3 ROUTE |
| [`vcf_relatedness`](vcf_relatedness.md) | vcf_relatedness | C | L2 UNIT; L3 ROUTE |
| [`vcf_sample_stats`](vcf_sample_stats.md) | Per-sample VCF genotype statistics | C | L2 UNIT; L3 ROUTE |
| [`vcf_site_missingness`](vcf_site_missingness.md) | Per-site VCF call rate | C | L2 UNIT; L3 ROUTE |
| [`vcf_stats`](vcf_stats.md) | vcf_stats | C | L2 UNIT; L3 ROUTE |
| [`vecm`](vecm.md) | Vector error correction model | B | L2 UNIT; L3 EXECUTED |
| [`vhh_humanization_mutations`](vhh_humanization_mutations.md) | VHH humanization mutations | B | L2 UNIT; L3 EXECUTED_SRV |
| [`vhh_humanization_score`](vhh_humanization_score.md) | VHH humanization score | B | L2 UNIT; L3 EXECUTED_SRV |
| [`vif`](vif.md) | Variance inflation factor | C | L2 UNIT; L3 ROUTE |
| [`vina_dock`](vina_dock.md) | AutoDock Vina docking | D | L2 UNIT; L3 SKIP |
| [`vina_dock_batch`](vina_dock_batch.md) | Batch docking | D | L2 UNIT; L3 SKIP |
| [`vina_dock_python`](vina_dock_python.md) | AutoDock Vina 对接 (Python 绑定) | B | L2 UNIT; L3 EXECUTED |
| [`vina_pose_cluster`](vina_pose_cluster.md) | Docking pose clustering | D | L2 UNIT; L3 SKIP |
| [`vina_pose_rmsd`](vina_pose_rmsd.md) | Pose RMSD to a reference | D | L2 UNIT; L3 SKIP |
| [`violin`](violin.md) | Violin plot | B | L2 UNIT; L3 EXECUTED |
| [`volcano`](volcano.md) | Volcano | C | L2 UNIT; L3 ROUTE |
| [`von_neumann`](von_neumann.md) | Von Neumann randomness test | C | L2 UNIT; L3 ROUTE |
| [`watterson_theta`](watterson_theta.md) | Watterson's theta | B | L2 UNIT; L3 EXECUTED |
| [`weighted_kappa`](weighted_kappa.md) | Weighted kappa | B | L2 UNIT; L3 EXECUTED |
| [`weighted_unifrac`](weighted_unifrac.md) | Weighted UniFrac | B | L2 UNIT; L3 EXECUTED |
| [`welch_anova`](welch_anova.md) | Welch ANOVA | C | L2 UNIT; L3 ROUTE |
| [`wgcna_soft_threshold`](wgcna_soft_threshold.md) | Scale-free topology fit for soft-threshold powers | C | L2 UNIT; L3 ROUTE |
| [`white_test`](white_test.md) | White heteroskedasticity test | C | L2 UNIT; L3 ROUTE |
| [`wilcoxon`](wilcoxon.md) | Wilcoxon signed-rank test | C | L2 UNIT; L3 ROUTE |
| [`winsorize`](winsorize.md) | Winsorise | C | L2 UNIT; L3 ROUTE |
| [`woolf_test`](woolf_test.md) | Woolf test | C | L2 UNIT; L3 ROUTE |
| [`xgboost_regressor`](xgboost_regressor.md) | XGBoost regressor | C | L2 UNIT; L3 ROUTE |
| [`xic_extract`](xic_extract.md) | Extracted ion chromatogram peaks | C | L2 UNIT; L3 ROUTE |
| [`youden_index`](youden_index.md) | Youden index | B | L2 UNIT; L3 EXECUTED |
| [`yuen_test`](yuen_test.md) | Yuen trimmed-mean test | C | L2 UNIT; L3 ROUTE |
| [`zero_inflated_negative_binomial`](zero_inflated_negative_binomial.md) | Zero-inflated negative binomial regression | B | L2 UNIT; L3 EXECUTED |
| [`zero_inflated_poisson`](zero_inflated_poisson.md) | Zero-inflated Poisson regression | C | L2 UNIT; L3 ROUTE |
| [`zivot_andrews`](zivot_andrews.md) | Zivot-Andrews structural break unit-root test | B | L2 UNIT; L3 EXECUTED |
| [`zscore`](zscore.md) | Z-score scaling | A- | L2 ORACLE; L3 ROUTE |
