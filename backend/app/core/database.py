"""Async SQLAlchemy engine, session factory, and tenant context for RLS."""

from __future__ import annotations

import contextvars
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

_tenant_id_var: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "tenant_id",
    default=None,
)
_user_id_var: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "user_id",
    default=None,
)


def set_session_context(*, tenant_id: UUID | None, user_id: UUID | None) -> None:
    """Set RLS context for the current async task (call from auth / dependencies)."""
    _tenant_id_var.set(tenant_id)
    _user_id_var.set(user_id)


def get_session_tenant_id() -> UUID | None:
    return _tenant_id_var.get()


def get_session_user_id() -> UUID | None:
    return _user_id_var.get()


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        str(settings.DATABASE_URL),
        echo=settings.DEBUG,
        pool_pre_ping=True,
    )


engine = _create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def _apply_rls_session_vars(session: AsyncSession) -> None:
    tenant_id = _tenant_id_var.get()
    user_id = _user_id_var.get()
    if tenant_id is not None:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
    if user_id is not None:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )


async def apply_session_rls_vars(session: AsyncSession) -> None:
    """Apply `app.tenant_id` / `app.user_id` from context — use in Celery after `set_session_context`."""
    await _apply_rls_session_vars(session)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session; callers commit/rollback explicitly."""
    async with async_session_factory() as session:
        await _apply_rls_session_vars(session)
        yield session
