# Relay proxy for GitHub and package registries

Release assets and dependency traffic have to leave this workstation through
the internal server `172.22.148.93` (`srv`). This directory holds the whole
path: a small authenticated CONNECT proxy on `srv`, an SSH tunnel that
publishes it on the Windows loopback interface, a release publisher that talks
to the GitHub API through that tunnel, and a shell helper that points pip,
HuggingFace, conda, npm and HTTPS git at the same tunnel.

## Why the tunnel is part of the design

The Windows workstation can open TCP connections to high ports on `srv`, but
any non-SSH payload on those ports is reset before it reaches the server
process (`curl: (56) Recv failure: Connection was reset`, and the same for a
plain `python3 -m http.server`). SSH is the only transport that survives the
network path. The proxy therefore listens on `127.0.0.1` only, and Windows
reaches it through `ssh -L`.

```
release publisher (Windows)
        |
        |  HTTPS via proxy  http://operon:<password>@127.0.0.1:18080
        v
ssh -N -L 127.0.0.1:18080:127.0.0.1:18080 srv     (supervised locally)
        |
        v
github_proxy_server.py on srv, 127.0.0.1:18080
        |
        |  CONNECT api.github.com:443 / uploads.github.com:443 ...
        v
GitHub
```

## Files

| File | Role |
| --- | --- |
| `github_proxy_server.py` | stdlib asyncio CONNECT proxy. Basic auth, host/port allowlist, 256 KiB streaming, 900 s idle timeout, rotating access log. |
| `service.sh` | `start`, `stop`, `restart`, `status`, `ensure` on the relay host. Keeps `proxy.pid` and `launcher.log` next to the script. |
| `install_cron.sh` | Installs `@reboot` and `*/5` keepalive entries marked `# operon-github-proxy`. |
| `config.example.json` | Shape of `config.json`; the real password is generated on the server by `--init-config`. |
| `tunnel.ps1` | Supervises the Windows SSH tunnel: `start`, `stop`, `restart`, `status`, `ensure`, `run`, `install-startup`, `remove-startup`. |
| `proxy.ps1` | Deployment and operations entry point: `deploy`, `status`, `start`, `stop`, `restart`, `test`, `logs`, `git`, `env`, `config`, `tunnel-start`, `tunnel-stop`, `tunnel-status`. |
| `publish_release.py` | GitHub release API client that dials through the proxy. `verify`, `list`, `create`, `upload`, `publish`, `check`, `selftest`, `delete-release`. |
| `proxy-env.ps1` | Dot-source helper that exports `HTTPS_PROXY`, `PIP_PROXY`, npm variables and `NO_PROXY` for the current shell. |

## Deploy

Run from the repository root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_proxy\proxy.ps1 -Action deploy -InstallStartup
```

The deploy action copies the server files to
`/public/home/lihj/.operon/github-proxy`, generates `config.json` with a random
password when it is missing, rewrites `listen_host` to `127.0.0.1`, restarts the
service, installs the crontab keepalive, writes the client configuration to
`%USERPROFILE%\.operon\github_proxy.json` (ACL restricted to the current user,
SYSTEM and Administrators), starts the supervised tunnel, installs the HKCU
`Run` entry `OperonGithubProxyTunnel`, and then checks one authorized request
and one anonymous request.

The GitHub token is not copied anywhere by this tooling. It stays on Windows in
`%USERPROFILE%\.operon\gh_token.txt` (classic token with `repo` scope is
enough) and is read by `publish_release.py` at run time. `%USERPROFILE%` expands
to the Windows profile; the file must contain only the token.

## Day-to-day operations

```powershell
# full state: local config, tunnel, remote service, auth probe
powershell -ExecutionPolicy Bypass -File .\scripts\release_proxy\proxy.ps1 -Action status

# restart the relay after a server reboot or a configuration change
powershell -ExecutionPolicy Bypass -File .\scripts\release_proxy\proxy.ps1 -Action restart

# tunnel only
powershell -ExecutionPolicy Bypass -File .\scripts\release_proxy\proxy.ps1 -Action tunnel-status

# relay log on srv
ssh -F "$env:USERPROFILE\.ssh\config" srv "tail -n 50 /public/home/lihj/.operon/github-proxy/proxy.log"
```

`-Action test` additionally runs `publish_release.py verify` and, with
`-SelfTestMB`, a draft-release upload/delete cycle.

## Publishing a release

The token identity is checked first; the response also shows whether the proxy
is actually in use:

```powershell
python .\scripts\release_proxy\publish_release.py verify
```

Expected fields: `login`, `can_push: true`, `proxy: 127.0.0.1:18080`.

Create the release and upload every asset through the tunnel:

```powershell
$assets = @(
    '.\dist\Operon_Setup.exe'
    '.\dist\Operon-4.2.3-Server.zip'
    '.\dist\operon_studio-4.2.3-py3-none-any.whl'
)
python .\scripts\release_proxy\publish_release.py publish `
  --tag v4.2.3 `
  --name "Operon Studio 4.2.3" `
  --body-file .\release\RELEASE_NOTES.md `
  --assets $assets
```

`publish` creates the release when it does not exist yet and skips assets that
are already present. `check --release-id <id> --assets ...` compares local files
against the uploaded size and digest.

A draft round trip that proves the full path, including a several-hundred-MB
body, is:

```powershell
python .\scripts\release_proxy\publish_release.py selftest --size-mb 420
```

The command creates a draft release, uploads a random file, verifies the
returned digest, deletes the draft and removes the temporary file. A 420 MB run
completes at roughly 4 MiB/s over the tunnel.

## Package registries (pip, HuggingFace, conda, npm)

The relay is a plain CONNECT tunnel, so the same tunnel carries package
downloads and uploads once the destination host is allowlisted. The default
list covers:

| Ecosystem | Hosts |
| --- | --- |
| GitHub | `github.com`, `api.github.com`, `uploads.github.com`, `codeload.github.com`, `*.githubusercontent.com`, `github-cloud.s3.amazonaws.com` |
| PyPI | `pypi.org`, `pythonhosted.org` (this suffix also covers `upload.pypi.org` and `files.pythonhosted.org`) |
| Tsinghua mirror | `tuna.tsinghua.edu.cn`, the pip `index-url` configured on this workstation |
| HuggingFace | `huggingface.co`, `hf.co` (CDN), `hf-mirror.com` |
| conda / micromamba | `anaconda.org`, `anaconda.com`, `mamba.pm` |
| npm / Node | `npmjs.org`, `npmmirror.com`, `nodejs.org` |

Load the client variables into a shell before running a tool. The deploy
action also copies the helper to `%USERPROFILE%\.operon\proxy-env.ps1`;
dot-sourcing that local copy avoids the `RemoteSigned` error Windows raises for
a script on a UNC path:

```powershell
. "$env:USERPROFILE\.operon\proxy-env.ps1"
python -m pip download --no-deps --dest .\tmp six
hf download hf-internal-testing/tiny-random-bert config.json --local-dir .\tmp\hf
npm view react version
```

If the local copy is missing, copy `scripts/release_proxy/proxy-env.ps1` there
first, or run `Set-ExecutionPolicy -Scope Process Bypass` for that session.

`proxy-env.ps1` sets `HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY`, `PIP_PROXY`,
`NO_PROXY` and the npm variants from `%USERPROFILE%\.operon\github_proxy.json`.
Dot-source it (the leading dot) so the variables stay in the current shell.

When `PIP_INDEX_URL` is not already set, the helper points pip at
`https://pypi.org/simple`. The Tsinghua mirror (`pypi.tuna.tsinghua.edu.cn`)
returns its "access denied" page for this relay's IPv4 egress path, while
upstream PyPI works through the same tunnel. Override `PIP_INDEX_URL` before
dot-sourcing if you need a different index.

Because pip on this workstation points at the Tsinghua mirror, plain
`pip install` sends the mirror through the tunnel. To fetch from upstream PyPI
instead, add `--index-url https://pypi.org/simple`. Uploads use the same
allowlist: `twine upload` reaches `upload.pypi.org`, and `hf upload` reaches
`huggingface.co`.

If a tool reports `403` for a new host, add that host to `allow_hosts` in
`/public/home/lihj/.operon/github-proxy/config.json`, restart the relay, and
update `config.example.json` so a fresh deploy keeps it.

## Persistence

Two independent keepalives are installed:

- `srv`: crontab entries `@reboot .../service.sh ensure` and `*/5 .../service.sh ensure`.
- Windows: HKCU `Run` value `OperonGithubProxyTunnel`, which starts
  `%USERPROFILE%\.operon\tunnel.ps1 run` at logon. The supervisor restarts the
  `ssh` child within about five seconds if it dies; the tunnel script is copied
  out of the repository so a logon does not depend on the UNC workspace.

## Security notes

- The proxy is bound to `127.0.0.1` on `srv`; it is not exposed to the lab
  network. The only ingress is the SSH local forward owned by the current user.
- Every request needs `Proxy-Authorization: Basic ...`. The password is 24
  random bytes (`secrets.token_urlsafe(24)`), stored in `config.json` with mode
  `0600` and mirrored to the Windows client file whose ACL is restricted.
- Only `CONNECT` to an allowlisted host on port 443 is accepted. Other
  hosts get `403`, other methods `405`, missing credentials `407`.
- The GitHub token never reaches `srv` and is never written into the repository.

## Limits and troubleshooting

- Upstream hosts are resolved to IPv4 by default (`prefer_ipv4: true`). The
  IPv6 egress resets connections to some CDNs, including HuggingFace; only
  disable it when IPv6 is known to work from `srv`.
- WSL cannot reach `172.22.148.93:22`, and the tunnel binds the Windows
  loopback interface, so publish from Windows Python, not from WSL.
- Git pushes use `git@github.com:lovegavin/Operon.git` (SSH) and therefore do
  not traverse this HTTP proxy. `proxy.ps1 -Action git` is available if an
  HTTPS remote should use it; do not enable it while the tunnel is down.
- `Connection was reset` from Windows means the SSH tunnel is down or the
  request bypassed it: run `proxy.ps1 -Action status`, then `-Action tunnel-start`.
- `407` means the client is not sending the credentials from
  `%USERPROFILE%\.operon\github_proxy.json`.
- `403` means the target host is not on the allowlist in `config.json`; add
  only the specific registry host and restart the service.
- `502` means `srv` could not open the upstream connection; check the server's
  outbound access and the relay log.
