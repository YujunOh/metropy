"""
Metropy 웹앱 진입점
실행: python run.py
접속: http://localhost:8000
"""
import os
import sys
import webbrowser
from pathlib import Path
import uvicorn


def check_dependencies():
    """필수 패키지 확인"""
    required = ["fastapi", "uvicorn", "pandas", "numpy"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[ERROR] 필수 패키지가 설치되지 않았습니다: {', '.join(missing)}")
        print("다음 명령어로 설치하세요:")
        print("  pip install -r requirements.txt")
        sys.exit(1)


def check_data():
    """데이터 파일 확인"""
    data_dir = Path("data/processed")
    required_files = [
        "congestion_long.csv",
        "interstation_distance_processed.csv",
    ]

    missing = []
    for file in required_files:
        if not (data_dir / file).exists():
            missing.append(file)

    if missing:
        print(f"[WARN]  일부 데이터 파일이 없습니다: {', '.join(missing)}")
        print("데이터 전처리가 필요할 수 있습니다.")
        print("  python src/preprocessing.py")
        print()


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("Metropy - 서울 지하철 착석 효용 최적화")
    print("=" * 60)
    print()

    # 환경 확인
    check_dependencies()
    check_data()

    # 환경 변수 로드 (선택사항)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # 서버 설정
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "True").lower() == "true"

    url = f"http://{host}:{port}"

    print(f"[*] 서버 주소: {url}")
    print(f"[*] 프로젝트 디렉토리: {Path.cwd()}")
    print(f"[*] 자동 재시작: {'활성화' if reload else '비활성화'}")
    print()
    print("서버를 중지하려면 Ctrl+C를 누르세요.")
    print("=" * 60)
    print()

    # 브라우저 자동 열기 (선택사항)
    if os.getenv("OPEN_BROWSER", "False").lower() == "true":
        try:
            webbrowser.open(url)
        except Exception:
            pass

    # 서버 실행
    try:
        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            reload=reload,
            reload_dirs=["api", "src", "frontend"],
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
        )
    except KeyboardInterrupt:
        print("\n\n[*] 서버를 종료합니다.")
    except Exception as e:
        print(f"\n[ERROR] 서버 실행 중 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
