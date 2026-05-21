import pytest


@pytest.fixture(autouse=True)
def _force_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_FAKE_MODEL", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("AMAP_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _block_live_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defense in depth: any outbound httpx call not intercepted by respx
    raises a clear error. respx patches at the httpcore layer (below
    httpx transports), so when a @respx.mock scope is active we must
    pass the request through to the original transport so respx's
    httpcore-level mocks can intercept it. Outside a respx scope, the
    guard fires and raises."""
    import httpx

    original_sync = httpx.HTTPTransport.handle_request
    original_async = httpx.AsyncHTTPTransport.handle_async_request

    def _respx_active() -> bool:
        try:
            from respx.mocks import HTTPCoreMocker
        except ImportError:
            return False
        routers = getattr(HTTPCoreMocker, "routers", None)
        return bool(routers)

    def _deny_sync(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        if _respx_active():
            return original_sync(self, request, *args, **kwargs)
        raise RuntimeError(
            "Live HTTP request blocked in tests. Use respx mocks or fix the "
            f"test. URL: {request.url!s}"
        )

    async def _deny_async(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        if _respx_active():
            return await original_async(self, request, *args, **kwargs)
        raise RuntimeError(
            "Live HTTP request blocked in tests. Use respx mocks or fix the "
            f"test. URL: {request.url!s}"
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _deny_sync)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", _deny_async
    )
