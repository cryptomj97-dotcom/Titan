import asyncio
import datetime
import json
import os
import re
from typing import AsyncGenerator, Dict, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.models.db import get_db_path
from apps.api.redis_client import get_redis_client
from apps.api.logger import logger
from services.agents.pipeline import AgentPipeline
from services.agents.state import TitanState
from services.data.data_packet_builder import DataPacketBuilder

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    asset: str
    mode: str = "standard"


class AnalyzeResponse(BaseModel):
    analysis_id: int
    status: str


VALID_ASSET_PATTERN = re.compile(r"^[A-Z0-9]{1,10}(/[A-Z0-9]{1,10})?$")


def validate_asset(asset: str) -> str:
    asset = asset.strip().upper()
    if not VALID_ASSET_PATTERN.match(asset):
        raise ValueError(f"Invalid asset format: {asset}")
    return asset


def get_asset_class(asset: str) -> str:
    asset = asset.upper()
    if asset in {"AAPL", "MSFT", "GOOG", "AMZN"}:
        return "EQUITY"
    if "/" in asset:
        base, quote = asset.split("/", 1)
        forex_symbols = {"EUR", "USD", "JPY", "GBP", "AUD", "NZD", "CHF", "CAD"}
        crypto_symbols = {"BTC", "ETH", "SOL", "BNB", "XRP", "LTC", "DOT", "ADA"}
        if base in forex_symbols and quote in forex_symbols:
            return "FOREX"
        if base in crypto_symbols or quote in {"USD", "USDT", "BTC", "ETH"}:
            return "CRYPTO"
        return "EQUITY"
    return "EQUITY"


async def _insert_analysis(asset: str, mode: str) -> int:
    db_path = get_db_path()
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO analyses (asset, mode, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (asset, mode, "queued", now, now),
        )
        await db.commit()
        return cursor.lastrowid


async def _update_analysis_status(analysis_id: int, status: str) -> None:
    db_path = get_db_path()
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE analyses SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, analysis_id),
        )
        await db.commit()


async def _log_data_quality(analysis_id: int, passed: bool, details: str) -> None:
    db_path = get_db_path()
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO data_quality_logs (analysis_id, passed, details, created_at) VALUES (?, ?, ?, ?)",
            (analysis_id, int(passed), details, now),
        )
        await db.commit()


async def _insert_signal(analysis_id: int, direction: str, confidence: float, payload: str) -> None:
    db_path = get_db_path()
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO signals (analysis_id, direction, confidence, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (analysis_id, direction, confidence, payload, now),
        )
        await db.commit()


async def _insert_agent_debate(analysis_id: int, bull_json: str, bear_json: str, judge_json: str) -> None:
    db_path = get_db_path()
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO agent_debates (analysis_id, bull_json, bear_json, judge_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (analysis_id, bull_json, bear_json, judge_json, now),
        )
        await db.commit()


async def _publish_event(analysis_id: int, event_type: str, payload: Dict) -> None:
    redis = await get_redis_client()
    channel = f"analysis:{analysis_id}"
    message = json.dumps({"event": event_type, "payload": payload, "timestamp": datetime.datetime.utcnow().isoformat()})
    try:
        await redis.publish(channel, message)
        logger.debug(f"Published {event_type} to channel {channel}")
    except Exception as exc:
        logger.error(f"Failed to publish event {event_type}: {exc}")


async def _run_analysis(analysis_id: int, asset: str, mode: str) -> None:
    await _update_analysis_status(analysis_id, "running")
    await _publish_event(analysis_id, "ANALYSIS_STARTED", {"asset": asset, "mode": mode})

    asset_class = get_asset_class(asset)
    builder = DataPacketBuilder(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    try:
        logger.info(f"Building data packet for {asset} ({asset_class})")
        packet = await builder.build(asset, asset_class)
        logger.info(f"Data packet built successfully. Quality passed: {packet.quality_report.get('passed', False)}")
        
        await _publish_event(analysis_id, "DATA_READY", {
            "asset": packet.asset,
            "asset_class": packet.asset_class,
            "quality_report": packet.quality_report,
            "assembled_at": packet.assembled_at,
        })
        await _log_data_quality(analysis_id, bool(packet.quality_report.get("passed", False)), json.dumps(packet.quality_report))

        if not packet.quality_report.get("passed", False):
            await _publish_event(analysis_id, "QUALITY_FAILED", {"reason": packet.quality_report})
            await _update_analysis_status(analysis_id, "failed")
            return

        state = TitanState(
            analysis_id=analysis_id,
            asset=asset,
            asset_class=asset_class,
            mode=mode,
            data_packet=packet,
        )

        def publish(event_type: str, payload: Dict) -> None:
            asyncio.create_task(_publish_event(analysis_id, event_type, payload))

        pipeline = AgentPipeline(publish)
        result_state = pipeline.run(state)

        await _insert_signal(
            analysis_id,
            result_state.final_output.get("signal", "NEUTRAL"),
            float(result_state.final_output.get("confidence", 0.0)),
            json.dumps(result_state.final_output),
        )

        debate_payload = result_state.debate or {}
        await _insert_agent_debate(
            analysis_id,
            json.dumps(debate_payload.get("bull", {})),
            json.dumps(debate_payload.get("bear", {})),
            json.dumps(debate_payload.get("judge", {})),
        )

        await _publish_event(analysis_id, "PIPELINE_COMPLETED", {
            "final_output": result_state.final_output,
            "debate": debate_payload,
        })
        await _update_analysis_status(analysis_id, "completed")
        await _publish_event(analysis_id, "ANALYSIS_COMPLETED", {"assembled_at": packet.assembled_at})
    except Exception as exc:
        logger.error(f"Analysis failed for {asset}: {exc}", exc_info=True)
        error_payload = {"error": str(exc)}
        await _publish_event(analysis_id, "ANALYSIS_FAILED", error_payload)
        await _log_data_quality(analysis_id, False, str(exc))
        await _update_analysis_status(analysis_id, "failed")


@router.post("/", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    try:
        asset = validate_asset(request.asset)
    except ValueError as exc:
        logger.warning(f"Invalid asset request: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    
    analysis_id = await _insert_analysis(asset, request.mode)
    logger.info(f"Created analysis {analysis_id} for {asset}")
    
    asyncio.create_task(_run_analysis(analysis_id, asset, request.mode))
    return AnalyzeResponse(analysis_id=analysis_id, status="queued")


async def event_stream(analysis_id: int) -> AsyncGenerator[str, None]:
    redis = await get_redis_client()
    pubsub = redis.pubsub()
    channel = f"analysis:{analysis_id}"
    await pubsub.subscribe(channel)
    
    logger.debug(f"Client subscribed to analysis stream: {analysis_id}")

    try:
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if not data:
                continue
            yield f"data: {json.dumps({"event": "analysis:update", "payload": json.loads(data)})}\n\n"
    except Exception as exc:
        logger.error(f"Error in event stream {analysis_id}: {exc}")
        yield f"data: {json.dumps({"event": "error", "payload": {"error": str(exc)}})}\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        logger.debug(f"Client unsubscribed from analysis stream: {analysis_id}")


@router.get("/{analysis_id}/stream")
async def stream_analysis(analysis_id: int):
    async def generator():
        async for event in event_stream(analysis_id):
            yield event

    return StreamingResponse(generator(), media_type="text/event-stream")
