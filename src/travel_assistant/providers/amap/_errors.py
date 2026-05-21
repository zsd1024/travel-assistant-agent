"""Typed Amap errors. Providers handle these uniformly."""


class AmapError(RuntimeError):
    """Base class for all Amap-related errors."""


class AmapTransientError(AmapError):
    """A transient upstream failure (network / 5xx) after retries are exhausted."""


class AmapApiError(AmapError):
    """A non-retryable upstream error (4xx, or Amap status != '1')."""


class AmapNotFoundError(AmapError):
    """An expected entity (e.g., geocode) was not found in Amap's response."""
