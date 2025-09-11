import os
import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("BOT_USERNAME", "test_bot")
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from web_app.web_main import app, get_session


@pytest.mark.asyncio
async def test_root_guest_redirect(session, sample_data):
    salon, _, _ = sample_data

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    headers = {"User-Agent": "Mozilla/5.0"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as ac:
        resp = await ac.get("/", headers=headers)
    app.dependency_overrides.clear()
    assert resp.status_code == 307
    assert resp.headers["location"] == f"/{salon.slug}/"
    assert "guest_id" in resp.cookies


@pytest.mark.asyncio
async def test_index_guest_name(session, sample_data):
    salon, _, _ = sample_data

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    headers = {"User-Agent": "Mozilla/5.0"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/{salon.slug}/", headers=headers)
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "Гость" in resp.text
    assert "guest_id" in resp.cookies
