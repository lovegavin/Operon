# Operon Studio 5.7.35

A regression fix for 5.7.34: every submission through `POST /api/v1/jobs`
answered `500 本地服务处理失败` because `_pool_error` was inserted at module
level inside the `TaskService` body, which ended the class there and left
`_launch`, `_prepare_submission`, `submit` and `_submit` as nested functions of
the helper.

## Fixed

- `application`: `_pool_error` now lives after `TaskService`, and the class owns
  `_launch`, `_prepare_submission`, `submit`, `_submit`, `_journal`, `_reuse`,
  `_submit_file` and `logs` again, so the HTTP and MCP submission paths work.

## Notes

- Library stays at `1.1.22`; only the application changed.
