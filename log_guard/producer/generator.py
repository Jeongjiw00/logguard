"""
Phase 1: 가상 웹 서버 로그 생성기 (Mock Log Producer)

Apache/Nginx 스타일의 로그를 생성하여 Redis Queue에 push합니다.
- 정상 트래픽: 자연스러운 분포를 따르는 일반 요청
- 이상 트래픽: 주기적으로 발생하는 급증(burst) 패턴
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone

import redis.asyncio as aioredis

from log_guard.config import settings

logger = logging.getLogger(__name__)

# ─── 로그 생성에 사용할 상수 데이터 ───────────────────────────────────

NORMAL_PATHS = [
    "/", "/index.html", "/about", "/contact",
    "/api/users", "/api/products", "/api/orders",
    "/static/css/main.css", "/static/js/app.js",
    "/images/logo.png", "/favicon.ico",
]

ATTACK_PATHS = [
    "/admin", "/admin/login", "/wp-admin", "/phpmyadmin",
    "/.env", "/api/users?id=1' OR 1=1--",
    "/api/../../etc/passwd",
]

HTTP_METHODS = ["GET", "GET", "GET", "GET", "POST", "PUT", "DELETE"]  # GET 비중 높음

STATUS_CODES_NORMAL = [200, 200, 200, 200, 200, 201, 301, 304, 404]
STATUS_CODES_ANOMALY = [200, 200, 403, 403, 500, 500, 502, 503]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) Safari/605.1",
    "Mozilla/5.0 (Linux; Android 14) Mobile Chrome/125.0",
    "curl/8.7.1",
    "python-requests/2.32.0",
]


def _random_ip() -> str:
    """랜덤 IPv4 주소 생성"""
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def generate_normal_log() -> dict:
    """정상 트래픽 로그 1건 생성"""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": _random_ip(),
        "method": random.choice(HTTP_METHODS),
        "path": random.choice(NORMAL_PATHS),
        "status_code": random.choice(STATUS_CODES_NORMAL),
        "response_time_ms": max(1, random.gauss(50, 15)),  # 평균 50ms, 표준편차 15ms
        "bytes_sent": random.randint(200, 15000),
        "user_agent": random.choice(USER_AGENTS),
    }


def generate_anomaly_log() -> dict:
    """이상 트래픽 로그 1건 생성 (느린 응답 + 의심스러운 경로)"""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": _random_ip(),
        "method": random.choice(["GET", "POST"]),
        "path": random.choice(ATTACK_PATHS),
        "status_code": random.choice(STATUS_CODES_ANOMALY),
        "response_time_ms": max(1, random.gauss(500, 200)),  # 평균 500ms → 10배 느림
        "bytes_sent": random.randint(0, 500),
        "user_agent": random.choice(USER_AGENTS),
    }


async def run_producer(
    burst_interval: int = 30,
    burst_duration: int = 5,
    burst_rate: float = 0.02,
):
    """
    로그 생성 메인 루프

    Args:
        burst_interval: 이상 트래픽 발생 간격 (초)
        burst_duration: 이상 트래픽 지속 시간 (초)
        burst_rate: 이상 트래픽 시 로그 생성 간격 (초)
    """
    pool = aioredis.ConnectionPool.from_url(
        f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
    )
    r = aioredis.Redis(connection_pool=pool)

    logger.info("Log Producer 시작 - Redis %s:%s", settings.redis_host, settings.redis_port)
    log_count = 0
    last_burst_time = time.time()

    try:
        while True:
            now = time.time()
            is_burst = (now - last_burst_time) >= burst_interval

            if is_burst:
                # ─── 이상 트래픽 급증 (Burst) ───
                logger.warning("이상 트래픽 급증 시작! (지속 시간: %ds)", burst_duration)
                burst_end = now + burst_duration

                while time.time() < burst_end:
                    log_entry = generate_anomaly_log()
                    await r.lpush(settings.redis_queue_key, json.dumps(log_entry))
                    log_count += 1
                    await asyncio.sleep(burst_rate)

                logger.warning("이상 트래픽 급증 종료 - 총 %d건 생성됨", log_count)
                last_burst_time = time.time()
            else:
                # ─── 정상 트래픽 ───
                log_entry = generate_normal_log()
                await r.lpush(settings.redis_queue_key, json.dumps(log_entry))
                log_count += 1

                if log_count % 100 == 0:
                    queue_len = await r.llen(settings.redis_queue_key)
                    logger.info("로그 %d건 생성됨 | 큐 대기: %d건", log_count, queue_len)

                await asyncio.sleep(0.1)  # 0.1초 간격

    except asyncio.CancelledError:
        logger.info("Log Producer 종료 - 총 %d건 생성", log_count)

    finally:
        await pool.aclose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_producer())
