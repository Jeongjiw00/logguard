"""
Pydantic 데이터 모델 정의

로그 엔트리와 이상 탐지 결과의 스키마를 정의합니다.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """단일 로그 엔트리"""

    timestamp: datetime
    ip: str
    method: str
    path: str
    status_code: int
    response_time_ms: float
    bytes_sent: int
    user_agent: str = ""


class AnomalyType(str, Enum):
    """이상 탐지 유형"""

    FREQUENCY = "frequency"  # 요청 빈도 급증
    LATENCY = "latency"  # 응답 시간 급증
    ERROR_RATE = "error_rate"  # 에러율 급증


class AnomalyAlert(BaseModel):
    """이상 탐지 결과"""

    detected_at: datetime
    anomaly_type: AnomalyType
    z_score: float = Field(..., description="계산된 Z-score 값")
    threshold: float = Field(..., description="설정된 임계값")
    current_value: float = Field(..., description="현재 측정값")
    mean: float = Field(..., description="윈도우 내 평균값")
    std: float = Field(..., description="윈도우 내 표준편차")
    window_size: int = Field(..., description="분석에 사용된 샘플 수")
    message: str = ""
    sample_logs: List[LogEntry] = Field(default_factory=list)


class DashboardStats(BaseModel):
    """대시보드 실시간 통계"""

    total_logs: int = 0
    logs_per_second: float = 0.0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    anomaly_count: int = 0
    recent_anomalies: List[AnomalyAlert] = Field(default_factory=list)
