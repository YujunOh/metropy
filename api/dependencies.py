"""
SeatScoreEngine 싱글턴 관리.
앱 시작 시 한 번 로드하고, 모든 요청에서 재사용한다.
"""
import sys
import threading
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.seatscore import SeatScoreEngine


class EngineRegistry:
    def __init__(self):
        self.engine: SeatScoreEngine | None = None
        self.engine_lock = threading.RLock()  # Protects engine state mutations (calibrate, stability, sensitivity)

    def load(self):
        data_dir = PROJECT_ROOT / "data" / "processed"
        raw_dir = PROJECT_ROOT / "data" / "raw"
        self.engine = SeatScoreEngine(
            data_dir=str(data_dir),
            raw_dir=str(raw_dir),
        )
        self.engine.load_all()

    def get_engine(self) -> SeatScoreEngine:
        if self.engine is None:
            raise RuntimeError("Engine not loaded")
        return self.engine

    def auto_direction(self, boarding: str, destination: str) -> str:
        """순환선에서 짧은 방향을 자동 판별한다."""
        engine = self.get_engine()
        stations = engine.station_order
        # 본선만 사용 (지선 제외: 용답~까치산은 index 44 이후)
        main_stations = stations[:44]  # 시청~시청(순환)

        try:
            b_idx = main_stations.index(boarding)
            d_idx = main_stations.index(destination)
        except ValueError:
            return "내선"  # 못 찾으면 기본값

        n = len(main_stations) - 1  # 마지막은 시청 중복
        clockwise = (d_idx - b_idx) % n
        counter = (b_idx - d_idx) % n

        return "내선" if clockwise <= counter else "외선"


registry = EngineRegistry()
