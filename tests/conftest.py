from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Async test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Mock DB session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_db_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.refresh = AsyncMock()
    return session
# Mock DB session fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session
