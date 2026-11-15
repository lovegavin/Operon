"""Compatibility import for the shared metadata-only planning implementation."""
import sys
from operon.planning import parameters as _implementation
sys.modules[__name__] = _implementation
