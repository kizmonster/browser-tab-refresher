#!/usr/bin/env python3
"""
Browser Tab Refresh - 브라우저 탭 새로고침 유틸리티
Chrome과 Edge 브라우저 탭을 모니터링하고 자동으로 새로고침
"""
import sys
import os
import json
import argparse
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QStandardPaths

from gui import MainWindow
from tab_manager import TabManager

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger('BrowserTabManager')

# 설정 파일 경로
def get_config_path():
    """설정 파일 경로 반환"""
    app_data = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not os.path.exists(app_data):
        os.makedirs(app_data, exist_ok=True)
    config_path = os.path.join(app_data, 'tab_handles.json')
    return config_path

def load_tab_handles(config_path):
    """설정 파일에서 탭 정보 로드"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            logger.warning(f"설정 파일을 로드할 수 없습니다: {config_path}")
    
    # 기본 설정
    return {
        "browser_type": "chrome",
        "managed_tabs": []
    }

def save_tab_handles(config_path, tab_handles):
    """설정 파일에 탭 정보 저장"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(tab_handles, f, ensure_ascii=False, indent=2)
    except:
        logger.warning(f"설정 파일을 저장할 수 없습니다: {config_path}")

def parse_arguments():
    """명령줄 인수 파싱"""
    parser = argparse.ArgumentParser(description='Browser Tab Refresh - 브라우저 탭 모니터링 및 자동 새로고침')
    parser.add_argument('--browser', choices=['chrome', 'edge'], default=None,
                        help='사용할 브라우저 (chrome 또는 edge)')
    parser.add_argument('--config', type=str, default=None,
                        help='설정 파일 경로 (기본값: 앱 데이터 디렉토리)')
    parser.add_argument('--debug', action='store_true',
                        help='디버그 모드 활성화')
    parser.add_argument('--refresh', action='store_true',
                        help='시작 시 저장된 모든 탭 즉시 리프레시')
    parser.add_argument('--auto', action='store_true', 
                        help='시작 시 자동 리프레시 활성화')
    return parser.parse_args()

def main():
    """메인 함수"""
    # 명령줄 인수 파싱
    args = parse_arguments()
    
    # 디버그 모드 설정
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("디버그 모드가 활성화되었습니다.")
    
    # 설정 파일 경로 설정
    config_path = args.config if args.config else get_config_path()
    logger.debug(f"설정 파일 경로: {config_path}")
    
    # 탭 설정 로드
    tab_handles = load_tab_handles(config_path)
    
    # 명령줄에서 브라우저 타입이 지정되었으면 업데이트
    if args.browser:
        tab_handles["browser_type"] = args.browser
    
    # 애플리케이션 생성
    app = QApplication(sys.argv)
    app.setApplicationName("Browser Tab Manager")
    
    # 탭 매니저 생성
    tab_manager = TabManager(tab_handles)
    
    # 메인 윈도우 생성
    main_window = MainWindow(tab_manager)
    
    # 실행 시 즉시 리프레시 수행
    if args.refresh and tab_manager.managed_tabs:
        # GUI가 표시된 후 실행하기 위해 타이머를 사용
        QTimer.singleShot(500, main_window.quick_refresh_all)
    
    # 자동 리프레시 활성화
    if args.auto:
        main_window.auto_refresh_enabled = True
        main_window.auto_refresh_check.setChecked(True)
        main_window.toggle_auto_refresh(True)
    
    # 30초마다 탭 설정 저장
    save_timer = QTimer()
    save_timer.timeout.connect(lambda: save_tab_handles(config_path, tab_manager.get_tab_handles()))
    save_timer.start(30000)  # 30초
    
    # 애플리케이션 종료 시 설정 저장
    app.aboutToQuit.connect(lambda: save_tab_handles(config_path, tab_manager.get_tab_handles()))
    
    # 애플리케이션 실행
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 