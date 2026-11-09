"""Talks to an OpenAI-compatible endpoint (a LiteLLM proxy in production) over raw HTTP."""
import os

import httpx

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:4000/v1")
API_KEY = os.environ.get("LLM_API_KEY", "")


def chat(messages: list[dict], model: str = "gpt-4.1-mini") -> str:
    r = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": model, "messages": messages},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def embed(text: str, model: str = "text-embedding-3-small") -> list[float]:
    r = httpx.post(
        f"{BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": model, "input": text},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]
