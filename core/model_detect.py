"""Model-profile detection helper used by session bootstrap."""

from __future__ import annotations

import os

def _normalize_profile(raw: str | None) -> str | None:
    value = (raw or "").strip().lower()
    if not value:
        return None
    if value in {"quick", "standard", "thorough", "recon"}:
        return value
    return None


def _env_model_value() -> str:
    for key in ("OPENCODE_MODEL", "OLLAMA_MODEL", "MODEL", "SMITH_MODEL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _classify_profile(model_name: str) -> str:
    marker = (model_name or "").lower()
    if not marker:
        return "standard"

    heavy = {"gpt", "claude", "gemini", "o1", "llama-3.1-70b", "llama3-70b", "qwen2.5-14b", "mixtral"}
    lightweight = {"phi", "qwen", "llama-2", "llama2", "gemma", "qwen2", "deepseek-r1-distill"}
    if any(token in marker for token in heavy):
        return "standard"
    if any(token in marker for token in lightweight):
        return "quick"
    return "standard"


def detect_profile(explicit_profile: str | None = None) -> tuple[str, str]:
    """Resolve model profile from explicit input, env, and a simple model-classifier."""
    profile = _normalize_profile(explicit_profile)
    if profile:
        return profile, "explicit_profile"

    override = _normalize_profile(os.environ.get("SMITH_MODEL_PROFILE"))
    if override:
        return override, "SMITH_MODEL_PROFILE"

    model_name = _env_model_value()
    if not model_name:
        return "standard", "default"

    return _classify_profile(model_name), f"auto_detect:{model_name}"
