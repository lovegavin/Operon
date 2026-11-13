"""Standalone builder for universal Operon library bundles.

The package depends only on the Python standard library and ``operon_sdk``; it
never imports the application package or reads installed Studio state.
"""

from .build import BuildResult, build_library
from .gate import gate

__all__ = ["BuildResult", "build_library", "gate"]
