# Python 3.9 경량 버전 사용
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필수 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사 (backend 폴더 내용)
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run.py .

# 환경변수 설정 (K8s에서 덮어쓰기 가능)
ENV REDIS_HOST=localhost
ENV REDIS_PORT=6379

# FastAPI 실행 포트 노출
EXPOSE 8000

# 서버 실행 명령어
CMD ["python", "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
