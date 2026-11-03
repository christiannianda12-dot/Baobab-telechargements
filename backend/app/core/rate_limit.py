"""Limiteur de requêtes en mémoire (fenêtre glissante, par IP).

Suffisant en développement / instance unique. En production multi-instances,
le remplacer par un limiteur adossé à Redis ou au reverse proxy.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_hits: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    _hits.clear()


def auth_rate_limit(request: Request) -> None:
    limit = get_settings().auth_rate_limit_per_minute
    key = f"{request.url.path}:{request.client.host if request.client else 'unknown'}"
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives, réessayez plus tard."
        )
    q.append(now)
