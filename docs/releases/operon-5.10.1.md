# Operon 5.10.1

Fix release for 5.10.0: environment packages that a tool needs corrected in
place are now declared in the operator library instead of being hand-edited on
the server.

## Declarative site-packages patches

`environments.json` entries may carry a `patches` list:

```json
"patches": [
  {
    "path": "simtk/openmm/app/__init__.py",
    "marker": "__path__ = list(_openmm_app.__path__)",
    "content": "import openmm.app as _openmm_app\n__path__ = list(_openmm_app.__path__)\n"
  }
]
```

The installer resolves the environment's site-packages trees, appends (or
writes) the declared content once, records the applied paths in the environment
receipt, and the repair path applies missing patches to an environment that is
already installed. Paths are validated: they must stay inside site-packages and
use `append` or `write` mode.

AlphaFold-2 now declares the OpenMM 8 compatibility line so
`simtk.openmm.app.internal` imports on a freshly built environment. Previously
that shim existed only as a manual edit on the test server and vanished on
rebuild.

## Library

Operator library 2.1.1 carries the declaration. App 5.10.1 ships it in the
bundled seed, so a managed server installed from the application build applies
the same patch.
### Server installs report progress instead of blocking

The install / upgrade request now starts a background worker and returns at once;
the desktop panel streams `/api/remote/{id}/setup` while the upgrade runs, so a
long SSH install can no longer abort the window's fetch or leave the log empty.
Host-key prompts still reach the panel (fingerprint carried by the setup status),
and MCP `operon_remote_install` + `operon_remote_install_status` follow the same
contract they already documented.

