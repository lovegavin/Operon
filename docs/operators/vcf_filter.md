# vcf_filter (`vcf_filter`)

**Category:** Genome  
**Entry point:** `src.task.step.steps.vcf_filter:VcfFilterStep`  
**Source:** [`library/seed/src/task/step/steps/vcf_filter.py`](../../library/seed/src/task/step/steps/vcf_filter.py) (207 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Filter VCF records by quality, FILTER, variant type, depth, missingness and

> Filter a VCF/VCF.gz and write the retained records as a native VCF file. The output is a byte-preserving subset: header meta lines and each retained record are copied verbatim, so INFO/FORMAT fields, phasing and sample order are unchanged. The filtered file is registered as a native result and also exposed as a FileArtifact so downstream operators can consume it directly. Filters are site-level by default; sample-level missingness is only evaluated when ``max_missing_rate <

关键符号：

- `class VcfFilterStep (line 22)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=0, numeric=False, dims=(—), info=(representation)
- 输出: mode=declare, schema={"kind": "file", "numeric": false, "ndim": 0, "dims": [], "info": {"representation": {"type": "string", "const": "vcf"}}, "info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `min_qual` | `0.0` | min 0.0 |
| `require_pass` | `False` | — |
| `biallelic_only` | `False` | — |
| `variant_type` | `any` | choices: any, snps, indels |
| `min_dp` | `0` | min 0 |
| `max_missing_rate` | `1.0` | min 0.0; max 1.0 |
| `region` | `` | — |
| `max_records` | `0` | min 0 |
| `output` | `vcf_filter` | — |

## 2. 用途与解释

Filter a VCF/VCF.gz and write the retained records as a native VCF file.

The output is a byte-preserving subset: header meta lines and each retained
record are copied verbatim, so INFO/FORMAT fields, phasing and sample order
are unchanged.  The filtered file is registered as a native result and also
exposed as a FileArtifact so downstream operators can consume it directly.

Filters are site-level by default; sample-level missingness is only evaluated
when ``max_missing_rate < 1``.

Quality/type/region filtering with a native filtered VCF output.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension363.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^vcf_filter,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
