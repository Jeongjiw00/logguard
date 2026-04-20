"""
Anomaly Detector 단위 테스트
"""

from datetime import datetime, timezone, timedelta

from log_guard.engine.detector import AnomalyDetector
from log_guard.engine.models import AnomalyType, LogEntry


def _make_log(response_time_ms: float = 50.0, status_code: int = 200, seconds_ago: int = 0) -> LogEntry:
    """테스트용 로그 엔트리 생성 헬퍼"""
    return LogEntry(
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago),
        ip="192.168.1.1",
        method="GET",
        path="/api/test",
        status_code=status_code,
        response_time_ms=response_time_ms,
        bytes_sent=1024,
        user_agent="pytest",
    )


class TestAnomalyDetector:
    """이상 탐지 엔진 테스트"""

    def test_no_alert_with_normal_data(self):
        """정상 데이터에서는 알림이 발생하지 않아야 함"""
        detector = AnomalyDetector(threshold=3.0, min_samples=5)

        alerts = []
        for _ in range(50):
            result = detector.ingest(_make_log(response_time_ms=50.0))
            alerts.extend(result)

        # 일정한 값이면 std=0이므로 알림 없음
        assert len(alerts) == 0

    def test_detects_latency_spike(self):
        """응답 시간 급증을 감지해야 함"""
        detector = AnomalyDetector(threshold=2.0, min_samples=5)

        # 정상 데이터 투입 (평균 ~50ms)
        for i in range(20):
            detector.ingest(_make_log(response_time_ms=50.0 + (i % 3)))

        # 극단적 이상치 투입 (2000ms)
        alerts = detector.ingest(_make_log(response_time_ms=2000.0))

        latency_alerts = [a for a in alerts if a.anomaly_type == AnomalyType.LATENCY]
        assert len(latency_alerts) > 0, "응답 시간 이상 감지 실패"
        assert latency_alerts[0].z_score > 2.0

    def test_stats_tracking(self):
        """통계 추적이 올바르게 동작해야 함"""
        detector = AnomalyDetector(min_samples=5)

        for _ in range(10):
            detector.ingest(_make_log())

        stats = detector.get_stats()
        assert stats["total_processed"] == 10
        assert stats["buffer_size"] == 10

    def test_window_trimming(self):
        """윈도우 시간이 지난 로그는 버퍼에서 제거"""
        detector = AnomalyDetector(window_seconds=30, min_samples=2)

        # 60초 전 로그 투입
        old_log = _make_log(seconds_ago=60)
        detector.ingest(old_log)

        # 현재 로그 투입 → 트리밍 발생
        detector.ingest(_make_log())

        # 오래된 로그는 제거되어야 함
        assert detector.get_stats()["buffer_size"] == 1
