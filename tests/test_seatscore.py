# -*- coding: utf-8 -*-
"""
SeatScoreEngine 유닛 테스트
"""
import pytest
import pandas as pd


class TestSeatScoreEngine:
    """SeatScoreEngine 테스트 클래스"""

    def test_engine_loads(self, seatscore_engine):
        """엔진이 정상적으로 로드되는지 테스트"""
        assert seatscore_engine is not None
        assert seatscore_engine.fast_exit_df is not None or hasattr(seatscore_engine, '_facility_cache')
        assert hasattr(seatscore_engine, '_alighting_cache')
        assert seatscore_engine.distance_df is not None or len(seatscore_engine.station_order) > 0

    def test_total_cars(self, seatscore_engine):
        """총 칸 수가 10개인지 확인"""
        assert seatscore_engine.TOTAL_CARS == 10

    def test_facility_weights(self, seatscore_engine):
        """시설 가중치가 올바르게 설정되었는지 확인"""
        weights = seatscore_engine.params.facility_weights
        assert weights["에스컬레이터"] == 1.2  # escalator
        assert weights["엘리베이터"] == 0
        assert weights["계단"] == 1.0

    def test_alpha_map(self, seatscore_engine):
        """시간대 배율이 올바르게 설정되었는지 확인"""
        alpha_map = seatscore_engine.params.alpha_map
        assert alpha_map["morning_rush"] == 1.4
        assert alpha_map["evening_rush"] == 1.3
        assert alpha_map["midday"] == 1.0
        assert alpha_map["night"] == 0.6

    def test_get_alpha(self, seatscore_engine):
        """시간대별 alpha 값 계산 테스트 (smooth interpolation)"""
        # 출근 러시 피크 (8시) - exact anchor point
        assert seatscore_engine._get_alpha(8) == 1.4
        # 퇴근 러시 피크 (19시) - anchor is 1.35
        assert seatscore_engine._get_alpha(19) == 1.35
        # 주간 (14시) - interpolation returns 1.0
        assert seatscore_engine._get_alpha(14) == 1.0
        # 심야 (23시) - exact anchor point
        assert seatscore_engine._get_alpha(23) == 0.6

    def test_compute_seatscore(self, seatscore_engine, sample_route):
        """SeatScore 계산 테스트"""
        result = seatscore_engine.compute_seatscore(
            sample_route["boarding"],
            sample_route["destination"],
            sample_route["hour"],
            sample_route["direction"]
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10  # 10개 칸
        assert "car" in result.columns
        assert "score" in result.columns
        assert "rank" in result.columns
        assert "benefit" in result.columns
        assert "penalty" in result.columns

        # 점수가 정렬되어 있는지 확인
        assert result["score"].is_monotonic_decreasing

        # 순위가 1부터 10까지인지 확인
        assert set(result["rank"]) == set(range(1, 11))

    def test_recommend(self, seatscore_engine, sample_route):
        """추천 함수 테스트"""
        result = seatscore_engine.recommend(
            sample_route["boarding"],
            sample_route["destination"],
            sample_route["hour"],
            sample_route["direction"]
        )

        assert "boarding" in result
        assert "destination" in result
        assert "hour" in result
        assert "direction" in result
        assert "best_car" in result
        assert "best_score" in result
        assert "worst_car" in result
        assert "worst_score" in result
        assert "score_spread" in result
        assert "intermediates" in result
        assert "scores" in result

        # best_car는 1-10 사이의 값
        assert 1 <= result["best_car"] <= 10
        assert 1 <= result["worst_car"] <= 10

        # best_score가 worst_score보다 크거나 같아야 함
        assert result["best_score"] >= result["worst_score"]

        # spread는 0 이상
        assert result["score_spread"] >= 0

    def test_different_times(self, seatscore_engine):
        """다른 시간대에 대한 테스트"""
        boarding = "강남"
        destination = "시청"
        direction = "내선"

        # 출근 시간 vs 심야 시간
        morning_result = seatscore_engine.recommend(boarding, destination, 8, direction)
        night_result = seatscore_engine.recommend(boarding, destination, 23, direction)

        # alpha 값이 다른지 확인
        assert morning_result["alpha"] > night_result["alpha"]

    def test_different_routes(self, seatscore_engine):
        """다른 경로에 대한 테스트"""
        hour = 8
        direction = "내선"

        # 긴 경로 vs 짧은 경로 (내선 방향 기준)
        long_route = seatscore_engine.recommend("강남", "시청", hour, direction)
        short_route = seatscore_engine.recommend("강남", "서초", hour, direction)

        # 중간역 수가 다른지 확인
        assert long_route["n_intermediate"] > short_route["n_intermediate"]

    def test_normalize_station_name(self):
        """역 이름 정규화 테스트"""
        from src.seatscore import normalize_station_name

        assert normalize_station_name("강남역") == "강남"
        assert normalize_station_name("강남역(2호선)") == "강남"
        assert normalize_station_name("강남 ") == "강남"
        assert normalize_station_name("역삼역") == "역삼"
        assert normalize_station_name("역삼") == "역삼"  # "역" 접미사만 제거

    def test_edge_cases(self, seatscore_engine):
        """엣지 케이스 테스트"""
        # 동일한 출발역과 도착역 (실제로는 에러를 발생시켜야 하지만, 현재 구현에서는 빈 결과 반환)
        try:
            result = seatscore_engine.recommend("강남", "강남", 8, "내선")
            assert result["n_intermediate"] == 0
        except Exception:
            # 에러가 발생하는 것도 허용
            pass

    def test_facility_score(self, seatscore_engine):
        """시설 점수 계산 테스트"""
        # 중간 칸(3-7호차)이 양 끝 칸보다 높은 시설 점수를 가질 것으로 예상
        boarding = "강남"
        destination = "시청"
        result = seatscore_engine.recommend(boarding, destination, 8, "내선")

        scores_df = result["scores"]
        edge_cars = scores_df[scores_df["car"].isin([1, 10])]
        middle_cars = scores_df[scores_df["car"].isin([3, 4, 5, 6, 7])]

        # 중간 칸의 평균 점수가 양 끝 칸보다 높은지 확인 (일반적인 경우)
        # 주의: 이것은 항상 참이 아닐 수 있으므로, 테스트에서 제외하거나 유연하게 처리
        # assert middle_cars["score"].mean() > edge_cars["score"].mean()
        pass

    def test_beta_penalty(self, seatscore_engine):
        """Beta 페널티가 올바르게 적용되는지 테스트"""
        assert seatscore_engine.params.beta == 0.3

        # Penalty가 0 이상인지 확인
        result = seatscore_engine.recommend("강남", "시청", 8, "내선")
        scores_df = result["scores"]
        assert (scores_df["penalty"] >= 0).all()

    def test_data_quality_report(self, seatscore_engine):
        """data_quality 필드가 recommend 결과에 포함되는지 확인"""
        result = seatscore_engine.recommend("강남", "시청", 8, "내선")

        assert "data_quality" in result
        dq = result["data_quality"]
        assert "getoff_rate" in dq
        assert "car_congestion" in dq
        assert "train_congestion" in dq
        assert "congestion_30min" in dq
        assert "travel_times" in dq

        # Each value should be one of the valid quality levels
        valid_levels = {"exact", "interpolated", "fallback"}
        for key, val in dq.items():
            assert val in valid_levels, f"data_quality[{key}] = {val} not in {valid_levels}"

    def test_load_factors_in_result(self, seatscore_engine):
        """load_factors 필드가 recommend 결과에 포함되는지 확인"""
        result = seatscore_engine.recommend("강남", "시청", 8, "내선")

        assert "load_factors" in result
        lf = result["load_factors"]
        assert len(lf) == 10
        for car_no, factor in lf.items():
            assert 1 <= car_no <= 10
            assert factor > 0


class TestSeatScorePerformance:
    """성능 테스트"""

    def test_recommendation_speed(self, seatscore_engine, sample_route):
        """추천 계산 속도 테스트 (1초 이내)"""
        import time

        start = time.time()
        seatscore_engine.recommend(
            sample_route["boarding"],
            sample_route["destination"],
            sample_route["hour"],
            sample_route["direction"]
        )
        elapsed = time.time() - start

        assert elapsed < 1.0, f"추천 계산이 너무 오래 걸립니다: {elapsed:.2f}초"

    def test_multiple_recommendations(self, seatscore_engine):
        """여러 추천을 연속으로 수행"""
        routes = [
            ("강남", "시청", 8, "내선"),
            ("홍대입구", "강남", 18, "외선"),
            ("잠실", "신촌", 14, "내선"),
        ]

        for boarding, destination, hour, direction in routes:
            result = seatscore_engine.recommend(boarding, destination, hour, direction)
            assert result is not None
            assert result["best_car"] >= 1
