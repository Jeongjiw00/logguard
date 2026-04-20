"""
Phase 2: Z-score 기반 이상 탐지 엔진

슬라이딩 윈도우 내 데이터에서 Z-score를 계산하여
요청 빈도, 응답 시간, 에러율의 이상치를 감지합니다.

──────────────────────────────────────────────
Z-score = (x - μ) / σ
  x: 현재 관측값
  μ: 윈도우 내 평균
  σ: 윈도우 내 표준편차
──────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Deque, List, Optional

import numpy as np
import pandas as pd

from log_guard.config import settings
from log_guard.engine.models import AnomalyAlert, AnomalyType, LogEntry

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """슬라이딩 윈도우 기반 이상 탐지기"""

    def __init__(
        self,
        threshold: Optional[float] = None,
        window_seconds: Optional[int] = None,
        min_samples: Optional[int] = None,
    ):
        self.threshold = threshold or settings.anomaly_threshold
        self.window_seconds = window_seconds or settings.window_seconds
        self.min_samples = min_samples or settings.min_samples

        # 슬라이딩 윈도우 버퍼 (시간 순서대로 저장)
        self._buffer: Deque[LogEntry] = deque()

        # 통계 추적
        self.total_processed: int = 0
        self.total_anomalies: int = 0
        self.recent_anomalies: Deque[AnomalyAlert] = deque(maxlen=50)

    def _trim_window(self) -> None:
        """윈도우 시간 범위를 초과한 오래된 로그를 버퍼에서 제거"""
        now = datetime.now(timezone.utc)
        while self._buffer:
            oldest = self._buffer[0]
            age = (now - oldest.timestamp).total_seconds()
            if age > self.window_seconds:
                self._buffer.popleft()
            else:
                break

    def ingest(self, log: LogEntry) -> List[AnomalyAlert]:
        """
        로그 1건을 수집하고 이상 탐지를 수행합니다.

        Returns:
            감지된 이상치 리스트 (없으면 빈 리스트)
        """
        self._buffer.append(log)
        self.total_processed += 1
        self._trim_window()

        if len(self._buffer) < self.min_samples:
            return []

        alerts: List[AnomalyAlert] = []

        # ─── 1. 응답 시간(Latency) 이상 탐지 ───
        latency_alert = self._check_latency(log)
        if latency_alert:
            alerts.append(latency_alert)

        # ─── 2. 요청 빈도(Frequency) 이상 탐지 ───
        freq_alert = self._check_frequency()
        if freq_alert:
            alerts.append(freq_alert)

        # ─── 3. 에러율(Error Rate) 이상 탐지 ───
        error_alert = self._check_error_rate()
        if error_alert:
            alerts.append(error_alert)

        for alert in alerts:
            self.total_anomalies += 1
            self.recent_anomalies.append(alert)

        return alerts

    def _check_latency(self, current_log: LogEntry) -> Optional[AnomalyAlert]:
        """응답 시간 Z-score 계산"""
        latencies = np.array([log.response_time_ms for log in self._buffer])
        mean = float(np.mean(latencies))
        std = float(np.std(latencies))

        if std == 0:
            return None

        z_score = (current_log.response_time_ms - mean) / std

        if abs(z_score) >= self.threshold:
            return AnomalyAlert(
                detected_at=datetime.now(timezone.utc),
                anomaly_type=AnomalyType.LATENCY,
                z_score=round(z_score, 3),
                threshold=self.threshold,
                current_value=round(current_log.response_time_ms, 2),
                mean=round(mean, 2),
                std=round(std, 2),
                window_size=len(self._buffer),
                message=(
                    f"응답 시간 이상! {current_log.response_time_ms:.0f}ms "
                    f"(평균: {mean:.0f}ms, Z={z_score:.2f})"
                ),
            )
        return None

    def _check_frequency(self) -> Optional[AnomalyAlert]:
        """
        1초 단위 요청 빈도의 Z-score를 계산.
        최근 1초의 요청 수가 윈도우 전체 평균 대비 이상인지 확인.
        """
        df = pd.DataFrame([
            {"ts": log.timestamp} for log in self._buffer
        ])
        df["ts"] = pd.to_datetime(df["ts"])

        # 1초 단위 리샘플링
        counts = df.set_index("ts").resample("1s").size()

        if len(counts) < 3:
            return None

        mean = float(counts.mean())
        std = float(counts.std())

        if std == 0:
            return None

        current_rate = float(counts.iloc[-1]) if len(counts) > 0 else 0
        z_score = (current_rate - mean) / std

        if z_score >= self.threshold:
            return AnomalyAlert(
                detected_at=datetime.now(timezone.utc),
                anomaly_type=AnomalyType.FREQUENCY,
                z_score=round(z_score, 3),
                threshold=self.threshold,
                current_value=current_rate,
                mean=round(mean, 2),
                std=round(std, 2),
                window_size=len(self._buffer),
                message=(
                    f"요청 빈도 급증! {current_rate:.0f}req/s "
                    f"(평균: {mean:.1f}req/s, Z={z_score:.2f})"
                ),
            )
        return None

    def _check_error_rate(self) -> Optional[AnomalyAlert]:
        """최근 윈도우 내 에러율(4xx/5xx) Z-score 계산"""
        if len(self._buffer) < self.min_samples:
            return None

        # 5초 단위 에러율 계산
        df = pd.DataFrame([
            {
                "ts": log.timestamp,
                "is_error": 1 if log.status_code >= 400 else 0,
            }
            for log in self._buffer
        ])
        df["ts"] = pd.to_datetime(df["ts"])
        error_rates = df.set_index("ts").resample("5s")["is_error"].mean()

        if len(error_rates) < 3:
            return None

        mean = float(error_rates.mean())
        std = float(error_rates.std())

        if std == 0:
            return None

        current_rate = float(error_rates.iloc[-1])
        z_score = (current_rate - mean) / std

        if z_score >= self.threshold:
            return AnomalyAlert(
                detected_at=datetime.now(timezone.utc),
                anomaly_type=AnomalyType.ERROR_RATE,
                z_score=round(z_score, 3),
                threshold=self.threshold,
                current_value=round(current_rate * 100, 1),
                mean=round(mean * 100, 1),
                std=round(std * 100, 1),
                window_size=len(self._buffer),
                message=(
                    f"에러율 급증! {current_rate * 100:.1f}% "
                    f"(평균: {mean * 100:.1f}%, Z={z_score:.2f})"
                ),
            )
        return None

    def get_stats(self) -> dict:
        """현재 탐지 엔진 통계"""
        latencies = [log.response_time_ms for log in self._buffer]
        errors = [1 for log in self._buffer if log.status_code >= 400]

        return {
            "buffer_size": len(self._buffer),
            "total_processed": self.total_processed,
            "total_anomalies": self.total_anomalies,
            "avg_latency": round(np.mean(latencies), 2) if latencies else 0,
            "error_rate": round(len(errors) / len(self._buffer) * 100, 1) if self._buffer else 0,
        }
