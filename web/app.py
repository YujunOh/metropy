# -*- coding: utf-8 -*-
"""
Metropy FastAPI Application
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from web.dependencies import registry
from web.routers import recommend, stations, calibrate

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.load()
    yield


app = FastAPI(title="Metropy", version="1.0.0", lifespan=lifespan)

# CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend.router, prefix="/api", tags=["recommend"])
app.include_router(stations.router, prefix="/api", tags=["stations"])
app.include_router(calibrate.router, prefix="/api", tags=["calibrate"])

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/health")
async def health():
    engine = registry.get_engine()
    return {
        "status": "healthy",
        "version": "3.0.0",
        "stations": len(engine.station_order),
        "data_sources": engine.data_sources,
    }


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))
