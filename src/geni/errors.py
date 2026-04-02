from __future__ import annotations


class GeniError(Exception):
    """Base exception for all geni errors."""

    def __init__(self, message: str, path: str | None = None) -> None:
        self.path = path
        if path:
            message = f"{message} (path: {path})"
        super().__init__(message)


class SchemaValidationError(GeniError):
    """Raised when the target YAML fails schema validation."""


class TemplateError(GeniError):
    """Raised on template loading or rendering failures."""


class GenerationError(GeniError):
    """Raised on generation failures."""


class HelmError(GeniError):
    """Raised on helm-related errors."""


