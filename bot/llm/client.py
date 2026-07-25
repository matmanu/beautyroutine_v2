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

    @abstractmethod
    async def complete_text(
        self, system: str, messages: list[dict[str, str]]
    ) -> str:
        """Risposta in linguaggio naturale, con storico della conversazione."""
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

    async def complete_text(
        self, system: str, messages: list[dict[str, str]]
    ) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1500,
            system=system,
            messages=messages,
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def _create(
        self, messages: list[dict[str, str]], *, json_mode: bool, budget: int
    ):
        """I modelli recenti (serie o / GPT-5) rifiutano `max_tokens` e vogliono
        `max_completion_tokens`; i più vecchi fanno l'esatto contrario.
        Proviamo il nome nuovo e ripieghiamo sul vecchio solo se serve."""
        from openai import BadRequestError

        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            return await self._client.chat.completions.create(
                **kwargs, max_completion_tokens=budget
            )
        except BadRequestError as exc:
            if "max_completion_tokens" not in str(exc):
                raise
            return await self._client.chat.completions.create(
                **kwargs, max_tokens=budget
            )

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        # Budget generoso: sui modelli di reasoning il limite comprende anche
        # i token di ragionamento, che non finiscono nell'output.
        response = await self._create(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            json_mode=True,
            budget=16000,
        )
        return extract_json(response.choices[0].message.content or "")

    async def complete_text(
        self, system: str, messages: list[dict[str, str]]
    ) -> str:
        response = await self._create(
            [{"role": "system", "content": system}, *messages],
            json_mode=False,
            budget=4000,
        )
        return (response.choices[0].message.content or "").strip()


def get_client() -> LLMClient:
    if settings.llm_provider == "openai":
        return OpenAIClient()
    return AnthropicClient()
