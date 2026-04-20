"""
Phase 3: Slack 웹훅 알림 모듈

이상 탐지 결과를 Slack 채널로 전송합니다.
SLACK_WEBHOOK_URL이 설정되지 않으면 콘솔 출력으로 대체합니다.
"""

import logging
from datetime import datetime

import httpx

from backend.config import settings
from backend.engine.models import AnomalyAlert

logger = logging.getLogger(__name__)


async def send_slack_alert(alert: AnomalyAlert) -> bool:
    """
    Slack 웹훅으로 이상 탐지 알림 전송

    Returns:
        True: 전송 성공, False: 전송 실패 또는 미설정
    """
    if not settings.slack_webhook_url or settings.slack_webhook_url.startswith("https://hooks.slack.com/services/YOUR"):
        logger.info("[콘솔 알림] %s", alert.message)
        return False

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Log-Guard 이상 탐지 알림",
                    "emoji": False,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*탐지 유형:*\n{alert.anomaly_type.value}"},
                    {"type": "mrkdwn", "text": f"*Z-score:*\n{alert.z_score:.3f}"},
                    {"type": "mrkdwn", "text": f"*현재값:*\n{alert.current_value}"},
                    {"type": "mrkdwn", "text": f"*평균:*\n{alert.mean}"},
                    {"type": "mrkdwn", "text": f"*표준편차:*\n{alert.std}"},
                    {"type": "mrkdwn", "text": f"*윈도우 크기:*\n{alert.window_size}"},
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Time: {alert.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    }
                ],
            },
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.slack_webhook_url,
                json=payload,
                timeout=10.0,
            )
            if response.status_code == 200:
                logger.info("Slack 알림 전송 성공")
                return True
            else:
                logger.error("Slack 알림 실패: %s", response.text)
                return False
    except httpx.HTTPError as e:
        logger.error("Slack 연결 오류: %s", e)
        return False
