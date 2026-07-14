from __future__ import annotations


class GcaError(Exception):
    """Base exception for expected application failures."""


class NotARepositoryError(GcaError):
    """Raised when a path cannot be resolved to a Git repository."""


class WorkspaceError(GcaError):
    """Raised when the repository-local workspace cannot be used safely."""


class ConfigurationError(GcaError):
    """Raised when project configuration is invalid."""


class IdentityResolutionError(GcaError):
    """Raised when an analysis target cannot be resolved to one confirmed person."""


class ReportError(GcaError):
    """Raised when a persisted analysis report cannot be loaded or rendered."""


class LlmProviderError(GcaError):
    """Base error for provider transport and service failures."""

    def __init__(self, message: str, *, code: str = "PROVIDER_ERROR", retriable: bool = False):
        super().__init__(message)
        self.code = code
        self.retriable = retriable
        self.attempts = 0


class LlmTimeoutError(LlmProviderError):
    def __init__(self, message: str = "LLM provider request timed out") -> None:
        super().__init__(message, code="TIMEOUT", retriable=True)


class LlmRateLimitError(LlmProviderError):
    def __init__(self, message: str = "LLM provider rate limit exceeded") -> None:
        super().__init__(message, code="RATE_LIMIT", retriable=True)


class LlmAuthenticationError(LlmProviderError):
    def __init__(self, message: str = "LLM provider authentication failed") -> None:
        super().__init__(message, code="AUTHENTICATION", retriable=False)


class LlmOutputError(LlmProviderError):
    def __init__(self, message: str = "LLM provider returned invalid structured output") -> None:
        super().__init__(message, code="INVALID_OUTPUT", retriable=True)
