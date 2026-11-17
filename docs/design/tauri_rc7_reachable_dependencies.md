# RC7: selected dependency traversal with complete resource preservation

RC6 copied each selected provider namespace and then traversed every copied
Python file. That incorrectly made unrelated optional modules mandatory, even
when the workflow never imported them. The installed plot provider exposed this
with an unused initializer referencing an absent vendored module.

RC7 separates two sets:

- Retained payload: the existing selected provider namespaces and resources,
  unchanged and hash-verified. No library code or provider pins are rewritten.
- Dependency frontier: the selected descriptors' exact entry-point files and
  the explicit runtime kernel. Traversal follows their imports transitively,
  including files already retained in the payload and package initializers.

Unused payload files are not parsed to invent additional dependencies. A missing
module reached from a selected entry or package initializer still fails before
launch. This is generic behavior, without module-name exceptions. Relative and
literal dynamic imports retain their existing support. Computed dynamic imports
and external resources retain existing explicit contracts; this is file/module
reachability, not function-level execution or branch/semantic inference.

The shared collector still feeds both canvas execution and portable export.
Closure ABI `operon-code-closure-v3` creates a distinct RunPlan identity for fresh
preparations. Old accepted runs/caches stay immutable. Payload hashing remains
conservative: retained resources participate even if unused by a particular run.
Scientific memory management, parameter JSON, dependency isolation and RC6's
validated cancellation cleanup are unchanged.

Regression coverage uses arbitrary provider/helper names: unused broken and
non-Python payload preservation; real selected transitive and initializer errors;
selected-entry inventory with unchanged pins; CSV Reader collection; existing
canvas preparation/export checks. Actual RC7 installed-machine fresh saved
CSV/PCA run and relocated scientific export remain separate acceptance gates.
