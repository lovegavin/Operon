# Operator library 1.0.4

Library 1.0.4 is the library shipped with Operon Studio 5.6.5.

## Changes

- The library version advances with the application release so that the
  packaged catalog, the route collection and the installer all agree on one
  version string.
- No operator declaration, resource manifest or environment descriptor changed
  relative to 1.0.3; the packaged descriptor count stays at 1,177 with 7
  packages, 108 readers and 16 resources (16 official maintenance units).

## Compatibility

- Minimum application: 5.6.5.
- The packaged library keeps the environment assignment of 1.0.3: 18
  environments, `core` owning the shared runtime operators.
