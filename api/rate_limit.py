# -*- coding: utf-8 -*-
"""요청 속도 제한 모듈"""
import time
from typing import Dict, List


class InMemoryBackend:
    """인메모리 슬라이딩 윈도우 Rate Limiter"""

    def __init__(self) -> None:
        self._requests: Dict[str, List[float]] = {}

    async def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        if key not in self._requests:
            self._requests[key] = []

        # 윈도우 밖의 요청 제거
        self._requests[key] = [ts for ts in self._requests[key] if now - ts < window]

        if len(self._requests[key]) >= limit:
            return True

        self._requests[key].append(now)
        return False


def create_backend() -> InMemoryBackend:
    """Rate limit backend 반환"""
    return InMemoryBackend()
