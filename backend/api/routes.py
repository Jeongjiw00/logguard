"""
REST API 라우트

대시보드에서 사용하는 HTTP 엔드포인트를 정의합니다.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["monitoring"])

# 탐지 엔진 인스턴스는 main.py에서 주입
_detector = None


def set_detector(detector):
    """탐지 엔진 인스턴스를 라우터에 주입"""
    global _detector
    _detector = detector


@router.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "ok", "service": "log-guard"}


@router.get("/stats")
async def get_stats():
    """현재 탐지 엔진 통계"""
    if _detector is None:
        return {"error": "Detector not initialized"}
    return _detector.get_stats()


@router.get("/anomalies")
async def get_recent_anomalies(limit: int = 20):
    """최근 이상 탐지 결과 목록"""
    if _detector is None:
        return {"error": "Detector not initialized"}

    anomalies = list(_detector.recent_anomalies)[-limit:]
    return {
        "count": len(anomalies),
        "anomalies": [a.model_dump(mode="json") for a in anomalies],
    }


@router.get("/config")
async def get_config():
    """현재 탐지 설정값"""
    from backend.config import settings

    return {
        "threshold": settings.anomaly_threshold,
        "window_seconds": settings.window_seconds,
        "min_samples": settings.min_samples,
    }
