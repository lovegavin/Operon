# Operon Studio 5.7.19

## Added

- `OPERON_CONDA_CHANNELS` selects the conda channels used when an environment is
  created or repaired. Point it at a mirror when the default channels are slow,
  for example
  `https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge`.
- `operon_remote_install` accepts `password` and `passphrase`, matching the
  desktop installer form.
- `operon_browse` accepts `offset` and `hidden` so remote listings page and show
  dotfiles the same way the desktop does.
- `operon_remote_status` accepts `brief=False` for the full status payload the
  desktop detail view reads.
- `docs/design/mcp_http_parity.md` records every frontend API method, the MCP
  tool and the CLI verb that cover it, plus the deliberate omissions.

## Changed

- Conda work now gets an 1800 second startup grace instead of the 300 second
  silence guard that pip uses. `micromamba` buffers its output, so a slow
  metadata fetch looked like a hang.
- Growth of the mamba package cache counts as activity while conda runs, so a
  large download no longer looks silent.
- The artifact index tolerates legacy report entries that carry no
  `artifact_id` instead of failing the whole listing.

## Fixed

- F-127 an environment creation could be killed after 300 seconds with
  `printed nothing in 300s` while conda was still resolving packages.
- F-128 `/api/v1/jobs/{id}/artifacts` returned 500 when a completed job carried
  a legacy report entry without an artifact identifier.
- F-129 `operon_remote_install` forwarded only `force` and silently dropped the
  credentials the desktop sends.
- F-130 `operon_browse` ignored the remote paging and hidden flags.

## Known limitations

- `operon_remote_source` remains degraded: the `/api/v1/remotes/{key}/source`
  handler ignores the request body, so the remote server rejects the call. The
  parity document records the two places that need to change.
