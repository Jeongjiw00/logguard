"""
Redis Consumer: 큐에서 로그를 소비하여 탐지 엔진에 전달

brpop을 사용하여 Redis Queue에서 로그를 하나씩 꺼내어
AnomalyDetector에 전달하는 비동기 루프입니다.
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis

from log_guard.config import settings
from log_guard.engine.detector import AnomalyDetector
from log_guard.engine.models import LogEntry

logger = logging.getLogger(__name__)


class LogConsumer:
    """Redis 기반 로그 소비자"""

    def __init__(self, detector: AnomalyDetector, on_anomaly=None):
        """
        Args:
            detector: 이상 탐지 엔진 인스턴스
            on_anomaly: 이상 탐지 시 호출되는 콜백 (async callable)
        """
        self.detector = detector
        self.on_anomaly = on_anomaly
        self._running = False

    async def start(self):
        """소비자 메인 루프 시작"""
        pool = aioredis.ConnectionPool.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
        )
        r = aioredis.Redis(connection_pool=pool)

        self._running = True
        logger.info("Log Consumer 시작 - 큐: %s", settings.redis_queue_key)

        try:
            while self._running:
                # brpop: 큐에 데이터가 올 때까지 최대 1초 대기
                result = await r.brpop(settings.redis_queue_key, timeout=1)

                if result is None:
                    continue

                _, raw_data = result
                try:
                    log_data = json.loads(raw_data)
                    log_entry = LogEntry(**log_data)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error("❌ 로그 파싱 실패: %s", e)
                    continue

                # 탐지 엔진에 로그 전달
                alerts = self.detector.ingest(log_entry)

                # 이상치가 감지되면 콜백 호출
                if alerts and self.on_anomaly:
                    for alert in alerts:
                        logger.warning(alert.message)
                        await self.on_anomaly(alert)

        except asyncio.CancelledError:
            logger.info("Log Consumer 종료")
        finally:
            self._running = False
            await pool.aclose()

    def stop(self):
        """소비자 루프 중지"""
        self._running = False
