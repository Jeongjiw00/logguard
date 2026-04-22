import httpx
import logging
from backend.config import settings
from backend.engine.models import AnomalyAlert

logger = logging.getLogger(__name__)

async def send_n8n_webhook(alert: AnomalyAlert):
    """
    n8n Webhook으로 이상 탐지 데이터를 전송하여 자동화 워크플로우를 트리거합니다.
    """
    webhook_url = settings.n8n_webhook_url
    
    if not webhook_url or webhook_url == "":
        # URL이 설정되지 않았으면 그냥 넘어갑니다.
        return False

    payload = alert.model_dump(mode="json")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=5.0
            )
            if response.status_code in [200, 201]:
                logger.info("n8n 워크플로우 트리거 성공")
                return True
            else:
                logger.error(f"n8n 트리거 실패: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"n8n 연결 오류: {e}")
        return False
