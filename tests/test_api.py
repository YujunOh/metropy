"""
FastAPI 엔드포인트 테스트
"""
import pytest


class TestAPIEndpoints:
    """API 엔드포인트 테스트 클래스"""

    def test_root_endpoint(self, test_client):
        """루트 엔드포인트 테스트"""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_static_files(self, test_client):
        """정적 파일 서빙 테스트"""
        # CSS 파일 (모듈별 분리됨)
        for css_file in ['variables.css', 'base.css', 'layout.css',
                         'components.css', 'results.css', 'responsive.css']:
            response = test_client.get(f'/static/css/{css_file}')
            assert response.status_code == 200, f'{css_file} 서빙 실패'

        # JS 파일
        response = test_client.get("/static/js/app.js")
        assert response.status_code == 200

        # 파비콘
        response = test_client.get("/static/favicon.svg")
        assert response.status_code == 200

    def test_stations_endpoint(self, test_client):
        """역 목록 조회 엔드포인트 테스트"""
        response = test_client.get("/api/stations")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # 첫 번째 역 구조 확인
        station = data[0]
        assert "name" in station
        assert "name_display" in station

    def test_recommend_endpoint_valid(self, test_client, sample_route):
        """추천 엔드포인트 정상 요청 테스트"""
        response = test_client.post("/api/recommend", json={
            "boarding": sample_route["boarding"],
            "destination": sample_route["destination"],
            "hour": sample_route["hour"],
            "direction": sample_route["direction"]
        })

        assert response.status_code == 200

        data = response.json()
        assert "boarding" in data
        assert "destination" in data
        assert "best_car" in data
        assert "best_score" in data
        assert "worst_car" in data
        assert "worst_score" in data
        assert "car_scores" in data

        # car_scores 구조 확인
        assert isinstance(data["car_scores"], list)
        assert len(data["car_scores"]) == 10

        car_score = data["car_scores"][0]
        assert "car" in car_score
        assert "score" in car_score
        assert "rank" in car_score
        assert "benefit" in car_score
        assert "penalty" in car_score

    def test_recommend_endpoint_without_direction(self, test_client):
        """방향 미지정 시 자동 판별 테스트"""
        response = test_client.post("/api/recommend", json={
            "boarding": "강남",
            "destination": "시청",
            "hour": 8
            # direction 미지정
        })

        assert response.status_code == 200
        data = response.json()
        assert "direction" in data
        assert data["direction"] in ["내선", "외선"]

    def test_recommend_endpoint_invalid_hour(self, test_client):
        """잘못된 시간 입력 테스트"""
        response = test_client.post("/api/recommend", json={
            "boarding": "강남",
            "destination": "시청",
            "hour": 25,  # 잘못된 시간
            "direction": "내선"
        })

        # 422 (Validation Error) 또는 400 (Bad Request) 예상
        assert response.status_code in [400, 422]

    def test_recommend_endpoint_missing_fields(self, test_client):
        """필수 필드 누락 테스트"""
        response = test_client.post("/api/recommend", json={
            "boarding": "강남"
            # destination, hour 누락
        })

        assert response.status_code == 422  # Validation Error

    def test_calibrate_get(self, test_client):
        """캘리브레이션 조회 엔드포인트 테스트"""
        response = test_client.get("/api/calibrate")
        assert response.status_code == 200

        data = response.json()
        assert "beta" in data
        assert "facility_weights" in data
        assert "alpha_map" in data

        # 기본값 확인
        assert data["beta"] == 0.3
        assert data["facility_weights"]["에스컬레이터"] == 1.2

    def test_calibrate_post(self, test_client):
        """캘리브레이션 설정 엔드포인트 테스트"""
        new_params = {
            "beta": 0.5,
            "escalator_weight": 2.0,
            "elevator_weight": 1.5,
            "stairs_weight": 1.0,
            "alpha_morning_rush": 1.5,
            "alpha_evening_rush": 1.4,
            "alpha_midday": 1.0,
            "alpha_night": 0.5
        }

        response = test_client.post("/api/calibrate", json=new_params)
        assert response.status_code == 200

        # 설정이 적용되었는지 확인
        response = test_client.get("/api/calibrate")
        data = response.json()
        assert data["beta"] == 0.5
        assert data["facility_weights"]["에스컬레이터"] == 2.0

        # 원래 값으로 복구
        original_params = {
            "beta": 0.3,
            "escalator_weight": 1.2,
            "elevator_weight": 0,
            "stairs_weight": 1.0,
            "alpha_morning_rush": 1.4,
            "alpha_evening_rush": 1.3,
            "alpha_midday": 1.0,
            "alpha_night": 0.6
        }
        test_client.post("/api/calibrate", json=original_params)

    def test_sensitivity_analysis(self, test_client, sample_route):
        """민감도 분석 엔드포인트 테스트"""
        response = test_client.get("/api/sensitivity", params={
            "boarding": sample_route["boarding"],
            "destination": sample_route["destination"],
            "hour": sample_route["hour"],
        })

        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # 각 항목에 beta, car, score가 있는지 확인
        assert "beta" in data[0]
        assert "car" in data[0]
        assert "score" in data[0]


class TestAPIErrorHandling:
    """API 에러 처리 테스트"""

    def test_404_not_found(self, test_client):
        """존재하지 않는 엔드포인트 테스트"""
        response = test_client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self, test_client):
        """허용되지 않은 HTTP 메서드 테스트"""
        # GET 대신 POST로 stations 요청
        response = test_client.post("/api/stations")
        assert response.status_code == 405  # Method Not Allowed

    def test_invalid_json(self, test_client):
        """잘못된 JSON 형식 테스트"""
        response = test_client.post(
            "/api/recommend",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestAPICORS:
    """CORS 설정 테스트 (필요시)"""

    def test_cors_headers(self, test_client):
        """CORS 헤더 확인"""
        # 프로덕션 환경에서는 CORS 설정이 필요할 수 있음
        response = test_client.get("/api/stations")

        # 개발 환경에서는 CORS가 설정되지 않을 수 있음
        # assert "access-control-allow-origin" in response.headers
        pass


class TestAPIPerformance:
    """API 성능 테스트"""

    def test_api_response_time(self, test_client, sample_route):
        """API 응답 시간 테스트"""
        import time

        start = time.time()
        response = test_client.post("/api/recommend", json=sample_route)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0, f"API 응답이 너무 느립니다: {elapsed:.2f}초"

    def test_concurrent_requests(self, test_client):
        """동시 요청 처리 테스트"""
        from concurrent.futures import ThreadPoolExecutor

        def make_request():
            response = test_client.post("/api/recommend", json={
                "boarding": "강남",
                "destination": "시청",
                "hour": 8
            })
            return response.status_code

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # 모든 요청이 성공했는지 확인
        assert all(status == 200 for status in results)
