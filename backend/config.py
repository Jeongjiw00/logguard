"""
중앙 집중식 설정 관리.
환경변수 → .env 파일 → 기본값 순으로 로드합니다.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_queue_key: str = "logguard:logs"

    # Detection
    anomaly_threshold: float = 3.0  # Z-score 임계값
    window_seconds: int = 60  # 슬라이딩 윈도우 크기 (초)
    min_samples: int = 10  # 최소 샘플 수 (이 이하면 탐지 건너뜀)

    # Notifications
    slack_webhook_url: str = ""
    n8n_webhook_url: str = ""


    # Server
    api_host: str = "0.0.0.0"

    api_port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
