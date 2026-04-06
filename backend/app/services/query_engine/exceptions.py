"""NL query domain errors mapped to HTTP in the router."""


class QueryUnsafeError(Exception):
    """Validator rejected the structured plan."""


class QueryTimeoutError(Exception):
    """Execution or LLM exceeded configured bounds."""


class LlmUnavailableError(Exception):
    """Provider missing, error, or non-JSON response."""
