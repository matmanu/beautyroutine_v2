"""Genera il piano e lo valida. Se la validazione fallisce, un solo retry
in cui l'errore viene rimandato al modello: quasi sempre basta."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from .domain import TOOL_CONTRAINDICATIONS
from .llm.client import get_client
from .llm.prompts import SYSTEM_PROMPT, build_user_prompt
from .schemas import Plan

logger = logging.getLogger(__name__)


def filter_contraindicated_tools(profile: dict) -> tuple[list[str], list[str]]:
    """Rimuove dagli strumenti quelli incompatibili con i flag di sicurezza.
    Restituisce (strumenti_ammessi, strumenti_esclusi)."""
    flags = set(profile.get("safety", [])) - {"nessuna"}
    allowed, blocked = [], []
    for tool in profile.get("tools", []):
        if TOOL_CONTRAINDICATIONS.get(tool, set()) & flags:
            blocked.append(tool)
        else:
            allowed.append(tool)
    return allowed, blocked


async def generate_plan(profile: dict) -> Plan:
    allowed, blocked = filter_contraindicated_tools(profile)
    safe_profile = {**profile, "tools": allowed}

    client = get_client()
    user_prompt = build_user_prompt(safe_profile)
    if blocked:
        from .domain import TOOLS

        names = ", ".join(TOOLS.get(t, t) for t in blocked)
        user_prompt += (
            f"\n\nNOTA: questi strumenti sono controindicati e vanno esclusi dal piano, "
            f"spiegando brevemente il perché in regole_sicurezza: {names}."
        )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = await client.complete_json(SYSTEM_PROMPT, user_prompt)
            return Plan.model_validate(raw)
        except (ValidationError, ValueError) as exc:
            last_error = exc
            logger.warning("Piano non valido (tentativo %s): %s", attempt + 1, exc)
            user_prompt = (
                f"{user_prompt}\n\nIl tentativo precedente non rispettava lo schema. "
                f"Errore:\n{exc}\n\nRigenera il JSON corretto e completo."
            )

    raise RuntimeError(f"Impossibile generare un piano valido: {last_error}")
