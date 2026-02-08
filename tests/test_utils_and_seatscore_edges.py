# -*- coding: utf-8 -*-
# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
"""utils/seatscore 추가 엣지 테스트"""
from dataclasses import FrozenInstanceError, replace

import pytest

from src.seatscore import SeatScoreParams
from src.utils import normalize_station_name


def test_normalize_station_name_handles_none_and_nan():
    """결측 입력은 빈 문자열로 정규화한다."""
    assert normalize_station_name(None) == ""
    assert normalize_station_name(float("nan")) == ""


def test_normalize_station_name_removes_suffixes_and_spaces():
    """괄호/대괄호 표기와 공백을 제거한다."""
    assert normalize_station_name("강남역(2호선)[환승]") == "강남"
    assert normalize_station_name(" 강남역(2호선) [환승] ") == "강남역"
    assert normalize_station_name("시 청 역") == "시청"


def test_seatscore_params_is_frozen_dataclass():
    """SeatScoreParams는 불변(frozen)이어야 한다."""
    params = SeatScoreParams()
    with pytest.raises(FrozenInstanceError):
        setattr(params, "beta", 0.9)


def test_dataclasses_replace_creates_new_params_instance():
    """replace()는 원본을 보존한 새 파라미터를 만든다."""
    original = SeatScoreParams()
    updated = replace(original, beta=0.9)

    assert original.beta == 0.3
    assert updated.beta == 0.9
    assert updated.gamma == original.gamma


def test_mock_engine_load_all_and_recommend(mock_engine):
    """mock 데이터로 엔진이 로드되고 추천을 생성한다."""
    result = mock_engine.recommend("강남", "시청", 8, "내선")

    assert result["n_intermediate"] > 0
    assert len(result["scores"]) == 10
    assert result["data_quality"]["congestion_30min"] in {"exact", "fallback"}


def test_recommend_invalid_station_returns_empty_intermediates(mock_engine):
    """존재하지 않는 역 입력 시 중간역 목록은 비어야 한다."""
    result = mock_engine.recommend("없는역", "시청", 8, "내선")

    assert result["n_intermediate"] == 0
    assert result["intermediates"] == []


def test_recommend_out_of_range_hour_is_wrapped(mock_engine):
    """시간 범위를 벗어나도 내부 alpha 계산은 모듈러로 동작한다."""
    result = mock_engine.recommend("강남", "시청", 26, "내선")

    assert result["hour"] == 26
    assert result["alpha"] == mock_engine._get_alpha(26)
