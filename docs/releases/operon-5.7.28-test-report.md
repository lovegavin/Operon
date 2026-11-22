# Operon Studio 5.7.28 — acceptance report

Scope: the single layout change in `operon-5.7.28.md`, verified on the development host
against the 5.7.27 install.

## Defect

| # | Symptom | Cause | Fix |
|---|---------|-------|-----|
| 1 | Settings → 执行 showed the concurrency field crushed together: legend, hint and input stacked inside 12px margins, the input touching the hint text | The block was `legend` + `p.settings-hint` + an inline `label.concurrency-field` whose only gap was 10px; no card, no column split | The section is a heading plus a card row; the copy and the input are separate flex children with a 20px gap and 16px padding |

## Evidence

- `frontend/src/ConcurrencySettings.tsx` renders `section.execution-settings` with an
  `h4`, one hint and `label.concurrency-field > span.concurrency-copy + input`.
- Geometry read from the installed 5.7.27 build over CDP after opening 设置 → 执行:
  `section 560×134`, heading `y=350`, hint `y=377`, card `560×75` at `y=409`,
  copy block `197×41` at `x=249`, input `88×39` at `x=688`, `gap: 20px`,
  `padding: 16px`, `scrollWidth == clientWidth == 560`.
- The stored value survived the redeploy: the field shows `12`, and
  `GET /api/preferences` returns `{"language": "system", "theme": "system",
  "parallel_tasks": 12}`.
- `npm test` in the packaged frontend: 44 files, 287 tests, exit 0.
