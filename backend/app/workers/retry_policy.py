"""Which failures are worth retrying, and which are permanent.

Transient errors (network, timeouts, rate limits, provider 5xx) are retried by
Celery with backoff. Permanent errors (schema validation, bad ids, auth) are not:
retrying them only burns time and money.
"""

import httpx

TRANSIENT_HTTPX_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.TransportError,
)
PERMANENT_MARKERS = ("ValidationError", "AuthenticationError", "PermissionDeniedError", "BadRequestError")


def transient_exceptions() -> tuple[type[BaseException], ...]:
    """Exception types Celery may retry, including provider errors when importable."""
    exceptions: list[type[BaseException]] = [TimeoutError, ConnectionError, *TRANSIENT_HTTPX_EXCEPTIONS]
    try:  # openai is a hard dependency through langchain-openai, but keep this defensive
        import openai

        for name in ("APITimeoutError", "APIConnectionError", "RateLimitError", "InternalServerError"):
            candidate = getattr(openai, name, None)
            if isinstance(candidate, type) and issubclass(candidate, BaseException):
                exceptions.append(candidate)
    except Exception:  # noqa: BLE001 - retry policy must never break imports
        pass
    return tuple(exceptions)


def is_transient_error(error: BaseException) -> bool:
    """True when the failure is likely to disappear on a retry."""
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    name = type(error).__name__
    if any(marker in name for marker in PERMANENT_MARKERS):
        return False
    return isinstance(error, transient_exceptions())
