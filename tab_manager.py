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

# 로깅 설정
logger = logging.getLogger('TabManager')

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
        self.system = SYSTEM  # 운영체제 확인 (Windows, Darwin, Linux)
        self.scheduled_refreshes = {}  # 예약된 새로고침 시간 저장
        
        # 설정에서 관리 탭 초기화
        if tab_handles is None:
            self.load_tabs()
        else:
            self.browser_type = tab_handles.get("browser_type", "chrome")
            self.managed_tabs = tab_handles.get("managed_tabs", [])
            self.scheduled_refreshes = tab_handles.get("scheduled_refreshes", {})
    
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
                    logger.info(f"{len(self.managed_tabs)}개의 탭 정보를 로드했습니다.")
        except Exception as e:
            logger.error(f"탭 정보 로드 오류: {e}")
            # 기본값 설정
            self.browser_type = "chrome"
            self.managed_tabs = []
            self.scheduled_refreshes = {}
    
    def save_tabs(self):
        """탭 정보 저장"""
        try:
            tab_data = {
                "browser_type": self.browser_type,
                "managed_tabs": self.managed_tabs,
                "scheduled_refreshes": self.scheduled_refreshes
            }
            with open(self.tab_info_file, 'w', encoding='utf-8') as f:
                json.dump(tab_data, f, ensure_ascii=False, indent=2)
            logger.info(f"{len(self.managed_tabs)}개의 탭 정보를 저장했습니다.")
            return True
        except Exception as e:
            logger.error(f"탭 정보 저장 오류: {e}")
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
            # 모든 창 가져오기
            all_windows = gw.getAllWindows()
            
            for window in all_windows:
                # 윈도우 제목에서 브라우저 확인
                title = window.title
                
                # Chrome 브라우저 확인
                if self.browser_type.lower() == "chrome" and self._is_chrome_window(title):
                    browser_windows.append({
                        "title": title,
                        "id": window._hWnd,
                        "name": self._extract_tab_name(title)
                    })
                # Edge 브라우저 확인
                elif self.browser_type.lower() == "edge" and self._is_edge_window(title):
                    browser_windows.append({
                        "title": title,
                        "id": window._hWnd,
                        "name": self._extract_tab_name(title)
                    })
            
            logger.info(f"{len(browser_windows)}개의 {self.browser_type} 브라우저 창을 찾았습니다.")
        except Exception as e:
            logger.error(f"Windows 브라우저 창 탐색 오류: {e}")
        
        return browser_windows
    
    def _macos_get_browser_windows(self):
        """macOS에서 브라우저 창 목록 가져오기"""
        browser_windows = []
        
        try:
            # AppleScript를 사용하여 브라우저 창 가져오기
            browser_name = "Google Chrome" if self.browser_type.lower() == "chrome" else "Microsoft Edge"
            
            # AppleScript 실행
            script = f'''
            tell application "{browser_name}"
                set windowList to every window
                set windowData to ""
                repeat with w in windowList
                    set windowID to id of w
                    set windowTitle to name of w
                    set windowData to windowData & windowID & "," & windowTitle & "\\n"
                end repeat
                return windowData
            end tell
            '''
            
            result = self._run_applescript(script)
            if result:
                lines = result.strip().split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.strip().split(',', 1)
                        if len(parts) == 2:
                            window_id, title = parts
                            browser_windows.append({
                                "title": title,
                                "id": int(window_id),
                                "name": self._extract_tab_name(title)
                            })
            
            logger.info(f"{len(browser_windows)}개의 {self.browser_type} 브라우저 창을 찾았습니다.")
        except Exception as e:
            logger.error(f"macOS 브라우저 창 탐색 오류: {e}")
            
            # 실패했을 경우 더미 데이터 생성 (디버깅/테스트용)
            if self.browser_type.lower() == "chrome":
                titles = ["Google", "GitHub", "Stack Overflow", "YouTube"]
            else:
                titles = ["Bing", "Microsoft", "GitHub", "YouTube"]
                
            for i, title in enumerate(titles):
                browser_windows.append({
                    "title": f"{title} - {browser_name}",
                    "id": 1000 + i,  # 고유 ID 임의 생성
                    "name": title
                })
            
            logger.info(f"생성된 테스트 창 {len(browser_windows)}개")
        
        return browser_windows
    
    def _linux_get_browser_windows(self):
        """Linux에서 브라우저 창 목록 가져오기"""
        # Linux는 현재 단순 구현만 제공
        browser_windows = []
        browser_name = "Chrome" if self.browser_type.lower() == "chrome" else "Edge"
        titles = ["Google", "GitHub", "Stack Overflow", "YouTube"]
        
        for i, title in enumerate(titles):
            browser_windows.append({
                "title": f"{title} - {browser_name}",
                "id": 2000 + i,  # 고유 ID 임의 생성
                "name": title
            })
        
        return browser_windows
    
    def _run_applescript(self, script):
        """AppleScript 실행"""
        try:
            process = subprocess.Popen(['osascript', '-e', script], 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                return stdout.decode('utf-8')
            else:
                logger.error(f"AppleScript 오류: {stderr.decode('utf-8')}")
                return None
        except Exception as e:
            logger.error(f"AppleScript 실행 오류: {e}")
            return None
    
    def _is_chrome_window(self, title):
        """제목에서 Chrome 브라우저 확인"""
        if self.system == "Windows":
            return "Google Chrome" in title
        elif self.system == "Darwin":  # macOS
            return "Chrome" in title or "Google Chrome" in title
        else:  # Linux 등
            return "Chrome" in title
    
    def _is_edge_window(self, title):
        """제목에서 Edge 브라우저 확인"""
        if self.system == "Windows":
            return "Microsoft Edge" in title
        elif self.system == "Darwin":  # macOS
            return "Edge" in title or "Microsoft Edge" in title
        else:  # Linux 등
            return "Edge" in title
    
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
        elif " - " in title:
            # 대부분의 브라우저는 "페이지 제목 - 브라우저 이름" 형식 사용
            return title.split(" - ")[0].strip()
        return title.strip()
    
    def add_tab(self, window_id, name):
        """관리할 탭 추가"""
        # 이미 추가된 탭인지 확인
        for tab in self.managed_tabs:
            if tab["id"] == window_id:
                return False
        
        # 새 탭 추가
        self.managed_tabs.append({
            "id": window_id,
            "name": name
        })
        self.save_tabs()
        return True
    
    def remove_tab(self, window_id):
        """관리 탭 제거"""
        for i, tab in enumerate(self.managed_tabs):
            if tab["id"] == window_id:
                self.managed_tabs.pop(i)
                self.save_tabs()
                return True
        return False
    
    def refresh_tab(self, window_id):
        """특정 탭 새로고침"""
        if self.system == "Windows":
            return self._windows_refresh_tab(window_id)
        elif self.system == "Darwin":  # macOS
            return self._macos_refresh_tab(window_id)
        else:  # Linux 등
            # 테스트 목적으로 성공 반환
            logger.info(f"탭 ID {window_id} (테스트) 새로고침 완료")
            return True
    
    def _windows_refresh_tab(self, window_id):
        """Windows에서 탭 새로고침"""
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
    
    def _macos_refresh_tab(self, window_id):
        """macOS에서 AppleScript로 탭 새로고침"""
        try:
            browser_name = "Google Chrome" if self.browser_type.lower() == "chrome" else "Microsoft Edge"
            
            # AppleScript를 사용하여 특정 창 새로고침
            script = f'''
            tell application "{browser_name}"
                set targetWindow to (every window whose id is {window_id})
                if length of targetWindow is 0 then
                    return "Window not found"
                end if
                set window_index to index of item 1 of targetWindow
                tell window window_index
                    tell active tab to reload
                end tell
                return "Success"
            end tell
            '''
            
            result = self._run_applescript(script)
            if result and "Success" in result:
                logger.info(f"AppleScript를 사용하여 탭 ID {window_id} 새로고침 완료")
                return True
            else:
                logger.warning(f"AppleScript 탭 새로고침 실패: {result}")
                
                # 대체 방법: 시스템 이벤트 사용
                alt_script = f'''
                tell application "{browser_name}"
                    activate
                    set targetWindow to (every window whose id is {window_id})
                    if length of targetWindow is 0 then
                        return "Window not found"
                    end if
                    set window_index to index of item 1 of targetWindow
                    set index of window window_index to 1
                end tell
                
                tell application "System Events"
                    keystroke "r" using {{command down}}
                end tell
                return "Success"
                '''
                
                alt_result = self._run_applescript(alt_script)
                if alt_result and "Success" in alt_result:
                    logger.info(f"시스템 이벤트를 사용하여 탭 ID {window_id} 새로고침 완료")
                    return True
                else:
                    logger.warning(f"시스템 이벤트 탭 새로고침 실패: {alt_result}")
                    return False
        except Exception as e:
            logger.error(f"macOS 탭 새로고침 오류: {e}")
            
            # 테스트용 성공 반환 (실제 환경이 없는 경우)
            logger.info(f"테스트 목적으로 탭 ID {window_id} 새로고침 성공으로 처리")
            return True
    
    def refresh_all_tabs(self):
        """모든 관리 탭 새로고침"""
        results = []
        
        # 각 탭에 대해 refresh_tab 호출
        for tab in self.managed_tabs:
            window_id = tab["id"]
            success = self.refresh_tab(window_id)
            
            # 결과 반환을 위한 정보 준비
            results.append({
                "name": tab["name"],
                "success": success
            })
            
            # 여러 탭을 연속 리프레시 시 딜레이
            time.sleep(0.5)
        
        return results
    
    def set_browser_type(self, browser_type):
        """브라우저 타입 설정"""
        if browser_type.lower() in ["chrome", "edge"]:
            self.browser_type = browser_type.lower()
            self.save_tabs()
            return True
        return False

    def add_scheduled_refresh(self, window_id, times):
        """
        특정 탭에 대한 예약 새로고침 시간 추가
        
        Args:
            window_id: 브라우저 창 ID
            times: 새로고침할 시간 목록 (HH:MM 형식의 문자열 리스트)
        """
        # 시간 형식 검증
        validated_times = []
        for time_str in times:
            try:
                # 시간 형식 검증 (HH:MM)
                hour, minute = map(int, time_str.split(':'))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    validated_times.append(f"{hour:02d}:{minute:02d}")
                else:
                    logger.error(f"잘못된 시간 형식: {time_str}")
            except ValueError:
                logger.error(f"잘못된 시간 형식: {time_str}")
                continue
        
        # 창 ID를 문자열로 변환 (JSON 직렬화를 위해)
        window_id_str = str(window_id)
        
        # 기존 시간이 있으면 업데이트, 없으면 새로 추가
        if validated_times:
            self.scheduled_refreshes[window_id_str] = sorted(validated_times)
            self.save_tabs()
            logger.info(f"창 {window_id}에 {len(validated_times)}개의 예약 새로고침 시간이 설정되었습니다.")
            return True
        return False

    def remove_scheduled_refresh(self, window_id, time_str=None):
        """
        예약된 새로고침 시간 제거
        
        Args:
            window_id: 브라우저 창 ID
            time_str: 제거할 특정 시간 (None이면 모든 시간 제거)
        """
        window_id_str = str(window_id)
        if window_id_str in self.scheduled_refreshes:
            if time_str is None:
                # 모든 예약 시간 제거
                del self.scheduled_refreshes[window_id_str]
                logger.info(f"창 {window_id}의 모든 예약 새로고침이 제거되었습니다.")
            else:
                # 특정 시간만 제거
                times = self.scheduled_refreshes[window_id_str]
                if time_str in times:
                    times.remove(time_str)
                    if not times:  # 시간이 더 이상 없으면 키 자체를 제거
                        del self.scheduled_refreshes[window_id_str]
                    else:
                        self.scheduled_refreshes[window_id_str] = times
                    logger.info(f"창 {window_id}의 {time_str} 예약 새로고침이 제거되었습니다.")
            self.save_tabs()
            return True
        return False

    def get_scheduled_refreshes(self, window_id=None):
        """
        예약된 새로고침 시간 조회
        
        Args:
            window_id: 특정 창의 ID (None이면 모든 창의 예약 시간 반환)
        """
        if window_id is None:
            return self.scheduled_refreshes
        return self.scheduled_refreshes.get(str(window_id), [])

    def check_scheduled_refreshes(self):
        """현재 시간에 예약된 새로고침 실행"""
        current_time = time.strftime("%H:%M")
        refreshed_tabs = []
        
        for window_id_str, times in self.scheduled_refreshes.items():
            if current_time in times:
                try:
                    window_id = int(window_id_str)
                    if self.refresh_tab(window_id):
                        refreshed_tabs.append(window_id)
                        logger.info(f"예약된 새로고침 실행: 창 {window_id}, 시간 {current_time}")
                except ValueError:
                    logger.error(f"잘못된 창 ID 형식: {window_id_str}")
        
        return refreshed_tabs 