"""Pytest configuration and shared async fixtures (integration tests need Postgres)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _bootstrap_env() -> None:
    """Load `.env` before `app.core.config` is imported (it instantiates Settings at import)."""
    backend = Path(__file__).resolve().parents[1]
    root = backend.parent
    for candidate in (backend / ".env", root / ".env"):
        if candidate.is_file():
            try:
                from dotenv import load_dotenv

                load_dotenv(candidate)
            except ImportError:
                pass
            return


_bootstrap_env()

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402


def _run_alembic_upgrade_head() -> None:
    """Ensure the Postgres used by pytest matches Alembic head (incl. Phase 3 NL schema)."""
    _bootstrap_env()
    backend = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed (integration tests require current schema).\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
            "Check DATABASE_URL and Postgres availability, then re-run."
        )


def pytest_collection_finish(session: pytest.Session) -> None:
    """Before running tests: migrate DB when the session includes integration tests."""
    if session.config.getoption("collectonly", default=False):
        return
    if os.environ.get("PYTEST_SKIP_ALEMBIC_UPGRADE", "").lower() in ("1", "true", "yes"):
        return
    items = getattr(session, "items", None) or []
    if not items:
        return
    has_integration = False
    for item in items:
        p = getattr(item, "path", None)
        if p is None and hasattr(item, "fspath"):
            p = item.fspath
        if p is not None and "integration" in str(p).replace("\\", "/"):
            has_integration = True
            break
    if not has_integration:
        return
    _run_alembic_upgrade_head()


import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """One session per test; all changes rolled back (requires running Postgres)."""
    from app.core.database import engine

    get_settings.cache_clear()
    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with DB override — same rolled-back transaction as db_session."""
    from app.main import app

    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session_with_flush_commit(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncSession, None]:
    """Same rollback sandbox, but `commit()` becomes `flush()` so `run_ingestion` stays testable."""
    async def _commit() -> None:
        await db_session.flush()

    monkeypatch.setattr(db_session, "commit", _commit)
    yield db_session


@pytest_asyncio.fixture
async def async_client_ingest(
    db_session_with_flush_commit: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for ingest E2E — uses session where commit is mapped to flush."""
    from app.main import app

    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session_with_flush_commit

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=120.0) as client:
        yield client
    app.dependency_overrides.clear()
