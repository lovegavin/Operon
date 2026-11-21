# Operon Studio 5.7.24 — test report

Scope: acceptance of the runtime and planning fixes in 5.7.24 on a freshly
installed Windows instance driving a cleared Linux server (`licai-srv`).

## Environment

- Fresh install: `D:\OperonAccept`, build `5.7.24`, port 5880, Edge attached over
  CDP for every UI step (text-only inspection, no screenshots).
- Server: `/public/home/lihj/Operon`, deployment `code-*` written by the UI
  "安装 / 升级服务端" action, library bundle 7 packages / 1182 descriptors /
  1074 operators.

## UI route

`CsvReader(rt/data/iris.csv) → PCA` was composed in the canvas and executed from
the run button:

- prepare reached `ready` (`phase=server:code`), the fixed plan ran one unit,
  `native-chain · #1` completed with exit 0;
- the step produced 150 observations and two components, explained variance
  `[0.7470533000277259, 0.1843525688793199]`;
- the artifact was committed (`state=committed`).

## Known limitations

- Final numbers for the 5.7.24 sweep batches are appended before release.
