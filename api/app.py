# -*- coding: utf-8 -*-
"""
Metropy FastAPI Application
"""
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from api.rate_limit import create_backend

from api.dependencies import registry
from api.routers import recommend, stations, calibrate, feedback, validate, stability

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """IP별 분당 60회 요청 제한 미들웨어"""
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.backend = create_backend()
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        if await self.backend.is_rate_limited(
            client_ip, self.requests_per_minute, window=60
        ):
            return JSONResponse(
                status_code=429,
                content={"detail": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."}
            )

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.load()
    try:
        from src.weather import WeatherService
        svc = WeatherService()
        if svc.service_key:
            engine = registry.get_engine()
            engine.set_weather_service(svc)
    except Exception:
        pass
    yield


app = FastAPI(title="Metropy", version="1.0.0", lifespan=lifespan)


allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

app.include_router(recommend.router, prefix="/api", tags=["recommend"])
app.include_router(stations.router, prefix="/api", tags=["stations"])
app.include_router(calibrate.router, prefix="/api", tags=["calibrate"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
app.include_router(validate.router, prefix="/api", tags=["validate"])
app.include_router(stability.router, prefix="/api", tags=["stability"])

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")



@app.get(
    "/health",
    summary="서비스 상태 확인",
    description="엔진 로드 여부, 역 수, 데이터 소스 목록 등 서비스 상태를 반환합니다.",
    response_description="status(healthy/degraded/unavailable), version, stations 수, data_sources 목록",
)
async def health():
    try:
        engine = registry.get_engine()
        station_count = len(engine.station_order)
        has_data = station_count > 0 and bool(engine.data_sources)
        return {
            "status": "healthy" if has_data else "degraded",
            "version": "4.0.0",
            "stations": station_count,
            "data_sources": engine.data_sources,
        }
    except RuntimeError:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "Engine not loaded"},
        )





@app.post(
    "/api/reload",
    summary="데이터 리로드",
    description="CSV/JSON 등 데이터 파일이 갱신된 후, 엔진 데이터를 메모리에 다시 로드합니다. "
               "추천 캐시도 함께 무효화됩니다.",
    response_description="리로드 성공 여부(status), 메시지, 갱신된 data_sources 목록",
)
async def reload_data():
    """데이터를 다시 로드한다. 새 CSV/JSON 파일 반영 시 사용."""
    try:
        with registry.engine_lock:
            registry.load()
            from api.cache import invalidate_recommend_cache
            invalidate_recommend_cache()
        engine = registry.get_engine()
        return {
            "status": "ok",
            "message": "데이터가 성공적으로 다시 로드되었습니다.",
            "data_sources": engine.data_sources,
        }
    except Exception as e:
        logging.exception("Data reload failed")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"데이터 리로드 실패: {str(e)}"},
        )


@app.get(
    "/",
    summary="프론트엔드 페이지",
    description="Metropy 프론트엔드 SPA(index.html)를 반환합니다.",
    response_description="index.html 파일",
)
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
