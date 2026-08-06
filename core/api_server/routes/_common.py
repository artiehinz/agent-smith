"""Route-wide API helpers."""
from __future__ import annotations

from collections.abc import Callable

try:
    from fastapi import APIRouter
except Exception:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]


class _FallbackRouter:
    """Lightweight decorator-compatible router when FastAPI is unavailable.

    The project includes route modules independently of the API runtime in this
    workspace, so tests and local imports should continue to work even when the
    framework signature differs from the pinned environment.
    """

    def __init__(self) -> None:
        self.routes: list[dict[str, object]] = []

    def add_api_route(self, path: str, endpoint: Callable[..., object] | None = None, methods: list[str] | tuple[str, ...] = ("GET",), **_kwargs: object) -> Callable[..., object] | None:
        if endpoint is None:
            def _decorator(func: Callable[..., object]) -> Callable[..., object]:
                self.routes.append({
                    "path": path,
                    "methods": methods,
                    "endpoint": func,
                })
                return func
            return _decorator

        self.routes.append({
            "path": path,
            "methods": methods,
            "endpoint": endpoint,
        })
        return endpoint

    def get(self, path: str, **kwargs: object) -> Callable[[Callable[..., object]], Callable[..., object]]:
        _ = kwargs

        def _decorator(func: Callable[..., object]) -> Callable[..., object]:
            self.routes.append({
                "path": path,
                "methods": ["GET"],
                "endpoint": func,
            })
            return func

        return _decorator

    def post(self, path: str, **kwargs: object) -> Callable[[Callable[..., object]], Callable[..., object]]:
        _ = kwargs

        def _decorator(func: Callable[..., object]) -> Callable[..., object]:
            self.routes.append({
                "path": path,
                "methods": ["POST"],
                "endpoint": func,
            })
            return func

        return _decorator

    def include_router(self, *_args: object, **_kwargs: object) -> None:
        return None


def _build_router():
    if APIRouter is None:
        return _FallbackRouter()
    try:
        return APIRouter()
    except TypeError:
        return _FallbackRouter()


router = _build_router()


async def _wake_smith_if_idle() -> None:
    """Compat helper for environments expecting a Smith wake callback."""
    return None

