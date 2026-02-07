# -*- coding: utf-8 -*-
"""
캐시 관리 모듈
- /recommend 엔드포인트용 LRU 캐시 (TTL 5분, 최대 100개)
- calibrate 변경 시 캐시 무효화
- Thread-safe: RLock으로 동시 접근 보호
"""
import threading
import time
from collections import OrderedDict
from typing import Optional, Dict, Any, Tuple


class RecommendCache:
    """
    /recommend 엔드포인트용 LRU 캐시 (thread-safe)
    - 캐시 키: (boarding, destination, hour, direction, dow) 튜플
    - TTL: 5분 (300초)
    - 최대 100개 항목
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[Tuple, Dict[str, Any]] = OrderedDict()  # {key: {value, timestamp}}
        self._lock = threading.RLock()
    
    def _cleanup_expired(self):
        """만료된 항목 제거 (caller must hold lock)"""
        now = time.time()
        expired_keys = [
            key for key, data in self.cache.items()
            if now - data["timestamp"] > self.ttl_seconds
        ]
        for key in expired_keys:
            del self.cache[key]
    
    def get(self, boarding: str, destination: str, hour: int, direction: str, dow: Optional[str]) -> Optional[Dict]:
        """캐시에서 값 조회"""
        with self._lock:
            self._cleanup_expired()
            key = (boarding, destination, hour, direction, dow)
            
            if key in self.cache:
                # LRU 업데이트: 최근 사용으로 이동
                self.cache.move_to_end(key)
                return self.cache[key]["value"]
            return None
    
    def set(self, boarding: str, destination: str, hour: int, direction: str, dow: Optional[str], value: Dict):
        """캐시에 값 저장"""
        with self._lock:
            self._cleanup_expired()
            key = (boarding, destination, hour, direction, dow)
            
            # 이미 존재하면 최근 사용으로 이동
            if key in self.cache:
                self.cache.move_to_end(key)
            
            # 크기 초과 시 가장 오래된 항목 제거
            if len(self.cache) >= self.max_size and key not in self.cache:
                self.cache.popitem(last=False)
            
            # 새 항목 추가
            self.cache[key] = {
                "value": value,
                "timestamp": time.time()
            }
    
    def invalidate(self):
        """전체 캐시 무효화 (calibrate 변경 시 호출)"""
        with self._lock:
            self.cache.clear()


# 전역 캐시 인스턴스
recommend_cache = RecommendCache(max_size=100, ttl_seconds=300)


def invalidate_recommend_cache():
    """calibrate 변경 시 호출되는 함수"""
    recommend_cache.invalidate()
