"""Command line entry point for the standalone library builder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from . import manifest
from .build import build_library
from .gate import gate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m operon_library_builder",
        description="Build and verify universal Operon library bundles.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build operon-library-<version>.zip")
    build.add_argument("--source", type=Path, default=Path("library/seed"))
    build.add_argument("--output", type=Path, default=Path("dist"))
    build.add_argument("--version", default="0.0.0")
    build.add_argument("--minimum-application", default="5.0.0")

    verify = subparsers.add_parser("verify", help="check bundle structure and checksums")
    verify.add_argument("--dist", type=Path, required=True)

    gate_parser = subparsers.add_parser("gate", help="fail-closed verification of a bundle")
    gate_parser.add_argument("--dist", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_library(
                args.source,
                args.output,
                version=args.version,
                minimum_application=args.minimum_application,
            )
            size = result.path.stat().st_size
            print(
                f"built {result.path} ({size} bytes, {result.packages} packages, "
                f"{result.descriptors} descriptors)"
            )
        elif args.command == "verify":
            path = manifest.resolve_bundle(args.dist)
            document, descriptors = manifest.verify_entries(manifest.read_entries(path))
            print(
                f"verified {path}: {len(document['packages'])} packages, "
                f"{len(descriptors)} descriptors"
            )
        else:
            path = manifest.resolve_bundle(args.dist)
            for line in gate(args.dist):
                print(f"ok: {line}")
            print(f"gate ok: {path}")
    except (manifest.BundleError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
