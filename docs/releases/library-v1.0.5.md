# Operator library main 1.0.5

Released with Operon Studio 5.6.6.

## Changed

- The ProteinMPNN, AntiFold, LigandMPNN and OpenFold steps resolve their
  interpreter from the registered environment before falling back to the host
  interpreter, so they no longer fail on Windows with `WinError 193`.
- Dependency metadata for the ProteinMPNN family records the interpreter
  requirement.

## Contents

- 7 packages, 1,177 descriptors: 1,069 operators and 108 readers.
- 18 environments, 1,177 operator-to-environment assignments.
- 16 resources with 16 official units.
