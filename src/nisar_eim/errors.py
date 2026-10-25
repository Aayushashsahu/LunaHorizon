"""Typed errors with actionable diagnostics.

The application never converts a georeferencing or product-format problem into a
silently degraded image. Every failure carries a machine-readable ``details``
mapping so the CLI, the web API and the tests can report exactly which invariant
was violated.
"""

from __future__ import annotations

from typing import Any


class NisarError(Exception):
    """Base class for all expected, user-actionable errors."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def to_json(self) -> dict[str, Any]:
        return {"error": type(self).__name__, "message": self.message, "details": self.details}

    def render(self) -> str:
        lines = [self.message]
        if self.details:
            width = max(len(str(k)) for k in self.details)
            for key, value in self.details.items():
                lines.append(f"  {str(key).ljust(width)} : {value}")
        return "\n".join(lines)


class ProductFormatError(NisarError):
    """The HDF5 file is not a supported NISAR GUNW product layout."""


class GeoreferencingError(NisarError):
    """The raster cannot be placed on the map without inventing information."""


class AmbiguousGeoreferencingError(GeoreferencingError):
    """More than one candidate grid matches the raster and they disagree."""


class EmptyDataError(NisarError):
    """No valid measurements remain after masking."""


class UnsupportedLayerError(NisarError):
    """A requested layer is not present in this product."""
