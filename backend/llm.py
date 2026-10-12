"""Groq (GroqCloud) chat call. Key and model name come from the environment."""
import os

import requests

from . import config


class LLMError(RuntimeError):
    pass


def api_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def model_name() -> str:
    return os.getenv("GROQ_MODEL", config.DEFAULT_GROQ_MODEL)


def available() -> bool:
    return bool(api_key())


def chat(messages: list, temperature: float = 0.2, json_mode: bool = False,
         max_tokens: int = 1024) -> str:
    if not available():
        raise LLMError("GROQ_API_KEY is not set")
    payload = {"model": model_name(), "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        r = requests.post(config.GROQ_URL, json=payload, timeout=60,
                          headers={"Authorization": f"Bearer {api_key()}"})
    except requests.RequestException as exc:
        raise LLMError(f"Could not reach Groq: {exc}")
    if r.status_code != 200:
        raise LLMError(f"Groq API error {r.status_code}: {r.text[:200]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"Unexpected Groq response: {exc}")
