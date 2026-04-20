"""
Log-Guard: One-Click Runner

이 스크립트는 다음 작업을 자동으로 수행합니다:
1. Redis 서비스 시작 (Homebrew)
2. 백엔드 서버 실행 (Uvicorn)
3. 브라우저에서 대시보드 자동 열기
"""

import os
import sys
import subprocess
import time
import webbrowser
import platform

def run_command(command, description):
    print(f"[*] {description}...")
    try:
        subprocess.run(command, shell=True, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] Error {description}: {e.stderr.decode().strip()}")
        return False

def main():
    print("🛡️  Log-Guard 통합 실행기 시작")
    
    # 1. Redis 실행 체크 및 시작
    is_mac = platform.system() == "Darwin"
    if is_mac:
        # Homebrew Redis 시작 시도
        print("[*] Redis 서비스 상태 확인 중...")
        result = subprocess.run("/opt/homebrew/bin/brew services list", shell=True, capture_output=True, text=True)
        if "redis" in result.stdout and "started" in result.stdout:
            print("[+] Redis가 이미 실행 중입니다.")
        else:
            if not run_command("/opt/homebrew/bin/brew services start redis", "Redis 시작"):
                print("[!] Redis 시작 실패. Docker Compose로 시도합니다...")
                run_command("docker compose up -d", "Docker Redis 시작")
    else:
        run_command("docker compose up -d", "Docker Redis 시작")

    # 2. 브라우저 열기 (서버가 뜨기 전 미리 요청 예약)
    print("[*] 대시보드 주소: http://localhost:8000")
    
    def open_browser():
        time.sleep(2) # 서버가 뜰 때까지 잠시 대기
        webbrowser.open("http://localhost:8000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # 3. 백엔드 실행
    print("[*] Log-Guard 백엔드 구동 시작...")
    venv_python = os.path.join("venv", "bin", "python")
    if not os.path.exists(venv_python):
        venv_python = "python3" # 가상환경 없을 경우 시스템 파이썬 시도

    cmd = [
        venv_python, "-m", "uvicorn", 
        "backend.api.main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000"
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[!] 시스템을 종료합니다.")
        sys.exit(0)

if __name__ == "__main__":
    main()
