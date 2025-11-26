from types import SimpleNamespace

import pytest

from utils import telegraph


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class DummyClient:
    def __init__(self, response, calls):
        self.response = response
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def post(self, url, data):
        self.calls.append((url, data))
        return self.response


@pytest.mark.asyncio
async def test_create_telegraph_page_success(monkeypatch):
    calls: list[tuple[str, dict]] = []
    payload = {"ok": True, "result": {"url": "https://telegra.ph/page"}}
    dummy_response = DummyResponse(payload)

    def client_factory(**_: dict):
        return DummyClient(dummy_response, calls)

    dummy_httpx = SimpleNamespace(AsyncClient=client_factory)
    monkeypatch.setenv("TELEGRAPH_ACCESS_TOKEN", "token")
    monkeypatch.setattr(telegraph, "httpx", dummy_httpx)

    url = await telegraph.create_telegraph_page("Title", "Content")

    assert url == payload["result"]["url"]
    assert calls
    sent_url, data = calls[0]
    assert sent_url.endswith("createPage")
    assert data["access_token"] == "token"


@pytest.mark.asyncio
async def test_create_telegraph_page_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAPH_ACCESS_TOKEN", raising=False)
    url = await telegraph.create_telegraph_page("Title", "Content")

    assert url is None
