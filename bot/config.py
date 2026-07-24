"""Configurazione centralizzata letta dalle variabili d'ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _normalize_db_url(raw: str) -> str:
    """Railway espone DATABASE_URL in formato sync: lo convertiamo per asyncpg."""
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    llm_provider: str          # "anthropic" | "openai"
    anthropic_api_key: str | None
    anthropic_model: str
    openai_api_key: str | None
    openai_model: str
    database_url: str
    default_tz: str
    allowed_user_ids: frozenset[int]


def _parse_allowlist(raw: str | None) -> frozenset[int]:
    """ALLOWED_USER_IDS=123456789,987654321 — vuoto significa bot aperto a tutti."""
    if not raw or not raw.strip():
        return frozenset()
    ids = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.lstrip("-").isdigit():
            raise RuntimeError(
                f"ALLOWED_USER_IDS contiene un valore non numerico: {chunk!r}"
            )
        ids.add(int(chunk))
    return frozenset(ids)


def load_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Manca la variabile d'ambiente TELEGRAM_BOT_TOKEN")

    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    if provider not in {"anthropic", "openai"}:
        raise RuntimeError("LLM_PROVIDER deve essere 'anthropic' oppure 'openai'")

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    if provider == "anthropic" and not anthropic_key:
        raise RuntimeError("LLM_PROVIDER=anthropic ma manca ANTHROPIC_API_KEY")
    if provider == "openai" and not openai_key:
        raise RuntimeError("LLM_PROVIDER=openai ma manca OPENAI_API_KEY")

    return Settings(
        telegram_token=token,
        llm_provider=provider,
        anthropic_api_key=anthropic_key,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        openai_api_key=openai_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        database_url=_normalize_db_url(
            os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./beauty_bot.db")
        ),
        default_tz=os.getenv("DEFAULT_TZ", "Europe/Rome"),
        allowed_user_ids=_parse_allowlist(os.getenv("ALLOWED_USER_IDS")),
    )


settings = load_settings()
