# Operon Studio 5.7.35 — acceptance report

## What changed

`5.7.34` shipped `_pool_error` at module level inside the `TaskService` body.
That ended the class there and turned `_launch`, `_prepare_submission`,
`submit`, `_submit`, `_journal`, `_reuse`, `_submit_file` and `logs` into
nested functions of the helper, so every `POST /api/v1/jobs` answered
`500 本地服务处理失败` with
`AttributeError: 'TaskService' object has no attribute 'submit'`
(`operon/control_api.py:382`).

`5.7.35` moves the helper after the class; the class owns its methods again and
the CLI, HTTP and MCP submission paths work. Library stays at `1.1.22`.

## Evidence

| check | result |
| --- | --- |
| `python3 -c 'import operon.application'` | passes |
| `TaskService` methods | `__init__ backend details list cancel active_ids _recover launch _launch _prepare_submission submit _submit _journal _reuse _submit_file logs` |
| module helpers | `_pool_error` |
| `pytest tests/test_pool_busy.py tests/test_pool_registration_binding.py` | 5 passed |
| remote environments | 19/19 ready (`core` gained the `vina` resource, downloaded 4,089,576 B) |
| submission | `POST /api/v1/jobs` accepted after deploy |

## Known gaps at this point

- `hmmer_domains` needs a user-supplied pressed `Pfam-A.hmm` (documented in
  `docs/large_resources.md`); `esm_pseudo_likelihood` wants an explicit
  `model_path`.
- Defect ledger (`<workdir>\p6\DEFECTS.md`) before this fix: 757 operators
  attempted, 385 complete, 372 failing, split by cause.
