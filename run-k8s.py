"""
Log-Guard: Kubernetes One-Click Runner (Enhanced)

이 스크립트는 다음 작업을 자동으로 수행합니다:
1. Minikube 클러스터 시작
2. 백엔드 이미지 빌드 (Minikube Docker)
3. K8s Manifest 적용
4. .env 설정 동기화 (Webhook URL 등)
5. 서비스 노출
"""

import os
import sys
import subprocess
import time

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
        print(f"[!] {description} 중 오류 발생: {e}")
        return False

def main():
    print("☸️  Log-Guard Kubernetes 통합 배포 제어기")
    
    # 1. Minikube 시작
    run_command("minikube start --driver=docker", "Minikube 클러스터 시작")

    # 2. 이미지 빌드
    print("[*] 백엔드 이미지를 빌드합니다 (Minikube 내부 저장소)")
    run_command("eval $(minikube docker-env) && docker build -t logguard-backend:latest .", "Docker 이미지 빌드")

    # 3. YAML 적용
    run_command("kubectl apply -f k8s/", "Kubernetes 설정(YAML) 적용")

    # 4. .env 동기화 (핵심!)
    print("[*] .env 파일의 환경 변수를 수집하여 전송합니다...")
    if os.path.exists(".env"):
        applied_count = 0
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    if key in ["N8N_WEBHOOK_URL", "SLACK_WEBHOOK_URL"]:
                        print(f"  -> {key} 전송 중...")
                        run_command(f"kubectl set env deployment/backend-deployment {key}={value}", f"{key} 동기화")
                        applied_count += 1
        print(f"[+] 총 {applied_count}개의 환경 변수가 서버에 주입되었습니다.")
    else:
        print("[!] .env 파일을 찾을 수 없어 환경 변수 주입을 건너뜁니다.")

    # 5. 마무리
    print("[*] 서버가 완전히 가동될 때까지 5초간 대기합니다...")
    time.sleep(5)
    
    print("[+] 모든 작업이 완료되었습니다! 대시보드를 엽니다.")
    run_command("minikube service backend-service", "대시보드 서비스 오픈")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] 중단되었습니다.")
        sys.exit(0)
