# Windows foreign-runtime path constraints

Python and native command executables use canonical extended-length Windows
paths. The explicit application path is preserved by the supervisor even when
the executable itself is short but one of its libraries is below a long prefix.

Windows R is different. R 4.4.2 can normalize directory junctions back to their
physical targets, still uses path-limited file operations in parts of startup,
and rejects a temporary directory containing spaces. A short junction spelling
is not sufficient evidence that a moved R environment can execute.

The R adapter therefore validates the physical environment inventory, script,
inputs, outputs and context paths before process creation. Scratch paths also
reserve room for R-generated temporary filenames and must contain no spaces.
An unsupported layout returns `foreign_runtime_path_unsupported`, identifying
the role and directing the user to a short physical work directory and
environment-store location. No data is silently moved; AccessDenied is not
retried as a substitute for a valid layout.

For an exported workflow, choose the work partition explicitly:

```powershell
$work = (Resolve-Path './work').Path
.\run.cmd --work-dir $work --threads 2 --memory 805306368
```

The example is a user-selected path, not a built-in location. The same option
works with `python run.py`. The package may remain in a different directory,
provided any R script and selected input paths also satisfy the runtime's
physical path limits. Results report the actual work directory. Its one
EnvironmentStore remains the source of environment verification and leases;
there is no second unmanaged runtime copy or second capacity authority.

`inputs.canonical.json` retains original references; R's runtime `inputs.json`
uses equivalent ordinary path spellings. Output collection publishes canonical
declared files. Frozen values, environment content identities, full-process
memory reservations and owned-tree cancellation are unchanged.

Automatic short physical work placement would need durable result retention
and explicit user-configurable storage policy. It is not implemented by this
adapter. Do not claim arbitrary long-path Windows R support. The actual
multi-language acceptance test requires `OPERON_ACCEPTANCE_FOREIGN_WORK_ROOT`
in addition to the prepared Python/R/native generations and records its scope.

## Verified development evidence

`verification/backend/languages-z.xml` records **21 passed** on Windows with
actual Python 3.11.15, R 4.4.2 and a compiled native C fixture. The exported
package was moved, launched with clean HOME and empty PATH, and used an
explicitly configured short physical work directory. The Python/R/C/Python
branch join produced 63, reused the completed run with `--resume`, then produced
57 after editing its independent parameter JSON. Immutable payload verification
passed. All eight generation leases and eight capacity leases were released;
generation exits were proven by the Windows Job Object supervisor. The tested
adapter, path validator and executor source bytes match the final working tree.

The failed `languages-y` and earlier alias traces are retained as diagnostic
evidence, not acceptance. No arbitrary long-path Windows R claim follows from
the successful configured-work-directory test.
