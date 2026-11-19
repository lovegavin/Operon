# Operon Studio 5.7.10

5.7.10 closes the gaps reported after 5.7.9: environments without registered
resources must not advertise an empty resource card, and the installer must
survive slow mirrors without aborting healthy downloads.

## Fixed

- **F-95** The runtime detail view rendered a resource card even when an
  environment declares no managed resources, so tool-only environments such as
  `core`, `openmm81`, `genomics`, `hic` and `rna` showed an empty unit list.
  The card is now omitted when the unit count is zero and the panel no longer
  prints the "no registered resources" hint.
- **F-96** Promotion left console scripts pointing at the staging directory
  (`#!.../.staging-<name>-<hash>/...`). The installer now rewrites those
  shebangs to the promoted location right after the tree is renamed.
- **F-97** pip and conda steps could be killed by the inactivity watchdog while
  a large wheel was downloading without line output. Downloads now report
  `--progress-bar raw`, and the watchdog also refreshes on directory activity.
- **F-98** The pip index was hard-coded to PyPI. `OPERON_PIP_INDEX` and
  `OPERON_PIP_TRUSTED_HOST` now override it so mirrors can be used.
- **F-99** Environment logs could be blank when a preparation never wrote a
  log file. `GET /api/environments/<name>/log` now renders the recorded
  command, phase, byte counters and error message when no log file exists,
  so the log drawer always shows the real state instead of an empty panel.

## Added

- **F-100** `result_report` operator. ResultReport was missing from the
  product: workflows could not materialise a report. The operator accepts a
  Form or a file artifact, writes a `csv`, `json` or `markdown` report and
  registers it as a native result, so every route can end at a report.
  The bundled library now declares 1,074 operators.

## Changed

- Dependency, dependency-status and resource accounting already follow the
  Reader-first data model: files enter only through Readers, operators exchange
  Forms, and result reports accept either Forms or files.

- **F-101** `result_report` reported the tensor shape through `form.shape`,
  which the Form type does not expose, so the first report run failed with
  `'Form' object has no attribute 'shape'`. The summary now reads
  `numpy.asarray(form.data).shape`, and `data_formats.inputs[].logical_type`
  is `form` so a Form output can feed the report node directly.

## Interface parity

- **F-102** The MCP and CLI adapters could not reach several controls that the
  UI exposes. Five adapter defects were fixed: the browse tool posted to a
  route that does not exist and used the wrong payload field; the remote
  library tools pointed at missing agent routes; the `profile_id` variants of
  environment retry, cancel and dependency install and of resource download had
  no agent twin; and `operon environment dependency` let its positional `file`
  argument capture the environment name. Nine agent routes were added, the MCP
  surface grew from 79 to 107 tools, and the CLI gained three verbs and seven
  action values. `tests/test_parity_control_plane.py` pins every action to its
  exact route, because `operon/client.py` rewrites `/v1/...` to `/api/v1/...`
  and everything else to `/api/agent/...`.

## Coverage status

The Reader-first sweep connects a real Reader to every operator and terminates
it with `result_report`. The harness now reaches the operator stage for
tabular operators; the remaining failures are data-shape, missing-column and
domain fixtures rather than plumbing. The current run is reported honestly in
the test report; no operator is marked as passing without a produced report.
