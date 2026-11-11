# Export results (`export_results`)

**Category:** data  
**Entry point:** `src.task.step.steps.export_results:ExportResultsStep`  
**Source:** [`library/seed/src/task/step/steps/export_results.py`](../../library/seed/src/task/step/steps/export_results.py) (264 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Export native files or convert annotated data to contact maps, sequences, genome tracks, networks and trees while other branches

> One branch output operator, using the existing v3 FileArtifact

关键符号：

- `def canonical_format() (line 19)`
- `def native_suffix() (line 26)`
- `def native_results() (line 34)`
- `def ordered_labels() (line 63)`
- `def write_array() (line 68)`
- `def write_table() (line 81)`
- `def write_fasta() (line 93)`
- `class ExportResultsStep (line 117)`

协议：v3 / revision ``；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=?, dims=(—), info=(—)
- 输出: mode=declare, schema={"kind": "file", "numeric": false, "ndim": 0, "dims": [], "info": {"representation": {"const": "exported_files"}}, "info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `format` | `auto` | Output format; choices: auto, native, csv, tsv, npy, fasta, pdb, cif, hic, cool, genbank, bed, bedgraph, graphml, newick |
| `filename` | `` | Filename stem |
| `include_labels` | `True` | Include table labels; advanced |
| `buffer_mb` | `1` | Write buffer (MiB); advanced |
| `resolution` | `` | Contact resolution (bp); min 1; advanced |
| `chrom_sizes` | `` | Chromosome sizes; advanced |
| `assembly` | `` | Reference assembly; advanced |
| `topology` | `linear` | DNA topology; choices: linear, circular; advanced |
| `value_column` | `0` | bedGraph value column; min 0; advanced |
| `directed` | `False` | Directed network; advanced |

## 2. 用途与解释

`export_results` saves an intermediate or final result as ordinary files. Add it
as a branch from any compatible data node; connect further calculations to that
same data node. Exporting does not consume or modify the upstream data. The output
port contains a `FileArtifact`, not a replacement numeric Form.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.23 s），导出 None 行，产物 sha256 bd636230e95f0076…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_export_contract.py,test_export_domain.py,test_export_results.py,test_extension110.py,test_extension246.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/export_results |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | ROUTE | library/seed/routes/assembly_ngx_qc/task.yaml |

本次执行细节：

- 状态：PASS，耗时 1.23 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/export_results`。
- 命令：`python scripts/run.py /tmp/cov_sequence/export_results`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

相邻算子 Markdown 是参数约束与失败模式的权威说明；未找到单独的限制段。

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^export_results,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
For a matrix named `counts`, run these steps in a manifest:

```yaml
steps:
  - name: export_results
    inputs: [counts]
    params: {output: counts_csv, format: csv}
  - name: describe
    inputs: [counts]
```

The first branch creates CSV; the second continues analysis of the same matrix.
For ProteinMPNN output `designs`, use `format: fasta` to export only sequences,
or `format: native` for both original sequences and score table. For RFdiffusion,
use `format: pdb` to export all generated backbones.
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
