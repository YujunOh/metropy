"""
Rate limiting backends for Metropy API.

- InMemoryBackend (기본): 단일 워커 배포용, 별도 의존성 없음
- RedisBackend (선택): 다중 워커 배포용, REDIS_URL 환경변수 설정 시 활성화
"""
import os
import time
import logging
from typing import Dict, List, Protocol

logger = logging.getLogger(__name__)


class RateLimitBackend(Protocol):
    """Rate limit backend protocol."""

    async def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        """
        key에 대한 요청이 window(초) 내에 limit을 초과했는지 확인.
        초과 시 True 반환 (요청 차단).
        """
        ...


class InMemoryBackend:
    """
    인메모리 슬라이딩 윈도우 Rate Limiter.
    단일 워커에서만 정확하게 동작하며, 주기적으로 오래된 항목을 정리한다.
    """

    def __init__(self) -> None:
        self._requests: Dict[str, List[float]] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # 1시간마다 전체 정리

    def _periodic_cleanup(self, now: float) -> None:
        """오래된 IP 항목을 제거하여 메모리 누수를 방지한다."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        stale_keys = [
            k for k, timestamps in self._requests.items()
            if not timestamps or now - max(timestamps) > 120
        ]
        for k in stale_keys:
            del self._requests[k]

    async def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        self._periodic_cleanup(now)

        if key not in self._requests:
            self._requests[key] = []

        # 윈도우 밖의 요청 제거 (슬라이딩 윈도우)
        self._requests[key] = [
            ts for ts in self._requests[key] if now - ts < window
        ]

        if len(self._requests[key]) >= limit:
            return True

        self._requests[key].append(now)
        return False


class RedisBackend:
    """
    Redis 기반 슬라이딩 윈도우 Rate Limiter.
    Sorted Set을 사용하여 다중 워커 환경에서도 정확하게 동작한다.
    REDIS_URL 환경변수가 설정되고 redis 패키지가 설치된 경우에만 활성화.
    """

    def __init__(self, redis_url: str) -> None:
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            sanitized = redis_url.split("@")[-1] if "@" in redis_url else redis_url
            logger.info("Rate limiting: Redis backend 활성화 (%s)", sanitized)
        except ImportError:
            raise ImportError(
                "Redis rate limiting에 redis 패키지가 필요합니다. "
                "설치: pip install 'redis>=5.0.0,<6.0'"
            )

    async def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        redis_key = f"metropy:rate_limit:{key}"

        pipe = self._redis.pipeline()
        # 윈도우 밖의 항목 제거
        pipe.zremrangebyscore(redis_key, 0, now - window)
        # 현재 윈도우 내 요청 수 조회
        pipe.zcard(redis_key)
        # 현재 요청 추가 (score=timestamp, member=unique id)
        pipe.zadd(redis_key, {f"{now}:{id(pipe)}": now})
        # TTL 설정 (윈도우 + 여유분)
        pipe.expire(redis_key, window + 10)

        results = await pipe.execute()
        current_count: int = results[1]  # zcard 결과

        if current_count >= limit:
            # 초과 시 방금 추가한 항목 제거
            pipe2 = self._redis.pipeline()
            pipe2.zremrangebyscore(redis_key, now - 0.001, now + 0.001)
            await pipe2.execute()
            return True

        return False


def create_backend() -> RateLimitBackend:
    """
    Rate limit backend 팩토리.
    REDIS_URL 환경변수가 설정되면 Redis backend를, 아니면 인메모리 backend를 반환한다.
    """
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            backend = RedisBackend(redis_url)
            return backend  # type: ignore[return-value]
        except ImportError:
            logger.warning(
                "REDIS_URL이 설정되었으나 redis 패키지가 없습니다. "
                "인메모리 backend로 전환합니다."
            )
    return InMemoryBackend()  # type: ignore[return-value]