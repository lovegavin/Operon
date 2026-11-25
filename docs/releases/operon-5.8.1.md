# Operon Studio 5.8.1

Released 2026-11-25. Library: main-v1.2.0.

5.8.1 is a patch release. The operator library is unchanged.

## Fixed

- **A remote environment's log is read from where the installer writes it.**
  The desktop asked the server for `environments/<name>.log`, but the installer
  has always written `<environments>/.operon-environment-logs/<name>.log`, so
  "view log" reported that the environment had no output even when the pip
  transcript was complete. The server now resolves the path through
  `environment_install.log_path()` and still falls back to the old flat name for
  environments prepared by earlier builds.
