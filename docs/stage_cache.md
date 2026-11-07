# Verified stage reuse

Stage reuse is opt-in: set `runtime.execution.cache` to `"verified"`. Frozen
parameter JSON, the ordinary worker, memory planning, emergency spill and
transfer formats are preserved. Ineligible stages run normally and explain the
cache miss in `cache_decisions`.

## Author declaration

Every operator **and Reader** participating in a stage must declare this optional
contract in the existing v3 `definition.resources` object:

```python
"resources": {
    "memory_modes": ["full"],
    "supports_cuda": False,
    "cache": {
        "deterministic": True,
        "stochastic": False,
        "side_effects": "none"
    }
}
```

Build/install validates this optional v3/3.7 resource declaration. Old operators
remain valid; missing declarations disable cache reuse. Booleans are strict.
Stochastic code must also declare `"seed_parameters": ["seed"]`, with names
present in its parameter schema and non-null frozen values during execution.
The author must ensure those seeds control every random source.

Use `"side_effects": "external"` for code modifying databases, sending messages,
depending on mutable network services, or publishing outside managed output.
Such code is ineligible. Managed result files belong to the cached artifact.
All input content must enter through declared sources or frozen parameters;
hidden files, ambient variables and undeclared tools cannot be assumed stable.

## Identity and verification

The key includes input file contents, frozen values, execution semantics,
implementation locks, application version, package generation and cache
contracts. Presentation coordinates and per-request IDs are excluded.

The environment probe runs in the **selected scientific interpreter**, with the
worker's installed provider paths. It records interpreter/prefix, installed
distribution versions and actual file hashes for the declared dependency
closure, without importing scientific code. Unknown environments refuse reuse.
Isolated targets, R, external tools and optional dependency extras currently
remain ineligible. Probing is
limited to otherwise eligible cached stages; it is not a startup scan.

Reuse verifies the artifact file set, sizes and content digests. Before inserting
new output, input/environment identity is checked again; changes during the run
prevent insertion. Keep inputs stable while running. The maintenance gate blocks
supported Operon repair/install operations during interpreter use, but cannot
prevent direct modification by other programs.

## Shared pool behavior

The execution service retains placement, uploads, stage boundaries and result
exchange. Each stage submits a stable request key to the pool's sole allocator.
Hits avoid starting a new worker. Pool-client mode requires shared workspace
storage on the same host; use the SSH gateway co-located with a remote pool.

Validation covers normal wheel installation of declared Readers/operators,
actual numeric worker output, reuse, changed inputs/parameters, damaged artifacts
and changed environment metadata or same-version dependency code files. A declaration is an author promise, not a
proof of scientific determinism or arbitrary external-tool reproducibility.
