from collections import deque
from time import time

from fastapi import HTTPException, status

_MEMORY_BUCKET: dict[str, deque[float]] = {}


def rate_limit(key: str, limit: int, window_seconds: int) -> None:
    now = time()
    bucket = _MEMORY_BUCKET.setdefault(key, deque())
    while bucket and (now - bucket[0]) > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    bucket.append(now)

