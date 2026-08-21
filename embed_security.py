from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

DEFAULT_ALLOWED_EMBED_ORIGINS = (
    "http://127.0.0.1:9000",
    "http://localhost:9000",
)


def allowed_embed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_EMBED_ORIGINS", "").strip()
    candidates = raw.split(",") if raw else list(DEFAULT_ALLOWED_EMBED_ORIGINS)

    origins: list[str] = []
    for candidate in candidates:
        origin = candidate.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(
                "ALLOWED_EMBED_ORIGINS must contain comma-separated http(s) origins "
                "such as https://shop.example.com"
            )
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise RuntimeError("Allowed embed origins must not include paths, queries, or fragments.")
        origins.append(origin)

    if not origins:
        raise RuntimeError("At least one allowed embed origin is required.")
    if "*" in origins:
        raise RuntimeError("Wildcard embed origins are not allowed.")
    return origins


def public_embed_only() -> bool:
    return os.getenv("PUBLIC_EMBED_ONLY", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def require_allowed_origin(request: Request) -> str:
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if not origin or origin not in allowed_embed_origins():
        raise HTTPException(status_code=403, detail="This website origin is not allowed to use the embed API.")
    return origin


def request_client_key(request: Request, origin: str) -> str:
    # Render and most managed hosts forward the original client IP. This is only
    # Minimum embed protection; distributed/stronger abuse controls are deferred.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        client_ip = forwarded.split(",", 1)[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    return f"{origin}|{client_ip}"


class InMemoryRateLimiter:
    """Small per-process sliding-window limiter for the public embed validation."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = max(1, limit)
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                raise HTTPException(
                    status_code=429,
                    detail="Too many chat requests. Please try again shortly.",
                    headers={"Retry-After": str(self.window_seconds)},
                )
            events.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


def configured_rate_limit() -> int:
    raw = os.getenv("EMBED_RATE_LIMIT_PER_MINUTE", "20").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("EMBED_RATE_LIMIT_PER_MINUTE must be an integer.") from exc
    if value < 1:
        raise RuntimeError("EMBED_RATE_LIMIT_PER_MINUTE must be at least 1.")
    return value


embed_rate_limiter = InMemoryRateLimiter(configured_rate_limit())
