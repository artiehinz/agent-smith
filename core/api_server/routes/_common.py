"""Route-wide API helpers."""
from __future__ import annotations

from fastapi import APIRouter


router = APIRouter()


async def _wake_smith_if_idle() -> None:
    """Compat helper for environments expecting a Smith wake callback."""
    return None

