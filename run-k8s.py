"""
Log-Guard: Kubernetes One-Click Runner

이 스크립트는 다음 작업을 자동으로 수행합니다:
1. Minikube 클러스터 시작 (Docker 드라이버)
2. Minikube 내부 도커 환경에 백엔드 이미지 빌드
3. Kubernetes Manifest 적용 (Redis + Backend)
4. 서비스 자동 노출 및 브라우저 열기
"""

import os
import sys
import subprocess
import time
import platform

# 설치된 경로들을 우선 탐색
BREW_PATH = "/opt/homebrew/bin"
DOCKER_BIN_PATH = "/Applications/Docker.app/Contents/Resources/bin"

def get_env_with_paths():
    env = os.environ.copy()
    paths = env.get("PATH", "").split(os.pathsep)
    if BREW_PATH not in paths: paths.append(BREW_PATH)
    if DOCKER_BIN_PATH not in paths: paths.append(DOCKER_BIN_PATH)
    env["PATH"] = os.pathsep.join(paths)
    return env

def run_command(command, description, capture=False):
    print(f"[*] {description}...")
    try:
        env = get_env_with_paths()
        if capture:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True, env=env)
            return result.stdout.strip()
        else:
            subprocess.run(command, shell=True, check=True, env=env)
            return True
    except subprocess.CalledProcessError as e:
        print(f"[!] Error during {description}: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(e.stderr.decode())
        return False

def main():
    print("Log-Guard Kubernetes 배포 시작")
    
    # 1. Minikube 시작
    if not run_command("minikube start --driver=docker", "Minikube 클러스터 시작"):
        sys.exit(1)

    # 2. 이미지 빌드 (Minikube 내부 도커 사용)
    print("[*] Minikube 도커 환경에 이미지 빌드 중 (시간이 소요될 수 있습니다)...")
    # eval $(minikube docker-env)를 파이썬에서 직접 쓰기엔 복잡하므로 쉘 스크립트 형식으로 전달
    build_cmd = "eval $(minikube docker-env) && docker build -t logguard-backend:latest ."
    if not run_command(build_cmd, "백엔드 이미지 빌드"):
        sys.exit(1)

    # 3. K8s Manifest 적용
    if not run_command("kubectl apply -f k8s/", "Kubernetes Manifest (YAML) 적용"):
        sys.exit(1)

    # 4. 롤아웃 대기 (옵션)
    print("[*] 서버가 준비될 때까지 잠시 대기 중...")
    time.sleep(5)

    # 5. 서비스 열기
    print("[+] 모든 준비가 완료되었습니다! 대시보드를 엽니다.")
    run_command("minikube service backend-service", "대시보드 서비스 열기")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] 중단되었습니다.")
        sys.exit(0)
