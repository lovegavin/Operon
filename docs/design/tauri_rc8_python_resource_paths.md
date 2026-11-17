# RC8: shared Python import and resource path boundary

## Cause and scope

RC7 reached the original CSV/PCA/describe/scatter route's environment preparation,
but both fresh execution and complete export failed before starting a worker.
A real dependency resource existed and had the expected digest; its ordinary
Windows path was 261 characters. The original staged Python failed on that path
and succeeded when the same package root used the extended Windows spelling.

An installed interpreter was an inadequate reproduction: its `.pth` loader hook
made the resource readable. Prepared generations intentionally separate the
interpreter from site-packages and therefore do not inherit that hook.

## Implementation

`operon/python_paths.py` is a stdlib-only boundary shared by environment probes,
Python command adapters, isolated workers and the independent export launcher.
It normalizes absolute Windows filesystem search paths, preserving dependency
precedence and relative search semantics. UNC paths use the extended UNC form.
It also aligns already loaded filesystem packages' loader paths, module paths
and spec metadata: changing `sys.path` alone does not fix cached resource roots.
Namespace search objects and custom loaders are retained. It does not monkeypatch
`open`, install a global hook, modify the registry, or enable user site packages.

Probes and independent launchers embed the same helper implementation before
importing application or scientific dependencies. The isolated `-I -S` bootstrap
loads the adjacent helper explicitly, then reads its config and selects the
declared dependency roots. The normal execution boundary delegates to the same
implementation. Temporary probe directories and logs use the existing extended
filesystem I/O helper.

`operon-python-paths-v1` is recorded in preparation identity and builder recipes;
the preparer source hash and embedded probe code participate in existing cache
identity. A previous readiness receipt cannot bypass the changed probe. No old
cache or workflow pin needs manual deletion or repinning. Verification remains
package-level; this does not add repeated dependency tree scans.

No package-specific workaround, dependency version change, operator library
edit, parameter rewrite or memory policy change is included. The RC7 selected
dependency traversal and resource retention are preserved.

## Focused evidence

Eight actual subprocess checks use a private Python 3.11 runtime with its
site-packages startup hooks removed: original failure versus fixed resource read,
cached loader repair, both scientific interpreter probe branches including
relocation, isolated dependency precedence, relative path semantics, real Python
command preparation/execution, and the collected export kernel's startup.
The resource fixture uses the same real jsonschema dependency and an additional
independent synthetic package; the implementation contains neither package name.

The command fixture supplies a binding rather than proving generation creation.
The export startup check exercises `--help`, not a scientific run. These are
focused boundary tests, not substitutes for the original route's fresh numeric
run and relocated complete export on the test computer.

Related regression checks cover environment closure acquisition, literal command
boundaries, portable kernel behavior, probe diagnostics and candidate packaging.
Exact results and extracted-Setup checks accompany the RC8 delivery.

## Limits and acceptance

This is a Python import/resource path fix, not a guarantee that arbitrary native
DLL loaders or R/external programs accept every physical path length. Existing
foreign-runtime validation remains in force. It does not rewrite future arbitrary
path mutations inside user code or change the semantics of unrelated custom
importers. Non-Windows search paths retain their original spelling.

Upgrade only the existing experimental installation. Preserve the original
profile, frozen route, library registration and old failed receipts. Start a
fresh run of `route_4e4b38d40199` v2, then export and relocate the complete bundle;
compare numeric results. Do not retest unchanged cancellation cleanup, full Agent
flows, installer rollback or native host behavior. Do not publish RC8.
