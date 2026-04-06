"""Domain exceptions mapped to HTTP by routers or handlers."""


class ImportOverlapError(Exception):
    """Raised when an import would overlap an existing batch scope without replace."""


class ImportValidationError(Exception):
    """Raised when Excel validation fails (whole-file semantics)."""


class NotFoundError(Exception):
    """Raised when a tenant-scoped resource is missing."""
