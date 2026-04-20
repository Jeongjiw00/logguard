# Log-Guard

**Real-time Log Anomaly Detection System using Z-score Analysis**

서버 로그를 실시간으로 수집하고, 통계적 방법(Z-score)으로 이상 트래픽을 자동 감지하는 시스템입니다.

![Log-Guard Dashboard Preview](assets/img/dashboard.png)

## 빠른 시작

가장 간단하게 시스템을 실행하는 방법입니다:

```bash
# 가상환경 활성화 (필요 시)
source venv/bin/activate

# 통합 서버 실행 (Redis 시작 + 백엔드 + 브라우저 열기)
python run.py
```

## 아키텍처

```
Log Producer -> Redis Queue -> Detection Engine -> Dashboard (WebSocket)
```

## 기술 스택

- **Backend**: Python 3.9+ / FastAPI / Pandas / NumPy
- **Frontend**: Vanilla JS / Chart.js (CDN) / CSS3 (Glassmorphism)
- **Infrastructure**: Redis (Message Queue)
- **Monitoring**: WebSocket Real-time Streaming, Slack Anomaly Alerts

---

## 상세 설정 및 실행 가이드

### 1. 환경 설정 및 설치

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (Slack 알림 설정 등)
cp .env.example .env
```

### 2. 수동 실행 방법

통합 실행기(`run.py`)를 사용하지 않을 경우:

```bash
# Redis 실행
docker compose up -d

# 백엔드 서버 실행
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

### 3. API 및 통계 확인

- **Dashboard**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health
- **Recent Anomalies**: http://localhost:8000/api/v1/anomalies

---

## 이상 탐지 원리 (수학적 접근)

고정 임계값(예: 100req/s 초과 시 차단) 대신 데이터의 분포를 고려한 **Z-score(표준점수)** 방식을 도입했습니다. 이를 통해 트래픽 변동성에 유연하게 대응하고 오탐(False Positive)을 줄였습니다.

### Z-score 공식
```
Z = (x - μ) / σ
```
- `x`: 현재 관측값 (응답 시간, 요청 빈도 등)
- `μ`: 슬라이딩 윈도우(60초) 내 평균
- `σ`: 슬라이딩 윈도우 내 표준편차

### 탐지 대상 메트릭

| 메트릭 | 탐지 기준 | 판정 기준 |
|--------|------|------|
| **Latency** | 응답 시간 거동 분석 | Z >= 3.0 |
| **Frequency** | 1초당 요청 수 분석 | Z >= 3.0 |
| **Error Rate** | 4xx/5xx 에러율 분석 | Z >= 3.0 |

## License

MIT
