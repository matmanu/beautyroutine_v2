"""Persistenza: un'unica tabella `users` con profilo e piano in colonne JSON."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

from .config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # profilo = {tools, days, minutes, skin_type, concerns, actives, safety}
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reminder_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tz: Mapped[str] = mapped_column(String(64), default=settings.default_tz)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_user(chat_id: int) -> User | None:
    async with SessionLocal() as session:
        return await session.get(User, chat_id)


async def upsert_user(chat_id: int, **fields: Any) -> User:
    async with SessionLocal() as session:
        user = await session.get(User, chat_id)
        if user is None:
            user = User(chat_id=chat_id, profile={}, tz=settings.default_tz)
            session.add(user)
        for key, value in fields.items():
            setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return user


async def all_users_with_reminder() -> list[User]:
    async with SessionLocal() as session:
        result = await session.scalars(
            select(User).where(User.reminder_hour.is_not(None))
        )
        return list(result)


async def delete_user(chat_id: int) -> None:
    async with SessionLocal() as session:
        user = await session.get(User, chat_id)
        if user is not None:
            await session.delete(user)
            await session.commit()
