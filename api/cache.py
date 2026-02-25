# -*- coding: utf-8 -*-
"""추천 결과 캐시 모듈 (TTL 5분, 최대 100개)"""
import time
from typing import Optional, Dict, Any


class RecommendCache:
    """recommend 엔드포인트 캐시"""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[tuple, Dict[str, Any]] = {}

    def get(self, boarding: str, destination: str, hour: int, direction: str, dow: Optional[str]) -> Optional[Dict]:
        """캐시에서 값 조회"""
        key = (boarding, destination, hour, direction, dow)
        if key in self.cache:
            data = self.cache[key]
            if time.time() - data["timestamp"] <= self.ttl_seconds:
                return data["value"]
            del self.cache[key]
        return None

    def set(self, boarding: str, destination: str, hour: int, direction: str, dow: Optional[str], value: Dict):
        """캐시에 값 저장"""
        key = (boarding, destination, hour, direction, dow)
        if len(self.cache) >= self.max_size:
            self.cache.clear()
        self.cache[key] = {"value": value, "timestamp": time.time()}

    def invalidate(self):
        """전체 캐시 초기화"""
        self.cache.clear()


# 전역 캐시 인스턴스
recommend_cache = RecommendCache(max_size=100, ttl_seconds=300)


def invalidate_recommend_cache():
    """calibrate 변경 시 호출되는 함수"""
    recommend_cache.invalidate()
