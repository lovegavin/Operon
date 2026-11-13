# Operon Studio 5.1.12

Released: 2026-11-14

## Fixes

### Remote server provisioning no longer depends on an optional file

`operon/remote/provision.py::source_archive()` built a fixed file list that
included `requirements-hic-linux.txt` unconditionally. Packages that omit the
optional Hi-C requirements failed during "install / upgrade server" with
`FileNotFoundError`.

The archive now includes each file only when it exists, and the 5.1.12 payload
ships `requirements-hic-linux.txt` again.

### Frontend version label matches the installed backend

The packaged `frontend/dist` was built at 5.1.5 and copied verbatim, so the
footer kept showing an older version after upgrades. 5.1.12 rebuilds the
version literal and packages the updated bundle.

## Upgrade

1. Install `Operon_Setup-5.1.12.exe`.
2. Reconnect the remote server and confirm the footer shows 5.1.12.
3. If the server is still older, use "install / upgrade server"; it should no
   longer raise `FileNotFoundError`.

## Compatibility

- `bundle_format` 1, operator protocol 3 / revision 3.7.
- Bundled library `main` 0.1.1 (1174 descriptors), routes 0.1.1 (79 routes).
- Minimum application for the bundled library: 5.1.9.