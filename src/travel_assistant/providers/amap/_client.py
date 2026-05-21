"""Shared sync HTTP client for the Amap Web Service API.

Responsibilities:
- inject API key + output=JSON
- retry transient (5xx / httpx.HTTPError) up to settings.amap_max_retries
- in-memory LRU cache keyed on (endpoint, sorted non-key params)
- redact the API key in any log line via a single helper
- normalize errors to AmapApiError / AmapTransientError
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from travel_assistant.config import Settings
from travel_assistant.providers.amap._errors import (
    AmapApiError,
    AmapTransientError,
)

_LOG = logging.getLogger("travel_assistant.providers.amap")
_REDACTED = "***"


def _redact_key(text: str, key: str) -> str:
    if not key:
        return text
    return text.replace(key, _REDACTED)


class _RetryableHTTPError(Exception):
    """Internal marker so tenacity retries 5xx + httpx.HTTPError but not 4xx."""


class AmapHttpClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.amap_api_key or ""
        self._base = settings.amap_base_url.rstrip("/")
        self._timeout = settings.amap_request_timeout_s
        self._max_retries = settings.amap_max_retries
        self._cache: OrderedDict[
            tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]
        ] = OrderedDict()
        self._cache_cap = settings.amap_cache_max_entries
        self._client = httpx.Client(timeout=self._timeout)

    # ----- public ---------------------------------------------------------
    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        endpoint = endpoint.lstrip("/")
        cache_key = (
            endpoint,
            tuple(sorted((k, str(v)) for k, v in params.items())),
        )
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            _LOG.debug("amap cache HIT endpoint=%s", endpoint)
            return self._cache[cache_key]

        try:
            data = self._get_with_retry(endpoint, params)
        except RetryError as e:
            raise AmapTransientError(
                f"Amap upstream failed after retries: endpoint={endpoint}"
            ) from e
        except _RetryableHTTPError as e:
            # tenacity reraise=True re-raises the original exception, not RetryError
            raise AmapTransientError(
                f"Amap upstream failed after retries: endpoint={endpoint}"
            ) from e

        # Amap-level errors: status != "1" => non-retryable API error
        status = data.get("status")
        if status != "1":
            info = data.get("info", "")
            infocode = data.get("infocode", "")
            raise AmapApiError(
                f"Amap API error endpoint={endpoint} info={info} infocode={infocode}"
            )

        # cache and return
        self._cache[cache_key] = data
        if len(self._cache) > self._cache_cap:
            self._cache.popitem(last=False)
        _LOG.debug("amap cache MISS endpoint=%s stored", endpoint)
        return data

    # ----- internal -------------------------------------------------------
    def _get_with_retry(
        self, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        attempts = self._max_retries + 1
        decorated = retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.2, max=2.0),
            retry=retry_if_exception_type(_RetryableHTTPError),
            reraise=True,
        )(self._do_get)
        result: dict[str, Any] = decorated(endpoint, params)
        return result

    def _do_get(
        self, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{self._base}/{endpoint}"
        full_params = {**params, "key": self._key, "output": "JSON"}
        try:
            resp = self._client.get(url, params=full_params)
        except httpx.HTTPError as e:
            self._log_with_redaction(
                logging.WARNING,
                "amap http error endpoint=%s url=%s err=%s",
                endpoint,
                url,
                str(e),
            )
            raise _RetryableHTTPError(str(e)) from e

        # Log endpoint + status (redacted URL)
        self._log_with_redaction(
            logging.DEBUG,
            "amap call endpoint=%s status=%s url=%s",
            endpoint,
            resp.status_code,
            _redact_key(str(resp.url), self._key),
        )

        if 500 <= resp.status_code < 600:
            raise _RetryableHTTPError(f"5xx status={resp.status_code}")
        if 400 <= resp.status_code < 500:
            raise AmapApiError(
                f"Amap 4xx endpoint={endpoint} status={resp.status_code}"
            )
        try:
            data: dict[str, Any] = resp.json()
            return data
        except ValueError as e:
            raise AmapApiError(
                f"Amap non-JSON response endpoint={endpoint}"
            ) from e

    def _log_with_redaction(
        self, level: int, fmt: str, *args: Any
    ) -> None:
        if not _LOG.isEnabledFor(level):
            return
        # Redact in pre-formatted message so even raw key in args is scrubbed.
        msg = fmt % args
        _LOG.log(level, _redact_key(msg, self._key))
