# -*- coding: utf-8 -*-
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""LRU 캐시 동작 테스트"""
from unittest.mock import patch

from api.cache import RecommendCache


def test_lru_eviction_respects_recent_access():
    """최근 접근한 항목은 유지되고 가장 오래된 항목이 제거된다."""
    cache = RecommendCache(max_size=2, ttl_seconds=300)

    cache.set("강남", "시청", 8, "내선", "MON", {"v": "A"})
    cache.set("역삼", "시청", 8, "내선", "MON", {"v": "B"})

    # 강남 키를 최근 사용으로 갱신
    assert cache.get("강남", "시청", 8, "내선", "MON") == {"v": "A"}

    # 새 항목 추가 시 역삼 키가 제거되어야 함
    cache.set("선릉", "시청", 8, "내선", "MON", {"v": "C"})

    assert cache.get("역삼", "시청", 8, "내선", "MON") is None
    assert cache.get("강남", "시청", 8, "내선", "MON") == {"v": "A"}
    assert cache.get("선릉", "시청", 8, "내선", "MON") == {"v": "C"}


def test_ttl_cleanup_expires_old_entries():
    """TTL 초과 항목은 조회 전에 정리된다."""
    cache = RecommendCache(max_size=3, ttl_seconds=10)

    with patch("api.cache.time.time", side_effect=[100.0, 100.0, 120.1]):
        cache.set("강남", "시청", 8, "내선", "MON", {"ok": True})
        value = cache.get("강남", "시청", 8, "내선", "MON")

    assert value is None
    assert len(cache.cache) == 0


def test_existing_key_update_moves_to_end_and_overwrites_value():
    """기존 키 업데이트 시 OrderedDict 순서와 값이 갱신된다."""
    cache = RecommendCache(max_size=3, ttl_seconds=300)

    cache.set("강남", "시청", 8, "내선", "MON", {"v": 1})
    cache.set("역삼", "시청", 8, "내선", "MON", {"v": 2})
    cache.set("강남", "시청", 8, "내선", "MON", {"v": 3})

    keys = list(cache.cache.keys())
    assert keys[-1] == ("강남", "시청", 8, "내선", "MON")
    assert cache.get("강남", "시청", 8, "내선", "MON") == {"v": 3}
