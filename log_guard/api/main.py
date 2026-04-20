"""
FastAPI 앱 엔트리포인트

Producer → Redis → Consumer → Detector → WebSocket/Slack
전체 파이프라인을 연결하여 실행합니다.
"""

import asyncio
import logging
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from log_guard.alerting.slack import send_slack_alert
from log_guard.api.routes import router, set_detector
from log_guard.api.websocket import manager
from log_guard.engine.consumer import LogConsumer
from log_guard.engine.detector import AnomalyDetector
from log_guard.engine.models import AnomalyAlert
from log_guard.producer.generator import run_producer

# 프론트엔드 디렉토리 경로
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

logger = logging.getLogger(__name__)

# ─── 전역 인스턴스 ───
detector = AnomalyDetector()
consumer = LogConsumer(detector=detector)


async def on_anomaly_detected(alert: AnomalyAlert):
    """이상 탐지 시 콜백: WebSocket 브로드캐스트 + Slack 알림"""
    # WebSocket으로 실시간 전송
    await manager.broadcast({
        "type": "anomaly",
        "data": alert.model_dump(mode="json"),
    })
    # Slack 알림
    await send_slack_alert(alert)


async def stats_broadcaster():
    """1초마다 대시보드에 현재 통계를 브로드캐스트"""
    while True:
        if manager.active_connections:
            stats = detector.get_stats()
            await manager.broadcast({
                "type": "stats",
                "data": stats,
            })
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 백그라운드 태스크 관리"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # 탐지 엔진을 라우터에 주입
    set_detector(detector)
    consumer.on_anomaly = on_anomaly_detected

    # 백그라운드 태스크 시작
    producer_task = asyncio.create_task(run_producer())
    consumer_task = asyncio.create_task(consumer.start())
    stats_task = asyncio.create_task(stats_broadcaster())

    logger.info("Log-Guard 시스템 시작!")
    logger.info("   대시보드: http://localhost:8000")
    logger.info("   API: http://localhost:8000/api/v1/health")
    logger.info("   WebSocket: ws://localhost:8000/ws")

    yield

    # 종료 정리
    logger.info("시스템 종료 중...")
    consumer.stop()
    producer_task.cancel()
    consumer_task.cancel()
    stats_task.cancel()


    await asyncio.gather(producer_task, consumer_task, stats_task, return_exceptions=True)


app = FastAPI(
    title="Log-Guard",
    description="Real-time Log Anomaly Detection System using Z-score Analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정 (프론트엔드 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API 라우트 등록
app.include_router(router)

# 정적 파일 서빙 (CSS, JS)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """대시보드 메인 페이지"""
    index_path = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트 - 실시간 로그/이상치 스트리밍"""
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터의 메시지 대기 (keep-alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
