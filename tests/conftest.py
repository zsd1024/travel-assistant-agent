import pytest


@pytest.fixture(autouse=True)
def _force_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_FAKE_MODEL", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("AMAP_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _block_live_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defense in depth: any outbound httpx call not intercepted by respx
    raises a clear error. respx tests install their own MockTransport which
    overrides this guard for the duration of the respx scope."""
    import httpx

    def _deny(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError(
            "Live HTTP request blocked in tests. Use respx mocks or fix the "
            f"test. URL: {request.url!s}"
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _deny)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _deny)
