"""Un'unica interfaccia, due implementazioni. Si cambia provider con LLM_PROVIDER."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from ..config import settings

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> dict[str, Any]:
    """I modelli a volte incorniciano il JSON o aggiungono una riga di preambolo.
    Puliamo prima di parsare, e in ultima istanza isoliamo il primo oggetto graffo."""
    cleaned = _FENCE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(cleaned[start : end + 1])


class LLMClient(ABC):
    @abstractmethod
    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        ...


class AnthropicClient(LLMClient):
    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return extract_json(text)


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=8000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return extract_json(response.choices[0].message.content or "")


def get_client() -> LLMClient:
    if settings.llm_provider == "openai":
        return OpenAIClient()
    return AnthropicClient()
