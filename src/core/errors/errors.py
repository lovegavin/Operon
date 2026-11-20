# src/core/errors/errors.py
"""Exception hierarchy."""

from __future__ import annotations


class OperonError(Exception):
    """Base class for all Operon errors."""

    def __str__(self) -> str:
        if len(self.args) > 1:
            return ": ".join(str(part) for part in self.args if part)
        return super().__str__()


class ValidationError(OperonError):
    """A Form fails its structural check."""


class ReaderError(OperonError):
    """A reader cannot parse the file or the spec."""


class ManifestError(OperonError):
    """The task manifest is malformed."""


class ContextError(OperonError):
    """A form referenced in the context is missing."""


class StepError(OperonError):
    """A step fails its input or execution check."""