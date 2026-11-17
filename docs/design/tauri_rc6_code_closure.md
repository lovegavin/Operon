# RC6: shared provider/application code closure

The RC5 CSV failure was a packaging boundary defect: the pinned Reader imported
an application helper absent from its isolated code directory. Adding one helper
to the kernel list would leave the same defect for the next provider.

RC6 inventories the selected, hash-verified provider code and runtime kernel,
then statically follows local imports across their explicit source roots. It
handles recursive dependencies, package initializers, relative imports, cycles,
from-import attributes and absolute literal importlib imports. Discovery does
not execute operator top-level code or scan installed Python distributions.
Frozen provider files retain their selected source; unowned application modules
resolve from the application. Conflicting provider modules and missing required
local modules fail before worker launch. Source aliases are rejected.

Canvas execution and portable export consume this same discovered inventory.
The code closure ABI and content digest enter the RunPlan identity, so a fresh
preparation cannot reuse the incomplete RC5 code cache. Existing accepted runs
remain immutable. Parameter JSON, operator implementation pins, memory planning,
environment generations and dependency conflict isolation are unchanged.

This is static code dependency collection, not general program inference.
Computed dynamic imports, dynamically selected resources, external tools and
binary dependencies still use their existing explicit resource/environment
contracts. The change does not promise to infer arbitrary runtime behavior.

Regression coverage includes arbitrary helper names, recursive relative imports,
cycles, literal dynamic imports, ambiguity and missing-module refusal, no import
side effects, transitive cache invalidation, and a real unchanged CsvReader
executed from the collected directory with its original pin. Package and remote
acceptance evidence are recorded separately in the RC6 delivery directory.
