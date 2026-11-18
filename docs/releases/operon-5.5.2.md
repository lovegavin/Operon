# Operon Studio 5.5.2 release notes

This release makes linking an existing directory to a large resource a guided
operation instead of a free-form one, and exposes the environment dimension of
resources in the API.

## Added

- **A step-by-step link dialog.** Settings → Large resources → "链接已有目录" now
  asks four questions in order:
  1. **Execution location** - this machine or one of the connected servers. The
     selector only appears when at least one server connection is configured.
  2. **Missing environment** - the environments that are not ready yet, taken
     from `/api/environments`; "全部环境" keeps the full list.
  3. **Missing weights or databases** - only resources of that environment that
     declare linkable roots and are not present yet. The list is filtered as
     soon as the environment changes, and an explicit empty note replaces the
     selector when nothing matches.
  4. **Absolute path of the existing directory** - typed by the operator, with
     the allowed link roots shown underneath so a rejected path is obvious
     before submitting.
- **`environments` on every large resource.** `GET /api/v1/large-resources`
  items now carry the environments whose operators read the resource, derived
  from the `resources.environment` field of the operator descriptors. The list
  view shows this as an "所属环境" row.

## Changed

- The ambiguous field names are gone: the source directory is labelled
  **源目录（本机已有）** and the host selector **执行位置**, and the dialog states
  that a link only affects the local file system of the machine that runs it and
  never copies bytes or maps remote files onto this machine.
- Selecting an environment preselects its first linkable resource, so the common
  case needs one click fewer.

## Fixed

- F-21: the dialog asked for a "link location" without saying whether that path
  belongs to this machine or to a remote host, and it could not target a
  specific missing environment or resource; the resource list had no environment
  column at all. Operators of a resource now report their environment, and the
  dialog drives the choice from the missing environment downwards.

## Verification

- `pytest tests/test_resource_api.py` - 12 passed, covering the environment map,
  its tolerance for a service without a catalog, and the snapshot field.
- `npm test` - 43 files, 264 tests passed, including the new
  `src/LargeResources.test.tsx`.
- A clean install of the packaged release is verified for the four-step dialog
  against a real library: `/api/large-resources` reports `environments` for every
  resource, and the dialog offers only the missing environments and their
  linkable resources.

The operator library is unchanged; this release keeps `main-v0.1.29`.
