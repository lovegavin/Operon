<!-- operon:generated -->
# result_report

## Purpose

Close a workflow by turning the final Form (or a file artifact produced
upstream) into a report file. The report is registered as a native result so it
survives the run and appears in the results pane.

## Inputs and outputs

Kind: `operator`. Operator ID: `result_report`.
Input count: `1`.
The single input accepts either a Form or a file artifact. The output is a
report file (`csv`, `json` or `markdown`).

## Parameters

- `title` (string, default `result report`)
- `format` (`csv` | `json` | `markdown`, default `csv`)
- `output` (string, default `report`)
