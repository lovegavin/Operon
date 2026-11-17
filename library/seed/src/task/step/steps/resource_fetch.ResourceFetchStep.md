# Fetch large-resource files

## Purpose

Download the files declared for one entry of `src/task/step/steps/resources.json`
into that resource's root directory. This is the library-side half of the resource
manager: the application can call it as a zero-input operator through the existing
MCP `operon_submit` tool, with no application change.

The operator does not decide which model or database a workflow needs. It only
fetches what the manifest declares; run `resource_preflight` afterwards to confirm
that every expected file is present.

## Inputs and outputs

Kind: `operator`. Operator ID: `resource_fetch`.
Input count: `0`. Output: one Form with dims `["file", "statistic"]` and statistics
`["downloaded", "bytes"]`. The `info` object reports the resource id, resolved root,
per-file status, and the receipt path.

## Parameters

- `resource`: manifest id to fetch. Required.
- `root`: optional destination directory. When empty, `OPERON_*` or the first
  manifest root is used.
- `overwrite`: replace an existing file only when its declared size or sha256 does
  not match.
- `output`: name of the output slot (default `fetched`).

## Behaviour

1. Reject resources without a `downloads` list and show the manual install text.
2. Validate every destination path as a relative path inside the resource root;
   reject `..`, absolute paths and symlinks.
3. Stream each HTTPS URL to `<name>.part` in chunks and hash while writing.
4. When `bytes` is declared, require an exact size; when `sha256` is declared,
   require an exact digest.
5. Move the verified file into place with an atomic rename.
6. Write `receipt-<resource>.json` in the resource root.

Existing files that match the declared metadata are reported as `existing` and are
not downloaded again.

## Limitations

- Only `https://` URLs are accepted; repository checkouts and gated HuggingFace
  resources need a different workflow.
- The operator cannot provide live byte-level progress to the current MCP client.
  Long downloads should be submitted as durable jobs and polled with `operon_job`
  and `operon_logs`.
- A gated resource needs its token in the environment variable named by the
  manifest; the operator never prints the token.
- The manifest is trusted library metadata; this operator does not accept arbitrary
  user-provided URLs.

## Examples

Submit a zero-input graph with a single `resource_fetch` node and `resource` set to
`esmfold`, then run `resource_preflight` for the same id. Use
`operon_download_result`/`operon_artifact_table` on the small result Form when the
job completes.

## Source

Implementation: `src/task/step/steps/resource_fetch.py` (`ResourceFetchStep`).
