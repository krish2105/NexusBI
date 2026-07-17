"""LLM abstraction — Groq (free tier) / Ollama (local) / deterministic.

The project runs with **zero API keys**: when no provider is configured we use a
deterministic engine (template planner/generator/narrator). Configure
``GROQ_API_KEY`` to upgrade to a general hosted model, or ``OLLAMA_BASE_URL`` for
fully-offline inference. The interface is identical, so the agent graph is
provider-agnostic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.config import settings


@dataclass
class LLMResponse:
    text: str
    provider: str


class LLMClient:
    def __init__(self):
        self.provider = self._resolve_provider()

    def _resolve_provider(self) -> str:
        pref = settings.llm_provider
        if pref != "auto":
            return pref
        if settings.groq_api_key:
            return "groq"
        if settings.ollama_base_url:
            return "ollama"
        return "deterministic"

    @property
    def is_llm(self) -> bool:
        return self.provider in ("groq", "ollama")

    def complete(self, system: str, user: str, *, json_mode: bool = False,
                 temperature: float = 0.1) -> LLMResponse:
        if self.provider == "groq":
            return self._groq(system, user, json_mode, temperature)
        if self.provider == "ollama":
            return self._ollama(system, user, json_mode, temperature)
        # deterministic mode never calls .complete(); nodes branch on is_llm.
        raise RuntimeError("complete() called in deterministic mode")

    # -- providers -----------------------------------------------------------
    def _groq(self, system, user, json_mode, temperature) -> LLMResponse:  # pragma: no cover
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=temperature, **kwargs)
        return LLMResponse(resp.choices[0].message.content, "groq")

    def _ollama(self, system, user, json_mode, temperature) -> LLMResponse:  # pragma: no cover
        import urllib.request

        body = json.dumps({
            "model": settings.ollama_model,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
            "format": "json" if json_mode else "",
            "options": {"temperature": temperature},
        }).encode()
        req = urllib.request.Request(
            f"{settings.ollama_base_url}/api/generate", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        return LLMResponse(data.get("response", ""), "ollama")


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
