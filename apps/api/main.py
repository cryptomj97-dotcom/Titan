import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from apps.api.models.db import init_db
from apps.api.redis_client import close_redis
from apps.api.routers.auth import router as auth_router
from apps.api.routers.analysis import router as analysis_router
from apps.api.logger import logger

app = FastAPI(title="Titan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(analysis_router)


@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized.")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Closing Redis connections...")
    await close_redis()
    logger.info("Redis connections closed.")


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/")
async def root():
    return JSONResponse({"service": "Titan API", "status": "ok"})
