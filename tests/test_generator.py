"""
Log Generator 단위 테스트
"""

from backend.producer.generator import generate_anomaly_log, generate_normal_log


class TestNormalLogGenerator:
    """정상 로그 생성 테스트"""

    def test_has_required_fields(self):
        log = generate_normal_log()
        required_fields = [
            "timestamp", "ip", "method", "path",
            "status_code", "response_time_ms", "bytes_sent", "user_agent",
        ]
        for field in required_fields:
            assert field in log, f"필드 누락: {field}"

    def test_response_time_is_positive(self):
        for _ in range(100):
            log = generate_normal_log()
            assert log["response_time_ms"] > 0

    def test_status_code_is_valid(self):
        for _ in range(100):
            log = generate_normal_log()
            assert 100 <= log["status_code"] < 600

    def test_ip_format(self):
        log = generate_normal_log()
        parts = log["ip"].split(".")
        assert len(parts) == 4
        for part in parts:
            assert 0 <= int(part) <= 255


class TestAnomalyLogGenerator:
    """이상 로그 생성 테스트"""

    def test_anomaly_has_higher_latency(self):
        """이상 로그의 평균 응답 시간이 정상보다 높아야 함"""
        normal_latencies = [generate_normal_log()["response_time_ms"] for _ in range(200)]
        anomaly_latencies = [generate_anomaly_log()["response_time_ms"] for _ in range(200)]

        avg_normal = sum(normal_latencies) / len(normal_latencies)
        avg_anomaly = sum(anomaly_latencies) / len(anomaly_latencies)

        assert avg_anomaly > avg_normal * 2, (
            f"이상 로그 평균({avg_anomaly:.0f}ms)이 정상({avg_normal:.0f}ms)의 2배 이상이어야 함"
        )

    def test_anomaly_uses_attack_paths(self):
        """이상 로그는 공격성 경로를 사용해야 함"""
        from backend.producer.generator import ATTACK_PATHS

        for _ in range(50):
            log = generate_anomaly_log()
            assert log["path"] in ATTACK_PATHS
