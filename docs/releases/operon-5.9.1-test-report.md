# Operon 5.9.1 test report

Scope: the 5.9.1 patch release for the remote retire script. The application
version, the packaged library (2.0.0) and the registry are described below.

## Registry

| Scope | Operators | Readers | Routes | Errors |
| --- | ---: | ---: | ---: | ---: |
| packages | 1074 | 110 | 7 packages | 0 |
| routes | 1074 | 110 | 79 | 0 |

`operon registry check --scope packages` returns `changed [] errors []`.
No operator, Reader or route declaration changed in this release.

## Unit tests

| Module | Tests | Result |
| --- | ---: | --- |
| `tests/test_remote_cleanup.py` | 3 | pass |
| `tests/test_remote_provision.py` | 20 | pass |
| `tests/test_remote_upgrade_retire.py` | 1 | pass |

Total 24 passed. The new test is
`test_retire_script_survives_a_pool_found_only_through_proc`: it spawns a
process whose command line contains `operon.managed_pool` and the fake home
(no `instance.json`), plus a process carrying `--workspace <ws>` and
`operon.remote.server` with its working directory under the fake home, then runs
the retire script text with `sys.executable -I`. It asserts exit code 0 and a
`BP_RETIRE_RESULT` line.

## Reproduction evidence

Running the same fixture against the retire script from the previous commit
(`e0aab4e26`) exits with code 1 and prints:

    TypeError: expected str, bytes or os.PathLike object, not NoneType

The traceback points at the control-socket `os.path.join(directory, ...)` line,
because the pool loop had set `directory` to `None`. The fixed script exits 0.

## Release artifacts

| Artifact | Bytes | sha256 |
| --- | ---: | --- |
| Operon_Setup-5.9.1.exe | see SHA256SUMS-5.9.1.txt | see file |
| Operon-Studio-v5.9.1-Windows-x64.zip | see SHA256SUMS-5.9.1.txt | see file |
| Operon-5.9.1-Server.zip | see SHA256SUMS-5.9.1.txt | see file |
| operon_studio-5.9.1-py3-none-any.whl | see SHA256SUMS-5.9.1.txt | see file |

The library assets are unchanged from 5.9.0: `operon-library-main-v2.0.0.operon-library.zip`,
`operon_builtin_library-2.0.0-py3-none-any.whl` and `Operon-Routes-v2.0.0.zip`.

The 5.9.1 acceptance script checks payload manifest metadata (version,
product, source commit, runtime mode, file set and sampled hashes), both
release documents, the runtime receipt, the packaged library descriptor counts
(1074 operators / 110 Readers, `FileReader` present, `msa_trim` form output),
the Server archive and both wheels. It must print `problems: []`.

## Limitations

- No remote server was upgraded for this release.
- The local Linux test box has no installed environments, so environment-gated
  operator tests are not part of this patch's evidence; the 5.9.0 test report
  records that limitation for the port-rule change.
