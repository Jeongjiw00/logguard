# Log-Guard

**Real-time Log Anomaly Detection System using Z-score Analysis**

서버 로그를 실시간으로 수집하고, 통계적 방법(Z-score)으로 이상 트래픽을 자동 감지하는 시스템입니다.

![Log-Guard Dashboard Preview](assets/img/dashboard.png)

## 아키텍처

```
Log Producer → Redis Queue → Detection Engine → WebSocket/Slack Alert
(0.1초 간격)    (메시지 버퍼)    (Z-score 분석)       (실시간 알림)
```

## 기술 스택

- **Python 3.11+** / FastAPI / Pandas / NumPy
- **Redis** — 메시지 큐
- **WebSocket** — 실시간 대시보드 스트리밍
- **Slack Webhook** — 이상 탐지 알림

## 빠른 시작

### 1. 환경 설정

```bash
# 가상환경 생성/활성화
python -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
```

### 2. Redis 실행

```bash
docker compose up -d
```

### 3. 서버 실행

```bash
uvicorn log_guard.api.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 시작되면 자동으로:
- Log Producer가 가상 로그를 생성합니다
- Detection Engine이 Z-score 기반 이상 탐지를 수행합니다
- 이상 감지 시 콘솔/Slack으로 알림을 보냅니다

### 4. API 확인

- Swagger UI: http://localhost:8000/docs
- 헬스 체크: http://localhost:8000/api/v1/health
- 실시간 통계: http://localhost:8000/api/v1/stats
- 이상 탐지 결과: http://localhost:8000/api/v1/anomalies

## 테스트

```bash
pytest -v
```

## 이상 탐지 원리

고정 임계값(예: 100req/s 초과 시 차단) 대신 **Z-score(표준점수)**를 사용합니다:

```
Z = (x - μ) / σ
```

- `x`: 현재 관측값
- `μ`: 슬라이딩 윈도우(60초) 내 평균
- `σ`: 슬라이딩 윈도우 내 표준편차

|Z-score| ≥ 3.0이면 이상치로 판정합니다 (정규분포에서 99.7% 밖).

### 탐지 대상

| 메트릭 | 설명 |
|--------|------|
| Latency | 응답 시간 급증 |
| Frequency | 초당 요청 수 급증 |
| Error Rate | 4xx/5xx 에러율 급증 |

## License

MIT


