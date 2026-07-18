"""LLM abstraction — Groq (free tier) / Ollama (local) / deterministic.

The project runs with **zero API keys**: when no provider is configured we use a
deterministic engine (template planner/generator/narrator). Configure
``GROQ_API_KEY`` to upgrade to a general hosted model, or ``OLLAMA_BASE_URL`` for
fully-offline inference. The interface is identical, so the agent graph is
provider-agnostic.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
from dataclasses import dataclass

from app.config import settings

# Per-request Groq key override: a Pro user's BYO key is set here for the duration
# of their query so generation runs on *their* Groq account (their COGS), without
# threading a key through every graph node. Unset -> the shared/deterministic path.
_byo_groq_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "byo_groq_key", default=None)


@contextlib.contextmanager
def use_groq_key(key: str | None):
    """Scope a BYO Groq key to a request. No-op when key is falsy."""
    if not key:
        yield
        return
    token = _byo_groq_key.set(key)
    try:
        yield
    finally:
        _byo_groq_key.reset(token)


@dataclass
class LLMResponse:
    text: str
    provider: str


class LLMClient:
    def __init__(self, groq_key: str | None = None):
        self._groq_key = groq_key or settings.groq_api_key
        self.provider = self._resolve_provider()

    def _resolve_provider(self) -> str:
        pref = settings.llm_provider
        if pref != "auto":
            return pref
        if self._groq_key:
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

        client = Groq(api_key=self._groq_key)
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
    # A per-request BYO key (Pro tier) takes precedence over the shared singleton.
    byo = _byo_groq_key.get()
    if byo:
        return LLMClient(groq_key=byo)
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
