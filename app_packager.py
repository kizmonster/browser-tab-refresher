#!/usr/bin/env python3
"""
패키징 스크립트 - PyInstaller를 사용해 실행 파일 생성
"""
import os
import sys
import platform
import subprocess
import shutil

def install_pyinstaller():
    """PyInstaller 설치"""
    print("PyInstaller 설치 중...")
    subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def package_app():
    """앱 패키징"""
    system = platform.system()
    
    # 임시 폴더 생성
    os.makedirs("build", exist_ok=True)
    
    # 기본 PyInstaller 옵션
    options = [
        "--name=BrowserTabManager",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        # 핵심 의존성 추가
        "--hidden-import=pyside6",
        "--hidden-import=selenium",
        "--hidden-import=webdriver_manager",
        # 압축 최적화
        "--upx-dir=./build" if os.path.exists("./build/upx") else "",
    ]
    
    # 시스템별 추가 옵션
    if system == "Darwin":  # macOS
        if os.path.exists("icon.icns"):
            options.append("--icon=icon.icns")
    elif system == "Windows":  # Windows
        if os.path.exists("icon.ico"):
            options.append("--icon=icon.ico")
    
    # 데이터 파일 포함
    if os.path.exists("tab_handles.json"):
        if system == "Darwin":
            options.append("--add-data=tab_handles.json:.")
        elif system == "Windows":
            options.append("--add-data=tab_handles.json;.")
    
    # UPX 압축기 다운로드 (더 작은 실행 파일 생성)
    try:
        if not os.path.exists("./build/upx"):
            print("UPX 압축기 다운로드 중...")
            if system == "Darwin":
                upx_url = "https://github.com/upx/upx/releases/download/v4.0.2/upx-4.0.2-macos_x86_64.tar.xz"
                subprocess.call(["curl", "-L", upx_url, "-o", "./build/upx.tar.xz"])
                subprocess.call(["tar", "-xf", "./build/upx.tar.xz", "-C", "./build"])
                shutil.move("./build/upx-4.0.2-macos_x86_64", "./build/upx")
            elif system == "Windows":
                upx_url = "https://github.com/upx/upx/releases/download/v4.0.2/upx-4.0.2-win64.zip"
                subprocess.call(["curl", "-L", upx_url, "-o", "./build/upx.zip"])
                import zipfile
                with zipfile.ZipFile("./build/upx.zip", 'r') as zip_ref:
                    zip_ref.extractall("./build")
                shutil.move("./build/upx-4.0.2-win64", "./build/upx")
    except Exception as e:
        print(f"UPX 다운로드 오류 (패키징은 계속됩니다): {e}")
    
    # 명령 실행
    cmd = [sys.executable, "-m", "PyInstaller"] + [opt for opt in options if opt]
    cmd.append("main.py")
    print(f"명령 실행: {' '.join(cmd)}")
    subprocess.call(cmd)
    
    # 결과 출력
    if system == "Darwin":
        print("\n패키징 완료! dist/BrowserTabManager.app 파일이 생성되었습니다.")
    elif system == "Windows":
        print("\n패키징 완료! dist/BrowserTabManager.exe 파일이 생성되었습니다.")
    else:
        print("\n패키징 완료! dist/BrowserTabManager 파일이 생성되었습니다.")
    
    # 정리
    try:
        if os.path.exists("./build"):
            shutil.rmtree("./build")
        if os.path.exists("./BrowserTabManager.spec"):
            os.remove("./BrowserTabManager.spec")
    except:
        pass

if __name__ == "__main__":
    # 필요한 경우 PyInstaller 설치
    try:
        import PyInstaller
    except ImportError:
        install_pyinstaller()
    
    # 앱 패키징
    package_app() 