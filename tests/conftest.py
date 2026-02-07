# -*- coding: utf-8 -*-
"""
pytest 설정 파일
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def test_client():
    """FastAPI 테스트 클라이언트 픽스처"""
    from web.app import app
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def seatscore_engine():
    """SeatScoreEngine 픽스처"""
    from src.seatscore import SeatScoreEngine

    engine = SeatScoreEngine(
        data_dir=str(PROJECT_ROOT / "data_processed"),
        raw_dir=str(PROJECT_ROOT / "data_raw"),
    )
    engine.load_all()
    return engine


@pytest.fixture
def sample_route():
    """샘플 경로 데이터"""
    return {
        "boarding": "강남",
        "destination": "시청",
        "hour": 8,
        "direction": "내선"
    }


@pytest.fixture
def sample_stations():
    """샘플 역 목록"""
    return ["강남", "역삼", "선릉", "삼성", "종합운동장", "신천", "잠실", "시청"]
