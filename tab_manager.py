#!/usr/bin/env python3
"""
브라우저 탭 관리자
열려 있는 브라우저 창을 찾아 관리하고 자동으로 새로고침하는 기능을 제공
"""
import os
import json
import time
import logging
import platform
import pyautogui
import subprocess
import random
import re
from datetime import datetime, timedelta  # datetime과 timedelta 클래스를 직접 import
import threading
import sys
import concurrent.futures  # 추가: 병렬 처리를 위한 concurrent.futures 모듈
import tempfile

# 로깅 설정
logger = logging.getLogger('TabManager')

# 핸들러가 없는 경우에만 추가 (중복 방지)
if not logger.handlers:
    # 콘솔 핸들러 추가
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 로그 레벨은 부모 로거의 설정을 따름
    logger.propagate = False

# OS 확인
SYSTEM = platform.system()

# Windows에서만 pygetwindow 임포트
if SYSTEM == "Windows":
    import pygetwindow as gw

class TabManager:
    def __init__(self, tab_handles=None):
        """
        TabManager 초기화
        
        Args:
            tab_handles (dict): 관리할 탭 정보가 포함된 딕셔너리
        """
        self.tab_info_file = "tab_handles.json"
        self.browser_type = "chrome"  # 기본값
        self.managed_tabs = []
        self.system = SYSTEM  # 운영체제 확인
        self.scheduled_refreshes = {}  # 예약된 새로고침 시간 저장
        self.tab_lock = threading.Lock()  # 스레드 안전을 위한 락
        self._tab_scheduled_refreshes = {}  # 내부적으로 사용할 예약된 새로고침 시간
        
        # 설정에서 관리 탭 초기화
        if tab_handles is None:
            self.load_tabs()
        else:
            self.browser_type = tab_handles.get("browser_type", "chrome")
            self.managed_tabs = tab_handles.get("managed_tabs", [])
            self.scheduled_refreshes = tab_handles.get("scheduled_refreshes", {})
            self._tab_scheduled_refreshes = self.scheduled_refreshes.copy()  # 내부 변수 초기화
    
    def get_tab_handles(self):
        """현재 탭 설정 반환"""
        return {
            "browser_type": self.browser_type,
            "managed_tabs": self.managed_tabs,
            "scheduled_refreshes": self.scheduled_refreshes
        }
    
    def load_tabs(self):
        """탭 정보 로드"""
        try:
            if os.path.exists(self.tab_info_file):
                with open(self.tab_info_file, 'r', encoding='utf-8') as f:
                    tab_data = json.load(f)
                    self.browser_type = tab_data.get("browser_type", "chrome")
                    self.managed_tabs = tab_data.get("managed_tabs", [])
                    self.scheduled_refreshes = tab_data.get("scheduled_refreshes", {})
                    self._tab_scheduled_refreshes = self.scheduled_refreshes.copy()  # 내부 변수 초기화
                    
                    # 시작 시 과거 시간 정리
                    self._clean_past_scheduled_times()
                    
                    logger.info(f"{len(self.managed_tabs)}개의 탭 정보를 로드했습니다.")
        except Exception as e:
            logger.error(f"탭 정보 로드 오류: {e}")
            # 기본값 설정
            self.browser_type = "chrome"
            self.managed_tabs = []
            self.scheduled_refreshes = {}
            self._tab_scheduled_refreshes = {}
    
    def _clean_past_scheduled_times(self):
        """현재 시간보다 이전 시간을 모두 정리합니다."""
        try:
            # 현재 시간 가져오기
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            cleaned_tabs = 0
            cleaned_times = 0
            
            # 모든 탭의 예약 시간 확인
            for tab_id_str, times in list(self.scheduled_refreshes.items()):
                if not times or not isinstance(times, list):
                    continue
                
                valid_times = []
                for time_str in times:
                    try:
                        # 시간 형식 분석
                        if len(time_str) == 5:  # HH:MM 형식
                            scheduled_h, scheduled_m = map(int, time_str.split(":"))
                            # 미래 시간만 유효하게 처리
                            if (scheduled_h > current_hour) or (scheduled_h == current_hour and scheduled_m > current_minute):
                                valid_times.append(time_str)
                            else:
                                cleaned_times += 1
                        elif len(time_str) == 8:  # HH:MM:SS 형식
                            scheduled_h, scheduled_m, _ = map(int, time_str.split(":"))
                            # 미래 시간만 유효하게 처리
                            if (scheduled_h > current_hour) or (scheduled_h == current_hour and scheduled_m > current_minute):
                                valid_times.append(time_str)
                            else:
                                cleaned_times += 1
                    except (ValueError, TypeError):
                        # 잘못된 형식은 무시
                        continue
                
                # 유효한 시간만 저장하거나 빈 목록이면 해당 탭 제거
                if valid_times:
                    self.scheduled_refreshes[tab_id_str] = valid_times
                else:
                    self.scheduled_refreshes.pop(tab_id_str)
                    cleaned_tabs += 1
            
            if cleaned_times > 0 or cleaned_tabs > 0:
                logger.info(f"시작 시 정리: {cleaned_times}개의 과거 시간 제거, {cleaned_tabs}개의 빈 탭 제거")
                self.save_tabs()
            
            # 내부 변수 동기화
            self._tab_scheduled_refreshes = self.scheduled_refreshes.copy()
                
        except Exception as e:
            logger.error(f"과거 시간 정리 중 오류: {e}", exc_info=True)
    
    def save_tabs(self):
        """탭 정보 저장"""
        try:
            # 재귀적 호출과 데드락 방지를 위해 락 사용 패턴 개선
            # 락 획득 시도
            lock_acquired = self.tab_lock.acquire(timeout=2.0)
            if not lock_acquired:
                logger.warning("탭 정보 저장 시 락 획득 실패, 락 없이 진행합니다.")
            
            try:
                # 내부 변수 간 동기화 - 간소화
                if hasattr(self, '_tab_scheduled_refreshes'):
                    # 변수 간 동기화를 단방향으로 수행 (단순화)
                    self.scheduled_refreshes = {}
                    for window_id, times in self._tab_scheduled_refreshes.items():
                        if isinstance(times, list) and times:  # 비어있지 않은 유효한 목록만 저장
                            self.scheduled_refreshes[window_id] = times.copy()
                
                # 저장할 데이터 구성
                tab_data = {
                    "browser_type": self.browser_type,
                    "managed_tabs": self.managed_tabs,
                    "scheduled_refreshes": self.scheduled_refreshes
                }
                
                # 안전한 파일 저장 (임시 파일 사용)
                import os
                temp_file = self.tab_info_file + ".tmp"
                try:
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(tab_data, f, ensure_ascii=False, indent=2)
                    
                    # 임시 파일을 실제 파일로 이동 (원자적 연산)
                    if os.path.exists(temp_file):
                        if os.path.exists(self.tab_info_file):
                            os.replace(temp_file, self.tab_info_file)  # 원자적 대체 작업
                        else:
                            os.rename(temp_file, self.tab_info_file)
                        
                        logger.info(f"{len(self.managed_tabs)}개의 탭 정보를 저장했습니다.")
                        return True
                except Exception as e:
                    logger.error(f"파일 저장 중 오류: {e}", exc_info=True)
                    # 임시 파일 정리 시도
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    return False
            finally:
                # 락 해제 (획득했을 경우에만)
                if lock_acquired:
                    self.tab_lock.release()
            
        except Exception as e:
            logger.error(f"탭 정보 저장 오류: {e}", exc_info=True)
            return False
    
    def get_browser_windows(self):
        """현재 열려있는 브라우저 창 목록 반환"""
        if self.system == "Windows":
            return self._windows_get_browser_windows()
        elif self.system == "Darwin":  # macOS
            return self._macos_get_browser_windows()
        else:  # Linux 등
            return self._linux_get_browser_windows()
    
    def _windows_get_browser_windows(self):
        """Windows에서 브라우저 창 목록 가져오기"""
        browser_windows = []
        
        try:
            # pywin32로 열린 창 목록 가져오기
            import win32gui
            
            # 브라우저 타입별 제목에 포함될 문자열 지정
            browser_identifiers = {
                "chrome": ["Chrome"],
                "firefox": ["Firefox", "Mozilla"],
                "edge": ["Edge", "Microsoft Edge"],
                "safari": ["Safari"]
            }
            
            current_identifiers = browser_identifiers.get(self.browser_type.lower(), [])
            if not current_identifiers:
                raise ValueError(f"지원하지 않는 브라우저 타입: {self.browser_type}")
            
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        window_title = win32gui.GetWindowText(hwnd)
                        if window_title and any(ident in window_title for ident in current_identifiers):
                            # 브라우저가 맞으면 목록에 추가
                            window_info = {
                                "title": window_title,
                                "id": hwnd,
                                "name": self._extract_tab_name(window_title),
                                "url": window_title  # URL 정보 없음, 제목으로 대체
                            }
                            # URL이 있는 경우 (고급 기능)
                            try:
                                # 추가 윈도우 관련 정보 가져오기 가능
                                pass
                            except:
                                pass
                            windows.append(window_info)
                    except Exception as e:
                        logger.error(f"창 정보 가져오기 오류: {e}")
            
            win32gui.EnumWindows(enum_windows_callback, browser_windows)
            
            # Chrome, Edge는 추가적인 탭 정보 처리를 시도
            if self.browser_type.lower() in ["chrome", "edge"]:
                try:
                    # Chrome 디버깅 프로토콜 연결 시도
                    import json
                    import socket
                    import os
                    import subprocess
                    import psutil
                    import time
                    
                    # 기존 창 정보 저장
                    existing_ids = set(win.get("id") for win in browser_windows)
                    
                    # 탭 정보 가져오기 시도
                    # Chrome 디버깅 포트 연결 정보 확인
                    debug_ports = []
                    
                    # 브라우저 프로세스 확인
                    browser_exe = "chrome.exe" if self.browser_type.lower() == "chrome" else "msedge.exe"
                    
                    # 열린 브라우저 프로세스 찾기
                    for proc in psutil.process_iter(['pid', 'name']):
                        try:
                            if browser_exe.lower() in proc.info['name'].lower():
                                # 추가 포트 정보 저장
                                debug_ports.append(9222)  # 기본 디버깅 포트
                        except:
                            pass
                    
                    # 각 디버깅 포트에 연결 시도
                    for port in debug_ports:
                        try:
                            # HTTP로 탭 정보 요청
                            import urllib.request
                            req = urllib.request.Request(f"http://localhost:{port}/json/list")
                            with urllib.request.urlopen(req, timeout=1.0) as response:
                                tabs_json = response.read().decode('utf-8')
                                tabs = json.loads(tabs_json)
                                
                                # 각 탭 정보 처리
                                for idx, tab in enumerate(tabs):
                                    if 'title' in tab and 'url' in tab:
                                        # 중복 ID 방지를 위한 고유 ID 생성
                                        unique_id = 90000 + idx  # 임의의 큰 수에서 시작
                                        
                                        # 이미 등록된 창과 중복 확인
                                        if unique_id not in existing_ids:
                                            browser_windows.append({
                                                "title": tab['title'],
                                                "id": unique_id,
                                                "name": self._extract_tab_name(tab['title']),
                                                "url": tab['url']
                                            })
                        except Exception as e:
                            logger.debug(f"탭 정보 가져오기 오류(포트 {port}): {e}")
                except Exception as e:
                    logger.debug(f"확장 탭 정보 가져오기 실패: {e}")
            
            logger.info(f"{len(browser_windows)}개의 {self.browser_type} 브라우저 탭을 찾았습니다.")
        except Exception as e:
            logger.error(f"Windows 브라우저 창 탐색 오류: {e}")
            
            # 실패했을 경우 더미 데이터 생성 (디버깅/테스트용)
            dummy_titles = {
                "chrome": ["Google", "GitHub", "Stack Overflow", "YouTube"],
                "firefox": ["Mozilla", "Firefox", "MDN", "Add-ons"],
                "edge": ["Bing", "Microsoft", "Office", "Azure"],
                "safari": ["Apple", "iCloud", "Safari", "Mac"]
            }
            
            browser_name = {
                "chrome": "Google Chrome",
                "firefox": "Mozilla Firefox",
                "edge": "Microsoft Edge",
                "safari": "Safari"
            }.get(self.browser_type.lower(), self.browser_type)
            
            titles = dummy_titles.get(self.browser_type.lower(), ["Test 1", "Test 2", "Test 3", "Test 4"])
            
            for i, title in enumerate(titles):
                browser_windows.append({
                    "title": f"{title} - {browser_name}",
                    "id": 2000 + i,
                    "name": title,
                    "url": f"https://{title.lower()}.com"  # 더미 URL
                })
            
            logger.info(f"생성된 테스트 창 {len(browser_windows)}개")
        
        return browser_windows
    
    def _macos_get_browser_windows(self):
        """macOS에서 브라우저 창 목록 가져오기"""
        browser_windows = []
        
        try:
            import subprocess
            import json
            import os
            import tempfile
            
            # macOS에서 AppleScript 사용하여 브라우저 창 정보 가져오기
            browser_app_name = {
                "chrome": "Google Chrome",
                "firefox": "Firefox",
                "edge": "Microsoft Edge",
                "safari": "Safari"
            }.get(self.browser_type.lower(), self.browser_type)
            
            # 실행 중인 프로세스 확인
            try:
                ps_cmd = ["ps", "aux"]
                ps_output = subprocess.check_output(ps_cmd).decode('utf-8')
                
                if self.browser_type.lower() not in ps_output.lower() and browser_app_name.lower() not in ps_output.lower():
                    logger.warning(f"{browser_app_name} 브라우저가 실행 중이지 않은 것으로 보입니다.")
            except Exception as e:
                logger.debug(f"프로세스 확인 중 오류: {e}")
            
            # Safari 브라우저인 경우 먼저 간단한 방법으로 시도
            if self.browser_type.lower() == "safari":
                logger.info("Safari 탭 가져오기 시도")
                simple_script = '''
                tell application "System Events"
                    set safariRunning to exists process "Safari"
                end tell
                
                if safariRunning then
                    tell application "Safari"
                        set windowInfo to ""
                        set windowCount to count windows
                        
                        repeat with w from 1 to windowCount
                            set currentWindow to window w
                            try
                                set tabCount to count tabs of currentWindow
                                repeat with t from 1 to tabCount
                                    set currentTab to tab t of currentWindow
                                    try
                                        set tabTitle to name of currentTab
                                        set uniqueId to ((w * 1000) + t)
                                        set windowInfo to windowInfo & uniqueId & "|" & tabTitle & "|Safari\\n"
                                    end try
                                end repeat
                            end try
                        end repeat
                        
                        return windowInfo
                    end tell
                else
                    return "Safari is not running"
                end if
                '''
                
                result = self._run_applescript(simple_script)
                if result and "not running" not in result and result.strip():
                    lines = result.strip().split('\n')
                    for line in lines:
                        if not line.strip():
                            continue
                            
                        parts = line.split('|', 2)
                        if len(parts) >= 2:
                            try:
                                win_id = int(parts[0].strip())
                                title = parts[1].strip()
                                
                                browser_windows.append({
                                    "id": win_id,
                                    "title": title + " - Safari",
                                    "name": title,
                                    "url": parts[2].strip() if len(parts) > 2 else title,
                                    "browser_type": "safari"  # 브라우저 타입 명시적 추가
                                })
                            except ValueError:
                                continue
                
                # Safari 탭을 찾았으면 바로 반환
                if browser_windows:
                    logger.info(f"{len(browser_windows)}개의 Safari 탭을 찾았습니다.")
                    return browser_windows
            
            # 방법 1: AppleScript로 브라우저 창/탭 가져오기 - 임시 파일 방식
            try:
                # 각 브라우저에 맞는 AppleScript 준비
                applescript = ""
                
                if self.browser_type.lower() == "chrome":
                    applescript = f'''
                    tell application "{browser_app_name}"
                        set windowList to ""
                        set windowCount to count windows
                        repeat with w from 1 to windowCount
                            set current_window to window w
                            set tabCount to count tabs of current_window
                            repeat with t from 1 to tabCount
                                set current_tab to tab t of current_window
                                set tabUrl to URL of current_tab
                                set tabTitle to title of current_tab
                                set uniqueId to ((w * 1000) + t) as string
                                set windowList to windowList & uniqueId & "|" & tabTitle & "|" & tabUrl & "\\n"
                            end repeat
                        end repeat
                        return windowList
                    end tell
                    '''
                elif self.browser_type.lower() == "safari":
                    applescript = f'''
                    tell application "{browser_app_name}"
                        set windowList to ""
                        set windowCount to count windows
                        repeat with w from 1 to windowCount
                            set current_window to window w
                            set tabCount to count tabs of current_window
                            repeat with t from 1 to tabCount
                                set current_tab to tab t of current_window
                                try
                                    set tabUrl to URL of current_tab
                                on error
                                    set tabUrl to "unknown"
                                end try
                                try
                                    set tabTitle to name of current_tab
                                on error
                                    set tabTitle to "Safari Tab " & t
                                end try
                                set uniqueId to ((w * 1000) + t) as string
                                set windowList to windowList & uniqueId & "|" & tabTitle & "|" & tabUrl & "\\n"
                            end repeat
                        end repeat
                        return windowList
                    end tell
                    '''
                elif self.browser_type.lower() == "firefox":
                    # Firefox는 각 창의 제목에 현재 활성화된 탭 정보가 포함됨
                    # 여기서는 각 창에서 활성화된 탭을 가져와 별도의 항목으로 처리
                    applescript = f'''
                    tell application "System Events"
                        set firefoxRunning to exists process "Firefox"
                    end tell
                    
                    if firefoxRunning then
                        tell application "{browser_app_name}"
                            set windowList to ""
                            set windowCount to count windows
                            
                            repeat with w from 1 to windowCount
                                set current_window to window w
                                
                                if w is active window's index then
                                    -- 활성 창에서는 Firefox의 현재 탭 가져오기
                                    set windowTitle to name of current_window
                                    set uniqueId to (w * 1000) as string
                                    
                                    -- 제목에서 " - Mozilla Firefox" 부분 제거
                                    if windowTitle ends with " - Mozilla Firefox" then
                                        set tabTitle to text 1 thru -18 of windowTitle
                                    else
                                        set tabTitle to windowTitle
                                    end if
                                    
                                    -- 파이어폭스 창에서 여러 탭 처리 (단순화)
                                    repeat with t from 1 to 5  -- 최대 5개 탭 처리 (가정)
                                        set tabId to ((w * 1000) + t) as string
                                        set tabName to tabTitle & " (탭 " & t & ")"
                                        set windowList to windowList & tabId & "|" & tabName & "|Firefox\\n"
                                    end repeat
                                else
                                    set windowTitle to name of current_window
                                    set uniqueId to (w * 1000) as string
                                    
                                    -- 제목에서 " - Mozilla Firefox" 부분 제거
                                    if windowTitle ends with " - Mozilla Firefox" then
                                        set tabTitle to text 1 thru -18 of windowTitle
                                    else
                                        set tabTitle to windowTitle
                                    end if
                                    
                                    set windowList to windowList & uniqueId & "|" & tabTitle & "|Firefox\\n"
                                end if
                            end repeat
                            
                            return windowList
                        end tell
                    else
                        return "Firefox is not running"
                    end if
                    '''
                elif self.browser_type.lower() == "edge":
                    applescript = f'''
                    tell application "{browser_app_name}"
                        set windowList to ""
                        set windowCount to count windows
                        repeat with w from 1 to windowCount
                            set current_window to window w
                            set tabCount to count tabs of current_window
                            repeat with t from 1 to tabCount
                                set current_tab to tab t of current_window
                                set tabUrl to URL of current_tab
                                set tabTitle to title of current_tab
                                set uniqueId to ((w * 1000) + t) as string
                                set windowList to windowList & uniqueId & "|" & tabTitle & "|" & tabUrl & "\\n"
                            end repeat
                        end repeat
                        return windowList
                    end tell
                    '''
                
                if applescript:
                    # 임시 파일에 스크립트 저장
                    with tempfile.NamedTemporaryFile(suffix='.scpt', delete=False) as temp:
                        temp_path = temp.name
                        temp.write(applescript.encode('utf-8'))
                    
                    # AppleScript 실행
                    cmd = ["osascript", temp_path]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = process.communicate(timeout=10)
                    
                    # 임시 파일 삭제
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    
                    if process.returncode == 0:
                        result = stdout.decode('utf-8').strip()
                        
                        if result:
                            lines = result.strip().split('\n')
                            for line in lines:
                                if not line.strip():
                                    continue
                                    
                                parts = line.split('|', 2)
                                if len(parts) >= 2:
                                    win_id = parts[0].strip()
                                    
                                    # ID를 정수로 변환 시도
                                    try:
                                        win_id = int(win_id)
                                    except ValueError:
                                        # 정수로 변환할 수 없으면 해시값 사용
                                        win_id = hash(win_id) % 10000
                                    
                                    title = parts[1].strip()
                                    url = parts[2].strip() if len(parts) > 2 else title
                                    
                                    browser_windows.append({
                                        "id": win_id,
                                        "title": title + f" - {self.browser_type.capitalize()}",
                                        "name": title,
                                        "url": url,
                                        "browser_type": self.browser_type  # 브라우저 타입 명시적 추가
                                    })
            except Exception as e:
                logger.error(f"AppleScript 실행 중 오류: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"macOS 브라우저 창 정보 가져오기 오류: {e}", exc_info=True)
        
        # 창을 찾지 못한 경우 테스트 데이터 생성
        if not browser_windows:
            logger.warning(f"{self.browser_type} 브라우저 창을 찾지 못했습니다. 테스트 데이터를 생성합니다.")
            
            # 테스트용 데이터 3개 생성
            for i in range(1, 4):
                title = f"테스트 탭 {i} ({self.browser_type})"
                browser_windows.append({
                    "id": (i * 1000) + i,
                    "title": title + f" - {self.browser_type.capitalize()}",
                    "name": title,
                    "url": f"https://{title.lower().replace(' ', '-')}.com",
                    "browser_type": self.browser_type  # 브라우저 타입 명시적 추가
                })
        
        logger.info(f"{len(browser_windows)}개의 {self.browser_type} 브라우저 탭을 찾았습니다.")
        return browser_windows
    
    def _linux_get_browser_windows(self):
        """Linux에서 브라우저 창 목록 가져오기"""
        browser_windows = []
        
        try:
            # Linux에서는 xdotool 또는 wnck를 사용하여 창 목록 가져오기
            import subprocess
            import json
            
            # 기본 브라우저 프로세스 이름 매핑
            browser_process = {
                "chrome": ["chrome", "chromium", "google-chrome", "chromium-browser"],
                "firefox": ["firefox", "firefox-esr"],
                "edge": ["microsoft-edge", "msedge"],
                "safari": ["safari"]  # 리눅스에는 Safari가 없지만 호환성을 위해 유지
            }.get(self.browser_type.lower(), [self.browser_type.lower()])
            
            # 방법 1: xdotool 사용하여 창 목록 가져오기
            try:
                # 브라우저 프로세스에 해당하는 창 ID 목록 가져오기
                window_ids = []
                for proc_name in browser_process:
                    try:
                        result = subprocess.run(
                            ["xdotool", "search", "--class", proc_name], 
                            capture_output=True, text=True, timeout=3
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            window_ids.extend(result.stdout.strip().split('\n'))
                    except:
                        pass
                
                # 각 창 정보 가져오기
                for win_id in window_ids:
                    try:
                        win_id = win_id.strip()
                        if not win_id:
                            continue
                            
                        # 창 제목 가져오기
                        get_title = subprocess.run(
                            ["xdotool", "getwindowname", win_id], 
                            capture_output=True, text=True, timeout=1
                        )
                        title = get_title.stdout.strip()
                        
                        # 브라우저 탭 제목이 맞는지 확인
                        if (self.browser_type.lower() == "chrome" and any(x in title.lower() for x in ["chrome", "chromium"])) or \
                           (self.browser_type.lower() == "firefox" and "firefox" in title.lower()) or \
                           (self.browser_type.lower() == "edge" and "edge" in title.lower()):
                            
                            browser_windows.append({
                                "title": title,
                                "id": int(win_id),
                                "name": self._extract_tab_name(title),
                                "url": title  # URL 정보 없음, 제목으로 대체
                            })
                    except Exception as e:
                        logger.debug(f"창 정보 가져오기 오류(ID: {win_id}): {e}")
            except Exception as e:
                logger.debug(f"xdotool 방식 오류: {e}")
            
            # 방법 2: Chrome/Chromium 디버깅 프로토콜 사용
            if self.browser_type.lower() in ["chrome", "chromium", "edge"] and not browser_windows:
                try:
                    # 기존 창 ID들 저장
                    existing_ids = set(win.get("id") for win in browser_windows)
                    
                    # 디버깅 포트 연결 시도
                    import urllib.request
                    import json
                    
                    for port in [9222, 9223, 9224]:  # 일반적인 디버깅 포트
                        try:
                            req = urllib.request.Request(f"http://localhost:{port}/json/list")
                            with urllib.request.urlopen(req, timeout=1.0) as response:
                                tabs_json = response.read().decode('utf-8')
                                tabs = json.loads(tabs_json)
                                
                                for idx, tab in enumerate(tabs):
                                    if 'title' in tab and 'url' in tab:
                                        unique_id = 90000 + idx  # 임의의 큰 수에서 시작
                                        
                                        if unique_id not in existing_ids:
                                            browser_windows.append({
                                                "title": tab['title'],
                                                "id": unique_id,
                                                "name": self._extract_tab_name(tab['title']),
                                                "url": tab['url']
                                            })
                        except Exception as e:
                            logger.debug(f"디버깅 포트 연결 오류(포트: {port}): {e}")
                except Exception as e:
                    logger.debug(f"Chrome 디버깅 프로토콜 방식 오류: {e}")
            
            # 방법 3: Firefox는 Native Messaging으로 시도
            if self.browser_type.lower() == "firefox" and not browser_windows:
                try:
                    # Firefox 탭 정보 가져오기 시도
                    # (Firefox는 Native Messaging API를 사용하거나 확장 프로그램이 필요할 수 있음)
                    pass
                except Exception as e:
                    logger.debug(f"Firefox 탭 정보 가져오기 오류: {e}")
            
            logger.info(f"{len(browser_windows)}개의 {self.browser_type} 브라우저 탭을 찾았습니다.")
            
        except Exception as e:
            logger.error(f"Linux 브라우저 창 탐색 오류: {e}")
            
            # 실패했을 경우 더미 데이터 생성 (디버깅/테스트용)
            dummy_titles = {
                "chrome": ["Google", "GitHub", "Stack Overflow", "YouTube"],
                "firefox": ["Mozilla", "Firefox", "MDN", "Add-ons"],
                "edge": ["Bing", "Microsoft", "Office", "Azure"],
                "safari": ["Apple", "iCloud", "Safari", "Mac"]
            }
            
            browser_name = {
                "chrome": "Google Chrome",
                "firefox": "Mozilla Firefox",
                "edge": "Microsoft Edge",
                "safari": "Safari"
            }.get(self.browser_type.lower(), self.browser_type)
            
            titles = dummy_titles.get(self.browser_type.lower(), ["Test 1", "Test 2", "Test 3", "Test 4"])
            
            for i, title in enumerate(titles):
                browser_windows.append({
                    "title": f"{title} - {browser_name}",
                    "id": 2000 + i,
                    "name": title,
                    "url": f"https://{title.lower()}.com"  # 더미 URL
                })
            
            logger.info(f"생성된 테스트 창 {len(browser_windows)}개")
        
        return browser_windows
    
    def _run_applescript(self, script, timeout=5):
        """AppleScript 실행 (타임아웃 설정 추가)"""
        if self.system != "Darwin":  # macOS가 아닌 경우
            return None
            
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(suffix='.scpt', delete=False) as tf:
                script_file = tf.name
                tf.write(script.encode('utf-8'))
            
            # 명령 실행 (타임아웃 설정)
            process = subprocess.Popen(['osascript', script_file], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE)
            
            # 타임아웃과 함께 프로세스 완료 대기
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                
                # 임시 파일 삭제
                try:
                    os.unlink(script_file)
                except:
                    pass
                    
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8')
                    logger.error(f"AppleScript 오류: {error_msg}")
                    return error_msg  # 오류 메시지 반환 (조건부 처리를 위함)
                    
                return stdout.decode('utf-8').strip()
                
            except subprocess.TimeoutExpired:
                # 타임아웃 발생 시 프로세스 강제 종료
                process.kill()
                logger.warning(f"AppleScript 실행 타임아웃 ({timeout}초)")
                
                # 임시 파일 삭제 시도
                try:
                    os.unlink(script_file)
                except:
                    pass
                    
                return None
                
        except Exception as e:
            logger.error(f"AppleScript 실행 오류: {e}")
            return None
    
    def _is_chrome_window(self, title):
        """Chrome 브라우저 창인지 확인"""
        return " - Google Chrome" in title

    def _is_firefox_window(self, title):
        """Firefox 브라우저 창인지 확인"""
        return " - Mozilla Firefox" in title

    def _is_edge_window(self, title):
        """Edge 브라우저 창인지 확인"""
        return " - Microsoft Edge" in title

    def _is_safari_window(self, title):
        """Safari 브라우저 창인지 확인"""
        return " - Safari" in title or "Safari" in title
    
    def _extract_tab_name(self, title):
        """창 제목에서 탭 이름 추출"""
        # 브라우저 이름 부분 제거
        if " - Chrome" in title:
            return title.split(" - Chrome")[0].strip()
        elif " - Google Chrome" in title:
            return title.split(" - Google Chrome")[0].strip()
        elif " - Microsoft Edge" in title:
            return title.split(" - Microsoft Edge")[0].strip()
        elif " - Edge" in title:
            return title.split(" - Edge")[0].strip()
        elif " - Safari" in title:
            return title.split(" - Safari")[0].strip()
        elif " - " in title:
            # 대부분의 브라우저는 "페이지 제목 - 브라우저 이름" 형식 사용
            return title.split(" - ")[0].strip()
        return title.strip()
    
    def add_tab(self, window_id, tab_title, browser_type="chrome"):
        """특정 브라우저의 탭을 관리 목록에 추가"""
        with self.tab_lock:
            try:
                logger.info(f"탭 추가 시도: ID={window_id}, 제목={tab_title}, 브라우저={browser_type}")
                
                # ID 정규화 - 항상 정수로 저장
                try:
                    if not isinstance(window_id, int):
                        converted_id = int(window_id)
                    else:
                        converted_id = window_id
                except (ValueError, TypeError):
                    # 정수 변환 실패 시 고유한 해시 ID 생성
                    timestamp = int(time.time())
                    converted_id = abs(hash(f"{browser_type}_{tab_title}_{timestamp}")) % 100000
                    logger.info(f"ID 변환 실패, 해시 ID 생성: {converted_id}")
                
                # 중복 검사 (정확히 같은 ID의 같은 브라우저 탭만 중복으로 처리)
                duplicate_found = False
                for tab in self.managed_tabs:
                    if tab.get('id') == converted_id and tab.get('browser_type') == browser_type:
                        logger.warning(f"이미 추가된 탭: ID={converted_id}, 이름={tab_title}, 브라우저={browser_type}")
                        duplicate_found = True
                        break
                
                if duplicate_found:
                    return False
                
                # 새 탭 추가 (ID를 정수형으로 저장)
                tab_info = {
                    'id': converted_id,
                    'name': tab_title,
                    'browser_type': browser_type
                }
                
                self.managed_tabs.append(tab_info)
                logger.info(f"탭 추가 성공: {tab_info}")
                self.save_tabs()  # 변경사항 저장
                return True
                
            except Exception as e:
                logger.error(f"탭 추가 중 오류 발생: {e}", exc_info=True)
                return False
    
    def remove_tab(self, window_id):
        """관리 탭 제거"""
        for i, tab in enumerate(self.managed_tabs):
            if tab["id"] == window_id:
                self.managed_tabs.pop(i)
                self.save_tabs()
                return True
        return False
    
    def refresh_tab(self, window_id, browser_already_running=False):
        """특정 탭 새로고침"""
        # 명확한 디버깅을 위한 로깅 추가
        logger.info(f"탭 리프레시 시작 - ID: {window_id}")
        
        # 관리 탭에서 해당 window_id를 가진 탭 정보 찾기
        tab_info = None
        for tab in self.managed_tabs:
            if str(tab["id"]) == str(window_id):
                tab_info = tab
                break
        
        # 탭을 찾지 못한 경우
        if tab_info is None:
            logger.warning(f"ID {window_id}인 탭을 찾을 수 없습니다. 대체 방법 시도...")
            
            # 대체 방법: window_id로 직접 새로고침 시도
            browser_type = self.browser_type
            
            # 문자열 ID를 정수로 변환 (안전한 방식으로)
            try:
                window_id_int = int(window_id)
            except (ValueError, TypeError):
                window_id_int = 0
                logger.warning(f"ID를 정수로 변환할 수 없음: {window_id}")
                
            # 추측: ID 패턴이 1000 이상이면 Chrome/Safari 방식일 가능성이 높음
            if window_id_int >= 1000:
                # ID 패턴에 따라 브라우저 타입 추측
                if window_id_int % 1000 == 1:  # 종종 Firefox/Safari 패턴
                    if "firefox" in self.browser_type.lower():
                        browser_type = "firefox"
                    elif "safari" in self.browser_type.lower():
                        browser_type = "safari"
                else:  # Chrome/Edge 패턴일 가능성이 높음
                    if "chrome" in self.browser_type.lower():
                        browser_type = "chrome"
                    elif "edge" in self.browser_type.lower():
                        browser_type = "edge"
            
            logger.info(f"탭을 찾지 못했지만 ID {window_id}와 브라우저 타입 {browser_type}으로 새로고침 시도")
        else:
            # 탭 정보에 browser_type 필드가 있으면 그 값 사용, 없으면 현재 browser_type 사용
            browser_type = tab_info.get("browser_type", self.browser_type)
            logger.info(f"탭 '{tab_info['name']}' (ID: {window_id}, 브라우저: {browser_type}) 새로고침 시도")
        
        # OS별 처리 로직
        refresh_result = False
        if self.system == "Windows":
            refresh_result = self._windows_refresh_tab(window_id, browser_type)
        elif self.system == "Darwin":  # macOS
            refresh_result = self._macos_refresh_tab(window_id, browser_type, browser_already_running)
        else:  # Linux 등
            # 테스트 목적으로 성공 반환
            logger.info(f"탭 ID {window_id} (테스트) 새로고침 완료")
            refresh_result = True
            
        # 결과 로깅
        if refresh_result:
            logger.info(f"탭 ID {window_id} 새로고침 성공")
        else:
            logger.warning(f"탭 ID {window_id} 새로고침 실패")
            
        return refresh_result
    
    def _windows_refresh_tab(self, window_id, browser_type=None):
        """Windows에서 탭 새로고침"""
        if browser_type is None:
            browser_type = self.browser_type
        
        try:
            # 창 목록에서 일치하는 ID 찾기
            all_windows = gw.getAllWindows()
            target_window = None
            
            for window in all_windows:
                if window._hWnd == window_id:
                    target_window = window
                    break
            
            if target_window is None:
                logger.warning(f"ID {window_id}인 창을 찾을 수 없습니다.")
                return False
            
            # 창을 활성화하고 F5 키 입력 보내기
            try:
                target_window.activate()
                time.sleep(0.2)  # 창이 활성화될 때까지 짧게 대기
                pyautogui.press('f5')
                time.sleep(0.1)  # 키 입력 후 잠시 대기
                
                logger.info(f"탭 '{target_window.title}' 새로고침 완료")
                return True
            except Exception as e:
                logger.error(f"창 활성화 및 키 입력 오류: {e}")
                # 대체 방법: 마우스로 창 클릭 후 F5 누르기
                try:
                    x, y = target_window.left + target_window.width // 2, target_window.top + 20
                    pyautogui.click(x, y)
                    time.sleep(0.2)
                    pyautogui.press('f5')
                    logger.info(f"대체 방법으로 탭 새로고침 완료")
                    return True
                except:
                    return False
        except Exception as e:
            logger.error(f"Windows 탭 새로고침 오류: {e}")
            return False
    
    def _macos_refresh_tab(self, window_id, browser_type=None, browser_already_running=False):
        """macOS에서 AppleScript로 탭 새로고침"""
        # 브라우저 타입 설정 (매개변수로 받거나 탭 정보에서 가져오기)
        if browser_type is None:
            browser_type = self._get_tab_browser_type(window_id)
        
        browser_type = browser_type.lower()
        
        # 디버그 정보 추가
        logger.info(f"[macOS] 탭 새로고침 시작 - ID: {window_id}, 브라우저: {browser_type}")
        
        # Safari는 별도 처리
        if browser_type == "safari":
            return self._macos_refresh_safari_tab(window_id)
        
        # 기타 브라우저(Chrome, Firefox, Edge) 처리
        try:
            # 브라우저 이름 결정
            browser_names = {
                "chrome": "Google Chrome",
                "firefox": "Firefox",
                "edge": "Microsoft Edge"
            }
            browser_name = browser_names.get(browser_type, "Google Chrome")
            
            # 문자열 ID를 정수로 변환 (안전한 방식으로)
            try:
                window_id_int = int(window_id)
            except (ValueError, TypeError):
                window_id_int = window_id  # 변환 실패 시 원래 값 유지
                logger.warning(f"[macOS] ID 변환 실패: {window_id} -> 문자열로 처리")
            
            # 브라우저 실행 여부 확인
            if not browser_already_running:
                check_script = f'''
                tell application "System Events"
                    set isRunning to exists process "{browser_name}"
                end tell
                '''
                check_result = self._run_applescript(check_script, timeout=2)
                
                browser_running = check_result and "true" in check_result.lower()
                if not browser_running:
                    logger.warning(f"{browser_name} 브라우저가 실행 중이지 않습니다. 실행을 시도합니다.")
                    
                    # 브라우저 시작
                    launch_script = f'''
                    tell application "{browser_name}"
                        activate
                        delay 0.5
                    end tell
                    return "Browser launched"
                    '''
                    launch_result = self._run_applescript(launch_script, timeout=5)
                    logger.info(f"브라우저 실행 결과: {launch_result}")
                    
                    # 브라우저가 시작될 때까지 짧게 대기
                    time.sleep(1.0)
            
            # 새로고침 방법 1: 고급 AppleScript 시도 - 인덱스 기반 정밀 접근
            logger.info(f"[macOS] {browser_name} 탭({window_id}) 새로고침 시도 (방법 1)")
            
            # 인덱스 기반 새로고침 (ID 기반보다 안정적)
            access_script = f'''
            tell application "{browser_name}"
                set windowCount to count of windows
                if windowCount is 0 then
                    return "Error: No windows open"
                end if
                
                set found to false
                set window_index to 0
                
                # 먼저 ID로 창 찾기 시도
                repeat with i from 1 to windowCount
                    if id of window i is {window_id_int} then
                        set window_index to i
                        set found to true
                        exit repeat
                    end if
                end repeat
                
                # ID로 찾지 못한 경우 창 ID가 숫자 체계를 따르는지 확인
                if not found then
                    # 창 ID가 2001, 3001 등의 패턴인 경우 해당 인덱스 사용
                    if {window_id_int} > 1000 then
                        set possible_index to {window_id_int} div 1000
                        if possible_index <= windowCount then
                            set window_index to possible_index
                            set found to true
                        end if
                    end if
                end if
                
                # 그래도 찾지 못한 경우 첫 번째 창 사용
                if not found then
                    set window_index to 1
                end if
                
                # 탭 새로고침 수행
                set tab_index to 1
                if {window_id_int} mod 1000 > 0 then
                    set tab_index to {window_id_int} mod 1000
                end if
                
                try
                    set total_tabs to count of tabs of window window_index
                    if tab_index > total_tabs then
                        set tab_index to 1
                    end if
                    
                    tell window window_index
                        # 새로고침할 탭 활성화 후 새로고침
                        set active tab index to tab_index
                        tell active tab to reload
                    end tell
                    
                    return "Success: Tab refreshed. 창 " & windowCount & "개 발견. 창 인덱스 " & window_index & ", 탭 인덱스 " & tab_index & " 접근 시도."
                on error errMsg
                    # 오류 발생 시 단순 명령으로 시도
                    activate
                    tell application "System Events"
                        tell process "{browser_name}"
                            keystroke "r" using {{command down}}
                        end tell
                    end tell
                    return "Success: Fallback refresh using keyboard command. Error: " & errMsg
                end try
            end tell
            '''
            
            access_result = self._run_applescript(access_script, timeout=5)
            if access_result and "Success" in access_result:
                logger.info(f"[macOS] AppleScript로 탭 새로고침 성공: {access_result}")
                return True
            else:
                logger.warning(f"[macOS] 방법 1 실패: {access_result}")
                
                # 방법 2: 단순 명령 시도 - 활성화 후 Command+R
                logger.info(f"[macOS] {browser_name} 탭 새로고침 시도 (방법 2)")
                simple_script = f'''
                tell application "{browser_name}"
                    activate
                    delay 0.3
                end tell
                tell application "System Events"
                    tell process "{browser_name}"
                        keystroke "r" using {{command down}}
                    end tell
                end tell
                return "Success: Emergency fallback refresh"
                '''
                
                simple_result = self._run_applescript(simple_script, timeout=3)
                if simple_result and "Success" in simple_result:
                    logger.info(f"[macOS] 응급 새로고침 성공: {simple_result}")
                    return True
                else:
                    # 방법 3: 가장 간단한 방법 시도
                    logger.warning(f"[macOS] 방법 2 실패: {simple_result}")
                    logger.info(f"[macOS] {browser_name} 탭 새로고침 최종 시도 (방법 3)")
                    
                    final_script = f'''
                    tell application "{browser_name}"
                        activate
                    end tell
                    delay 0.5
                    tell application "System Events" to keystroke "r" using {{command down}}
                    return "Final attempt completed"
                    '''
                    
                    final_result = self._run_applescript(final_script, timeout=2)
                    logger.info(f"[macOS] 최종 시도 결과: {final_result}")
                    return final_result is not None
                
        except Exception as e:
            logger.error(f"[macOS] 탭 새로고침 처리 중 예외 발생: {e}", exc_info=True)
            return False
    
    def _macos_refresh_safari_tab(self, window_id):
        """
        macOS에서 Safari 탭을 새로고침합니다.
        여러 방법을 사용하여 더 안정적인 새로고침 기능을 제공합니다.
        
        Args:
            window_id (int or str): Safari 탭 ID, 정수 (w*1000+t) 형식 또는 "window_index:tab_index" 형식
        
        Returns:
            bool: 성공 여부
        """
        try:
            # ID를 문자열로 변환 후 window_index와 tab_index 추출
            window_id = str(window_id)
            logger.info(f"Safari 탭 새로고침 시작: {window_id}")
            
            # window_id에서 window 및 tab 인덱스 추출
            try:
                # "window_index:tab_index" 형식 처리
                if ":" in window_id:
                    window_index, tab_index = map(int, window_id.split(":"))
                # 정수 형식 처리 (w*1000+t)
                else:
                    window_id_int = int(window_id)
                    window_index = window_id_int // 1000
                    tab_index = window_id_int % 1000
                
                logger.debug(f"Safari 창 인덱스: {window_index}, 탭 인덱스: {tab_index}")
            except ValueError:
                logger.error(f"잘못된 Safari 탭 ID 형식: {window_id}")
                return False
            
            # Safari가 실행 중인지 확인하고, 실행 중이 아니면 실행
            safari_running = self._is_browser_running("safari")
            if not safari_running:
                logger.info("Safari가 실행 중이지 않아 실행을 시도합니다.")
                self._activate_browser("safari")
                time.sleep(1)  # Safari가 시작될 때까지 잠시 대기
            
            # 방법 1: JavaScript를 사용하여 직접 페이지 새로고침 (가장 안정적)
            try:
                logger.debug("방법 1: JavaScript로 페이지 새로고침 시도")
                # AppleScript를 사용하여 Safari에 JavaScript 실행 명령
                script = f'''
                tell application "Safari"
                    set windowCount to count of windows
                    if {window_index} ≤ windowCount then
                        set theWindow to window {window_index}
                        set tabCount to count of tabs of theWindow
                        if {tab_index} ≤ tabCount then
                            set currentTab to tab {tab_index} of theWindow
                            tell currentTab
                                do JavaScript "window.location.reload(true);"
                            end tell
                            return true
                        end if
                    end if
                    return false
                end tell
                '''
                result = self._run_applescript(script)
                if result.strip().lower() == "true":
                    logger.info(f"Safari 탭 새로고침 성공 (방법 1): {window_id}")
                    return True
                else:
                    logger.debug(f"방법 1 실패, 다음 방법 시도: {result}")
            except Exception as e:
                logger.debug(f"방법 1 오류: {e}, 다음 방법 시도")
            
            # 방법 2: System Events를 사용하여 Command+R 키 입력 전송
            try:
                logger.debug("방법 2: 키보드 단축키 사용 시도")
                script = f'''
                tell application "Safari"
                    activate
                    set windowCount to count of windows
                    if {window_index} ≤ windowCount then
                        set theWindow to window {window_index}
                        set tabCount to count of tabs of theWindow
                        if {tab_index} ≤ tabCount then
                            set current tab of theWindow to tab {tab_index} of theWindow
                            delay 0.5
                        end if
                    end if
                end tell
                tell application "System Events"
                    tell process "Safari"
                        keystroke "r" using {{command down}}
                        delay 0.5
                    end tell
                end tell
                return true
                '''
                result = self._run_applescript(script)
                if result.strip().lower() == "true":
                    logger.info(f"Safari 탭 새로고침 성공 (방법 2): {window_id}")
                    return True
                else:
                    logger.debug(f"방법 2 실패, 다음 방법 시도: {result}")
            except Exception as e:
                logger.debug(f"방법 2 오류: {e}, 다음 방법 시도")
            
            # 방법 3: 현재 URL을 가져와서 다시 로드
            try:
                logger.debug("방법 3: URL 재로드 시도")
                # 현재 URL 가져오기
                url_script = f'''
                tell application "Safari"
                    set windowCount to count of windows
                    if {window_index} ≤ windowCount then
                        set theWindow to window {window_index}
                        set tabCount to count of tabs of theWindow
                        if {tab_index} ≤ tabCount then
                            set currentTab to tab {tab_index} of theWindow
                            return URL of currentTab
                        end if
                    end if
                    return ""
                end tell
                '''
                current_url = self._run_applescript(url_script).strip()
                
                if current_url and current_url != "":
                    # URL 재로드
                    reload_script = f'''
                    tell application "Safari"
                        set windowCount to count of windows
                        if {window_index} ≤ windowCount then
                            set theWindow to window {window_index}
                            set tabCount to count of tabs of theWindow
                            if {tab_index} ≤ tabCount then
                                set currentTab to tab {tab_index} of theWindow
                                set URL of currentTab to "{current_url}"
                                return true
                            end if
                        end if
                        return false
                    end tell
                    '''
                    result = self._run_applescript(reload_script)
                    if result.strip().lower() == "true":
                        logger.info(f"Safari 탭 새로고침 성공 (방법 3): {window_id}")
                        return True
                    else:
                        logger.debug(f"방법 3 실패: {result}")
                else:
                    logger.debug(f"현재 URL을 가져올 수 없음: {current_url}")
            except Exception as e:
                logger.debug(f"방법 3 오류: {e}")
            
            # 모든 방법 실패 시
            logger.error(f"Safari 탭 새로고침 실패 (모든 방법): {window_id}")
            return False
            
        except Exception as e:
            logger.error(f"Safari 탭 새로고침 중 예외 발생: {e}", exc_info=True)
            return False
    
    def refresh_tabs_parallel(self, tab_ids, max_workers=None):
        """
        여러 탭을 병렬로 새로고침합니다.
        
        Args:
            tab_ids (list): 새로고침할 탭 ID 목록
            max_workers (int, optional): 최대 동시 작업자 수. 기본값은 None(자동 결정)
            
        Returns:
            list: 각 탭의 새로고침 결과 목록
        """
        results = []
        
        # tab_ids가 비어있으면 빈 결과 반환
        if not tab_ids:
            return results
            
        try:
            # 최대 작업자 수 결정 (기본값: 탭 수 또는 CPU 수 * 2 중 작은 값)
            if max_workers is None:
                import multiprocessing
                max_workers = min(len(tab_ids), multiprocessing.cpu_count() * 2)
            
            logger.info(f"병렬 새로고침 시작: {len(tab_ids)}개 탭, 최대 작업자 {max_workers}명")
            
            # 결과를 저장할 딕셔너리 (순서 유지를 위해)
            results_dict = {}
            
            # 병렬 처리 시작
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 각 탭 ID에 대한 새로고침 작업 제출
                future_to_tab_id = {
                    executor.submit(self.refresh_tab, tab_id): tab_id for tab_id in tab_ids
                }
                
                # 완료된 작업 결과 수집
                for future in concurrent.futures.as_completed(future_to_tab_id):
                    tab_id = future_to_tab_id[future]
                    
                    try:
                        # 작업 결과 (성공 여부) 가져오기
                        success = future.result()
                        
                        # 탭 정보 가져오기
                        tab = self.get_tab_by_id(tab_id)
                        if tab:
                            tab_name = tab["name"]
                            browser_type = tab.get("browser_type", self.browser_type)
                        else:
                            # 탭 정보가 없으면 기본값 사용
                            tab_name = f"탭 {tab_id}"
                            browser_type = self.browser_type
                        
                        # 결과 저장
                        results_dict[tab_id] = {
                            "name": tab_name,
                            "browser_type": browser_type,
                            "success": success
                        }
                        
                        if success:
                            logger.info(f"병렬 새로고침 성공: {tab_name} (ID: {tab_id})")
                        else:
                            logger.warning(f"병렬 새로고침 실패: {tab_name} (ID: {tab_id})")
                            
                    except Exception as exc:
                        logger.error(f"탭 ID {tab_id} 새로고침 중 오류: {exc}")
                        # 오류가 발생해도 결과 목록에 추가
                        results_dict[tab_id] = {
                            "name": f"탭 {tab_id}",
                            "browser_type": self.browser_type,
                            "success": False
                        }
            
            # 원래 탭 ID 순서대로 결과 정렬
            for tab_id in tab_ids:
                if tab_id in results_dict:
                    results.append(results_dict[tab_id])
                    
            logger.info(f"병렬 새로고침 완료: 총 {len(results)}개 탭")
                    
        except Exception as e:
            logger.error(f"병렬 새로고침 처리 중 오류: {e}", exc_info=True)
        
        return results

    def refresh_all_tabs(self):
        """모든 관리 탭 새로고침 - 병렬 처리 방식으로 변경"""
        # 모든 탭 ID 추출
        tab_ids = [tab["id"] for tab in self.managed_tabs]
        
        # 병렬 처리 함수 호출
        return self.refresh_tabs_parallel(tab_ids)
    
    def set_browser_type(self, browser_type):
        """브라우저 타입 설정"""
        if browser_type.lower() in ["chrome", "firefox", "edge", "safari"]:
            self.browser_type = browser_type.lower()
            logger.info(f"브라우저 타입을 {browser_type}로 변경했습니다.")
            return True
        return False

    def add_scheduled_refresh(self, window_id, times):
        """특정 창에 자동 새로고침 시간을 추가합니다.
        
        Args:
            window_id: 창 ID
            times: 새로고침 시간 목록 (예: ["09:00", "15:30"])
        """
        logger.info(f"스케줄 추가 요청: 창 ID {window_id}, 시간 {times}")
        
        if not isinstance(times, list):
            if isinstance(times, str):
                times = [times]
            elif isinstance(times, bool):
                logger.warning(f"boolean 값이 시간 목록으로 전달됨: {times}")
                return
            else:
                logger.warning(f"유효하지 않은 시간 형식: {times}, 타입: {type(times)}")
                return
        
        # None 또는 빈 목록이 아닌지 확인
        if not times:
            logger.warning("빈 시간 목록이 전달됨")
            return
            
        # 정확한 시간 형식인지 확인 (HH:MM 또는 HH:MM:SS)
        validated_times = []
        for time_str in times:
            # 시간 문자열 검증 및 정규화
            normalized_time = self._normalize_time_string(time_str)
            if normalized_time:
                validated_times.append(normalized_time)
            else:
                logger.warning(f"유효하지 않은 시간 형식: {time_str}, 타입: {type(time_str)}")
        
        if not validated_times:
            logger.warning("유효한 시간이 없어 예약을 취소합니다.")
            return
            
        window_id_str = str(window_id)
        with self.tab_lock:
            # 이 창이 관리 목록에 있는지 확인
            if any(tab["id"] == window_id for tab in self.managed_tabs):
                # 기존 시간 확인 및 병합
                existing_times = self.scheduled_refreshes.get(window_id_str, [])
                if not isinstance(existing_times, list):
                    existing_times = []
                    
                # 중복 제거 후 추가
                for time_str in validated_times:
                    if time_str not in existing_times:
                        existing_times.append(time_str)
                
                self.scheduled_refreshes[window_id_str] = existing_times
                logger.info(f"창 {window_id}에 대한 예약 시간 추가 완료: {', '.join(validated_times)}")
                self.save_tabs()
                return True
            else:
                logger.warning(f"창 {window_id}가 존재하지 않아 예약 시간을 추가할 수 없습니다.")
                return False
    
    def _normalize_time_string(self, time_str):
        """시간 문자열 검증 및 정규화
        
        Args:
            time_str: 검증할 시간 문자열
            
        Returns:
            정규화된 시간 문자열 또는 유효하지 않은 경우 None
        """
        # 초기값 설정 - 명시적으로 유효하지 않음을 표시
        valid = False
        
        try:
            # 1. 문자열 타입 체크 및 변환
            if not isinstance(time_str, str):
                if isinstance(time_str, bool):
                    logger.debug(f"불리언 값 ({time_str})은 시간 문자열로 사용할 수 없습니다.")
                    return None
                
                try:
                    time_str = str(time_str)
                    logger.debug(f"문자열이 아닌 값 ({time_str}, 타입: {type(time_str)})을 문자열로 변환했습니다.")
                except Exception as e:
                    logger.warning(f"값 ({time_str})을 문자열로 변환할 수 없습니다: {e}")
                    return None
            
            # 2. 기본 포맷 검증 - 콜론(:) 개수 확인
            if ":" not in time_str:
                logger.debug(f"시간 문자열 '{time_str}'에 콜론(:)이 없어 유효하지 않습니다.")
                return None
            
            parts = time_str.split(":")
            if not (2 <= len(parts) <= 3):
                logger.debug(f"시간 문자열 '{time_str}'의 콜론 개수가 잘못되었습니다. 필요: 1-2개, 발견: {len(parts)-1}개")
                return None
            
            # 3. 시간 구성요소 변환 및 범위 검증
            try:
                h = int(parts[0])
                m = int(parts[1])
                s = int(parts[2]) if len(parts) > 2 else 0
                
                # 시간 범위 검증
                if 0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60:
                    valid = True
                else:
                    invalid_parts = []
                    if not (0 <= h < 24): invalid_parts.append(f"시({h})")
                    if not (0 <= m < 60): invalid_parts.append(f"분({m})")
                    if not (0 <= s < 60): invalid_parts.append(f"초({s})")
                    
                    logger.debug(f"시간 범위가 유효하지 않습니다: {', '.join(invalid_parts)}")
            except (ValueError, TypeError, IndexError) as e:
                logger.debug(f"시간 문자열 '{time_str}' 변환 중 오류: {e}")
                return None
            
            # 4. 유효성 검증 실패 시 종료
            if not valid:
                return None
            
            # 5. 형식화된 시간 문자열로 정규화
            normalized = f"{h:02d}:{m:02d}" if len(parts) == 2 else f"{h:02d}:{m:02d}:{s:02d}"
            logger.debug(f"시간 문자열 '{time_str}'을 '{normalized}'로 정규화했습니다.")
            return normalized
            
        except Exception as e:
            logger.warning(f"시간 문자열 '{time_str}' 정규화 중 예상치 못한 오류: {e}", exc_info=True)
            return None
    
    def remove_scheduled_refresh(self, window_id, time_str=None):
        """예약된 새로고침 시간 제거
        
        Args:
            window_id: 브라우저 창 ID
            time_str: 제거할 특정 시간 (None이면 모든 시간 제거)
        """
        window_id_str = str(window_id)
        changes_made = False
        
        # 데드락 방지를 위해 락 패턴 개선
        lock_acquired = False
        try:
            # 락 획득 시도 (타임아웃 설정)
            lock_acquired = self.tab_lock.acquire(timeout=2.0)
            if not lock_acquired:
                logger.warning("시간 제거 중 락 획득 실패, 락 없이 진행합니다.")
            
            # 내부 변수에 직접 작업
            if hasattr(self, '_tab_scheduled_refreshes'):
                target_dict = self._tab_scheduled_refreshes
            else:
                # 내부 변수가 없으면 생성
                self._tab_scheduled_refreshes = {}
                target_dict = self._tab_scheduled_refreshes
                # scheduled_refreshes에서 복사
                for wid, times in self.scheduled_refreshes.items():
                    if isinstance(times, list):
                        target_dict[wid] = times.copy()
            
            # 해당 창 ID가 있는지 확인
            if window_id_str in target_dict:
                if time_str is None:
                    # 모든 예약 시간 제거
                    target_dict.pop(window_id_str)
                    logger.info(f"창 {window_id}의 모든 예약 새로고침이 제거되었습니다.")
                    changes_made = True
                else:
                    # 시간 문자열 정규화
                    normalized_time = self._normalize_time_string(time_str)
                    if not normalized_time:
                        logger.warning(f"제거 요청된 시간 형식이 유효하지 않음: {time_str}")
                        return False
                    
                    # 해당 시간 찾아 제거
                    times = target_dict[window_id_str]
                    if not isinstance(times, list):
                        target_dict[window_id_str] = []
                        logger.warning(f"창 {window_id}의 예약 시간 목록이 유효하지 않아 초기화됨")
                        changes_made = True
                    elif normalized_time in times:
                        times.remove(normalized_time)
                        if not times:  # 시간이 더 이상 없으면 키 자체를 제거
                            target_dict.pop(window_id_str)
                        logger.info(f"창 {window_id}의 {normalized_time} 예약 새로고침이 제거되었습니다.")
                        changes_made = True
                    else:
                        logger.info(f"창 {window_id}에 제거할 시간 {normalized_time}이 존재하지 않습니다.")
            else:
                logger.warning(f"창 {window_id}에 대한 예약 정보가 없습니다.")
        finally:
            # 락 해제 (획득했을 경우에만)
            if lock_acquired:
                self.tab_lock.release()
        
        # 변경사항이 있었을 경우에만 저장
        if changes_made:
            # 락을 이미 해제했으므로 save_tabs에서 락을 획득할 수 있음
            self.save_tabs()
            return True
        
        return False
    
    def get_scheduled_refreshes(self, window_id=None):
        """예약된 새로고침 시간 조회
        
        Args:
            window_id: 특정 창의 ID (None이면 모든 창의 예약 시간 반환)
            
        Returns:
            예약된 시간 목록 (window_id가 없으면 전체 예약 정보 딕셔너리)
        """
        if window_id is None:
            # 모든 예약 정보 반환 (정규화된 형식으로)
            normalized_schedules = {}
            for win_id, times in self.scheduled_refreshes.items():
                if isinstance(times, list):
                    valid_times = []
                    for t in times:
                        normalized = self._normalize_time_string(t)
                        if normalized:
                            valid_times.append(normalized)
                    if valid_times:
                        normalized_schedules[win_id] = valid_times
            return normalized_schedules
        
        # 특정 창의 예약 정보 반환
        window_id_str = str(window_id)
        times = self.scheduled_refreshes.get(window_id_str, [])
        if not isinstance(times, list):
            return []
        
        # 유효한 시간 문자열만 필터링하여 반환
        valid_times = []
        for t in times:
            normalized = self._normalize_time_string(t)
            if normalized:
                valid_times.append(normalized)
        return valid_times
    
    def check_scheduled_refreshes(self):
        """
        예약된 새로고침 시간이 현재 시간과 일치하는지 확인 후 새로고침 실행
        매 분마다 호출되어 예약된 새로고침 시간을 확인하고 해당하는 탭 새로고침
        
        Returns:
            list: 새로고침된 탭 ID 목록 반환
        """
        # 새로고침될 탭 ID 목록 초기화
        refreshed_tabs = []
        tabs_to_refresh = []  # 병렬 처리를 위해 먼저 탭 ID들을 수집
        
        # 현재 시간 가져오기
        current_time = datetime.now()
        current_time_hhmm = current_time.strftime("%H:%M")
        current_time_hhmmss = current_time.strftime("%H:%M:%S")
        
        logger.info(f"예약된 새로고침 확인: 현재 시간 = {current_time_hhmmss}")
        
        # 새로 고침된 탭 ID 추적을 위한 세트
        processed_tabs = set()
        
        # 제거할 시간 항목 추적 (탭ID, 시간문자열)
        times_to_remove = []
        
        # 모든 탭에 대한 예약 시간 확인
        for window_id_str, times in self.scheduled_refreshes.items():
            # 이미 처리된 탭은 건너뜀
            if window_id_str in processed_tabs:
                continue
                
            # 유효한 시간 목록인지 확인
            if not isinstance(times, list) or not times:
                continue
                
            for time_str in times:
                # 문자열 형식인지 확인
                if not isinstance(time_str, str):
                    continue
                    
                # 반복 시간인지 확인 (별표로 시작하는 경우)
                is_repeating = time_str.startswith("*")
                # 실제 비교할 시간 문자열 준비
                compare_time_str = time_str[1:] if is_repeating else time_str
                
                # 정확한 시간 비교를 위해 초까지 확인
                if len(compare_time_str) == 5:  # HH:MM 형식인 경우
                    compare_time = compare_time_str
                    current_compare = current_time_hhmm
                else:  # HH:MM:SS 형식인 경우
                    compare_time = compare_time_str[:8]  # 최대 8자까지 (HH:MM:SS)
                    current_compare = current_time_hhmmss
                
                # 정확히 시간이 일치할 때만 새로고침
                if compare_time == current_compare:
                    logger.info(f"정확히 일치하는 시간 발견: 탭={window_id_str}, 시간={time_str}")
                    
                    try:
                        # 문자열 ID를 숫자로 변환 (안전하게)
                        try:
                            tab_id = int(window_id_str)
                        except ValueError:
                            tab_id = window_id_str
                        
                        # 새로고침할 탭 목록에 추가 (중복 방지)
                        if tab_id not in tabs_to_refresh:
                            tabs_to_refresh.append(tab_id)
                            processed_tabs.add(window_id_str)
                        
                            # 일회성 시간인 경우 제거 목록에 추가
                            if not is_repeating:
                                times_to_remove.append((window_id_str, time_str))
                                logger.info(f"일회성 시간 {time_str}은 실행 후 제거될 예정")
                    except Exception as e:
                        logger.error(f"탭 {window_id_str} 처리 중 오류: {e}")
        
        # 병렬로 일괄 새로고침 실행
        if tabs_to_refresh:
            logger.info(f"예약된 새로고침 실행: {len(tabs_to_refresh)}개 탭 병렬 처리")
            
            # 결과 수집 (성공한 탭만 반환)
            results = self.refresh_tabs_parallel(tabs_to_refresh)
            for i, result in enumerate(results):
                if result.get("success", False):
                    refreshed_tabs.append(tabs_to_refresh[i])
            
            # 일회성 시간 제거
            if times_to_remove:
                with self.tab_lock:  # 스레드 안전성 보장
                    for window_id_str, time_str in times_to_remove:
                        if window_id_str in self.scheduled_refreshes and time_str in self.scheduled_refreshes[window_id_str]:
                            self.scheduled_refreshes[window_id_str].remove(time_str)
                            logger.info(f"일회성 시간 제거됨: 탭={window_id_str}, 시간={time_str}")
                            
                            # 시간 목록이 비었으면 키 자체를 제거
                            if not self.scheduled_refreshes[window_id_str]:
                                self.scheduled_refreshes.pop(window_id_str)
                                logger.info(f"시간 목록이 비어 탭 제거됨: {window_id_str}")
                
                # 변경사항 저장
                self.save_tabs()
        
        return refreshed_tabs
    
    def _execute_scheduled_refresh(self, tab_id, time_str, exact_match):
        """
        예약된 새로고침을 실행하는 메서드
        
        Args:
            tab_id (str): 새로고침할 탭 ID
            time_str (str): 예약된 시간 문자열
            exact_match (bool): 정확한 초 단위 일치 여부
        """
        try:
            # 로그 시작 - 예약된 새로고침 시작
            logger.info(f"[ID:{tab_id}] 예약된 새로고침 시작: 시간={time_str}")
            
            # 정확한 시간 매칭이 아닌 경우 약간의 지연 추가
            if not exact_match:
                # 매우 짧은 지연만 추가 (정확성 유지)
                time.sleep(0.1)
            
            # 탭 새로고침 실행
            refresh_result = self.refresh_tab(tab_id)
            
            if refresh_result:
                logger.info(f"[ID:{tab_id}] 예약된 새로고침 완료: 시간={time_str}")
            else:
                logger.warning(f"[ID:{tab_id}] 예약된 새로고침 실패: 시간={time_str}")
                
        except Exception as e:
            logger.error(f"[ID:{tab_id}] 예약된 새로고침 중 오류 발생: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _check_browsers_running_status(self, tab_ids):
        """탭 ID 목록에 해당하는 브라우저들의 실행 상태를 확인합니다."""
        status = {}
        
        try:
            # 각 브라우저 타입별 실행 상태
            browser_running = {
                "chrome": False,
                "firefox": False,
                "edge": False,
                "safari": False
            }
            
            if self.system == "Darwin":  # macOS
                # AppleScript로 실행 중인 브라우저 확인
                check_script = '''
                tell application "System Events"
                    set chromeRunning to exists process "Google Chrome"
                    set firefoxRunning to exists process "Firefox"
                    set edgeRunning to exists process "Microsoft Edge"
                    set safariRunning to exists process "Safari"
                    return chromeRunning & "," & firefoxRunning & "," & edgeRunning & "," & safariRunning
                end tell
                '''
                
                result = self._run_applescript(check_script, timeout=3)
                if result and "," in result:
                    results = result.split(",")
                    if len(results) == 4:
                        browser_running["chrome"] = results[0].lower() == "true"
                        browser_running["firefox"] = results[1].lower() == "true"
                        browser_running["edge"] = results[2].lower() == "true"
                        browser_running["safari"] = results[3].lower() == "true"
            
            # 각 탭에 대한 브라우저 실행 상태 기록
            for tab_id in tab_ids:
                browser_type = self._get_tab_browser_type(tab_id)
                status[tab_id] = browser_running.get(browser_type, False)
        
        except Exception as e:
            logger.error(f"브라우저 실행 상태 확인 중 오류: {e}")
        
        return status
    
    def _group_tabs_by_browser_type(self, tab_ids):
        """탭 ID를 브라우저 타입별로 그룹화"""
        browser_tabs = {
            "chrome": [],
            "firefox": [],
            "edge": [],
            "safari": []
        }
        
        for tab_id in tab_ids:
            browser_type = self._get_tab_browser_type(tab_id)
            if browser_type in browser_tabs:
                browser_tabs[browser_type].append(tab_id)
        
        return {browser: tabs for browser, tabs in browser_tabs.items() if tabs}
    
    def _get_tab_browser_type(self, tab_id):
        """탭 ID에 해당하는 브라우저 타입 반환"""
        tab_id_str = str(tab_id)
        for tab in self.managed_tabs:
            if str(tab["id"]) == tab_id_str:
                return tab.get("browser_type", self.browser_type).lower()
        
        # 기본값 반환 (ID 패턴에 따라 브라우저 타입 추측)
        if tab_id >= 1000:
            if tab_id % 1000 == 1:  # Firefox/Safari 패턴
                return "safari"
            else:  # Chrome/Edge 패턴
                return "chrome"
        
        return self.browser_type.lower()
    
    def add_refresh_time(self, tab_id, refresh_time):
        """특정 탭에 새로고침 시간 추가
        
        Args:
            tab_id: 탭 ID
            refresh_time: 새로고침 시간 문자열 (hh:mm 또는 hh:mm:ss 형식)
        """
        # 입력 파라미터 검증
        if not tab_id or not refresh_time:
            logger.warning("유효하지 않은 탭 ID 또는 시간 형식")
            return False
            
        # 시간 문자열 정규화
        normalized_time = self._normalize_time_string(refresh_time)
        if not normalized_time:
            logger.warning(f"유효하지 않은 시간 형식: {refresh_time}")
            return False
            
        # 현재 시간을 가져오고 방금 설정한 시간과 비교
        current_time = datetime.now()
        time_parts = normalized_time.split(":")
        
        # 설정된 시간이 현재 시간보다 이전이면 로그 출력
        if len(time_parts) >= 2:
            # 시/분 추출
            scheduled_hour = int(time_parts[0])
            scheduled_minute = int(time_parts[1])
            
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            if (scheduled_hour < current_hour) or (scheduled_hour == current_hour and scheduled_minute <= current_minute):
                logger.info(f"시간 {normalized_time}은 현재 시간({current_hour:02d}:{current_minute:02d})보다 이전입니다. 내일의 해당 시간으로 간주됩니다.")
        
        # 내부 락 사용 
        with self.tab_lock:
            # 내부 딕셔너리 초기화 확인
            if not hasattr(self, '_tab_scheduled_refreshes'):
                self._tab_scheduled_refreshes = {}
            
            # 문자열 ID 변환
            str_tab_id = str(tab_id)
            
            # 기존 시간 목록에 추가
            existing_times = self._tab_scheduled_refreshes.get(str_tab_id, [])
            
            # 이미 존재하는지 확인 후 추가
            if normalized_time not in existing_times:
                existing_times.append(normalized_time)
                self._tab_scheduled_refreshes[str_tab_id] = existing_times
                self.scheduled_refreshes = self._tab_scheduled_refreshes.copy()
                logger.info(f"탭 ID {tab_id}에 시간 {normalized_time} 추가됨")
                
                # 변경사항 저장
                self.save_tabs()
                return True
            else:
                logger.info(f"시간 {normalized_time}은 이미 탭 ID {tab_id}에 존재함")
                return False
    
    def clear_refresh_times(self, tab_id):
        """탭의 모든 새로고침 시간 제거"""
        tab_id_str = str(tab_id)
        with self.tab_lock:  # 스레드 안전성 보장
            changes_made = False
            
            # 기본 scheduled_refreshes에서 제거
            if tab_id_str in self.scheduled_refreshes:
                self.scheduled_refreshes.pop(tab_id_str)
                changes_made = True
            
            # 내부 변수 _tab_scheduled_refreshes에서도 제거
            if hasattr(self, '_tab_scheduled_refreshes') and tab_id_str in self._tab_scheduled_refreshes:
                self._tab_scheduled_refreshes.pop(tab_id_str)
                changes_made = True
            
            if changes_made:
                logger.info(f"탭 {tab_id}의 모든 새로고침 시간이 제거됨")
                self.save_tabs()
                return True
            
            logger.info(f"탭 {tab_id}에 제거할 새로고침 시간이 없음")
            return False
    
    def set_scheduled_refresh(self, tab_id, enabled):
        """탭의 예약 새로고침 상태 설정"""
        tab_id_str = str(tab_id)
        
        with self.tab_lock:  # 스레드 안전성 보장
            if enabled:
                # 이미 등록된 시간이 없는 경우, 빈 목록으로 초기화
                if tab_id_str not in self.scheduled_refreshes:
                    self.scheduled_refreshes[tab_id_str] = []
                
                # 내부 변수도 함께 업데이트
                if hasattr(self, '_tab_scheduled_refreshes'):
                    if tab_id_str not in self._tab_scheduled_refreshes:
                        self._tab_scheduled_refreshes[tab_id_str] = []
                else:
                    self._tab_scheduled_refreshes = {tab_id_str: []}
            else:
                # 예약 해제 시 모든 시간 제거
                if tab_id_str in self.scheduled_refreshes:
                    self.scheduled_refreshes.pop(tab_id_str)
                
                # 내부 변수도 함께 업데이트
                if hasattr(self, '_tab_scheduled_refreshes') and tab_id_str in self._tab_scheduled_refreshes:
                    self._tab_scheduled_refreshes.pop(tab_id_str)
            
            self.save_tabs()
            logger.info(f"탭 {tab_id}의 예약 새로고침 상태가 {enabled}로 설정됨")
            return True
    
    def get_tab_by_id(self, tab_id):
        """
        ID로 탭 정보를 가져옵니다.
        
        Args:
            tab_id: 탭 ID
            
        Returns:
            해당하는 탭 정보 딕셔너리, 찾지 못한 경우 None
        """
        tab_id_str = str(tab_id)
        for tab in self.managed_tabs:
            if str(tab["id"]) == tab_id_str:
                return tab
        return None
        
    def _save_tab_scheduled_refreshes(self):
        """
        예약된 새로고침 시간을 저장합니다.
        내부 _tab_scheduled_refreshes 값을 scheduled_refreshes로 동기화합니다.
        """
        try:
            # 간단히 save_tabs 호출 (save_tabs에서 동기화 처리)
            # 별도의 락 관리나 동기화 로직 없이 save_tabs에 위임
            self.save_tabs()
            logger.debug("예약된 새로고침 시간이 저장되었습니다.")
        except Exception as e:
            logger.error(f"예약된 새로고침 시간 저장 중 오류: {e}", exc_info=True)

# 테스트 및 단독 실행용 코드
if __name__ == "__main__":
    import argparse
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description='브라우저 탭 관리자')
    parser.add_argument('--test', action='store_true', help='테스트 모드 실행')
    parser.add_argument('--browser', type=str, choices=['chrome', 'firefox', 'edge', 'safari'],
                       default='chrome', help='사용할 브라우저 (기본값: chrome)')
    parser.add_argument('--scan', action='store_true', help='현재 브라우저 탭 스캔')
    args = parser.parse_args()
    
    # 관리자 초기화
    tab_manager = TabManager()
    tab_manager.browser_type = args.browser
    
    # 테스트 모드
    if args.test:
        logger.setLevel(logging.DEBUG)
        print(f"[테스트 모드] 탭 관리자 초기화됨 (브라우저: {tab_manager.browser_type})")
        
        # 현재 시스템 정보 표시
        print(f"운영체제: {SYSTEM}")
        
        # 현재 관리 중인 탭 표시
        print("\n관리 중인 탭 목록:")
        for tab in tab_manager.managed_tabs:
            print(f"  - {tab['name']} (ID: {tab['id']})")
        
        # 예약된 새로고침 목록 표시
        print("\n예약된 새로고침 목록:")
        for window_id, times in tab_manager.scheduled_refreshes.items():
            # 오류 방지를 위한 타입 검사 추가
            if isinstance(times, list):
                valid_times = [str(t) for t in times if isinstance(t, str)]
                if valid_times:
                    print(f"  - 창 ID {window_id}: {', '.join(valid_times)}")
                else:
                    print(f"  - 창 ID {window_id}: (유효한 시간 없음)")
            else:
                print(f"  - 창 ID {window_id}: (잘못된 형식)")
        
        # 브라우저 탭 스캔 테스트
        if args.scan or not tab_manager.managed_tabs:
            print("\n브라우저 탭 스캔 결과:")
            browser_windows = tab_manager.get_browser_windows()
            for window in browser_windows:
                print(f"  - {window['name']} (ID: {window['id']}, 전체 제목: {window['title']})")
            
            # 테스트용 탭 추가
            if browser_windows and not tab_manager.managed_tabs:
                first_window = browser_windows[0]
                tab_manager.add_tab(first_window['id'], first_window['name'])
                print(f"\n테스트용 탭 추가됨: {first_window['name']} (ID: {first_window['id']})")
                
                # 테스트용 예약 추가
                test_time = (datetime.now() + timedelta(minutes=1)).strftime("%H:%M")
                tab_manager.add_scheduled_refresh(first_window['id'], [test_time])
                print(f"테스트 예약 추가됨: {test_time}")
                
            # 저장
            tab_manager.save_tabs()
    
    # 스캔 모드만 실행
    elif args.scan:
        print("\n브라우저 탭 스캔 결과:")
        browser_windows = tab_manager.get_browser_windows()
        for window in browser_windows:
            print(f"  - {window['name']} (ID: {window['id']}, 전체 제목: {window['title']})") 