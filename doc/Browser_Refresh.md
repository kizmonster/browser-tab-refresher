# Browser Tab Refresher 설계 문서

## 최신 업데이트 (2024-04-11)

### UI 개선

- 탭 관리 영역 확장 (전체 창의 57%)
  - 스캔된 탭 목록: 최소 높이 200px
  - 관리 중인 탭 목록: 최소 높이 200px
- 레이아웃 비율 최적화
  - 탭 관리 영역: 4
  - 브라우저 선택: 1
  - 새로고침 설정: 1
  - 상태 정보: 1

### 브라우저 지원 확장

- 지원 브라우저
  - Google Chrome
  - Mozilla Firefox
  - Microsoft Edge
  - Safari
- OS별 브라우저 처리
  - Windows: pygetwindow 기반 창 관리
  - macOS: AppleScript 기반 창 관리
  - Linux: 기본 구현 (향후 확장 예정)

### 코드 구조 개선

- MainWindow 클래스 리팩토링
  - 생성자 매개변수 수정
  - 탭 관리자 의존성 개선
- TabManager 클래스 확장
  - 브라우저별 창 처리 로직 추가
  - 탭 정보 구조 최적화
- 오류 처리 강화
  - 브라우저 전환 시 상태 초기화
  - 예외 상황 처리 개선

## 구성 요소

### 1. GUI (gui.py)

- 메인 윈도우 구성
  - 브라우저 선택 영역
  - 탭 관리 영역 (스캔/관리 목록)
  - 새로고침 설정
  - 상태 정보 표시
- 사용자 상호작용 처리
  - 탭 스캔 및 선택
  - 새로고침 설정
  - 상태 업데이트

### 2. 탭 관리자 (tab_manager.py)

- 브라우저 창 관리
  - 브라우저별 창 감지
  - 탭 정보 추출
  - OS별 최적화
- 새로고침 기능
  - 자동 새로고침
  - 예약 새로고침
  - 수동 새로고침

### 3. 시간 설정 다이얼로그 (time_schedule_dialog.py)

- 새로고침 시간 설정
- 다중 시간 관리
- 시간 목록 표시

## 데이터 구조

### 탭 정보

```json
{
  "id": "창 고유 ID",
  "name": "탭 이름",
  "title": "창 제목"
}
```

### 설정 파일 (tab_handles.json)

```json
{
  "browser_type": "브라우저 종류",
  "managed_tabs": [
    {
      "id": "창 ID",
      "name": "탭 이름"
    }
  ],
  "scheduled_refreshes": {
    "창 ID": ["HH:MM", "HH:MM"]
  }
}
```

## 주요 기능 흐름

### 1. 탭 스캔 및 추가

1. 브라우저 선택
2. 탭 스캔 실행
3. 스캔된 탭 목록 표시
4. 탭 선택 및 추가
5. 관리 목록 업데이트

### 2. 새로고침 실행

1. 자동 새로고침
   - 간격 설정
   - 타이머 기반 실행
2. 예약 새로고침
   - 시간 설정
   - 스케줄 기반 실행
3. 수동 새로고침
   - 선택 탭 새로고침
   - 전체 탭 새로고침

### 3. 상태 관리

1. 새로고침 상태
   - 다음 예정 시간
   - 마지막 실행 시간
2. 탭 상태
   - 선택된 탭 정보
   - 예약된 시간 목록
3. 오류 처리
   - 상태바 메시지
   - 오류 대화상자

## 향후 개선 사항

1. Linux 지원 강화
2. 브라우저 플러그인 연동
3. 고급 스케줄링 기능
4. 원격 제어 기능
5. 성능 모니터링 추가

---

# PyAutoGUI와 PyGetWindow를 활용한 직접적인 브라우저 탭 리프레시 전략

브라우저 탭을 효과적으로 리프레시하는 최적의 방법은 브라우저 창을 직접 제어하는 접근법입니다. 최종 결과물은 맥과 윈도우에서 모두 실행 가능하며, 사용자가 편하게 원하는 창을 지정할 수 있는 형태의 프로그램으로 개발했습니다. 다음은 이를 단계별로 명확하게 설명합니다.

---

## 📌 탭 리프레시 전략 개요

브라우저 탭을 리프레시하기 위해 PyAutoGUI와 PyGetWindow를 활용하여 실행 중인 브라우저 창을 직접 제어합니다. 이 접근 방식은 원격 디버깅 모드 없이도 빠르고 효율적으로 작동합니다.

> **핵심 전략**: 브라우저 창 식별 → 활성화 → 리프레시 키 (F5/Cmd+R) 전송 → 결과 확인

---

## 🚀 단계별 구현 방법

### 1️⃣ 브라우저 창 식별 및 관리

Windows와 macOS에서 실행 중인 Chrome 또는 Edge 브라우저 창을 식별합니다:

```python
import pygetwindow as gw

# Windows에서 브라우저 창 찾기
chrome_windows = gw.getWindowsWithTitle('Chrome')
edge_windows = gw.getWindowsWithTitle('Edge')
```

macOS에서는 AppleScript를 활용한 방식도 구현했습니다:

```python
import subprocess

def get_chrome_windows_macos():
    script = '''
    tell application "Google Chrome"
        get every window
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    # 결과 파싱 로직
```

### 2️⃣ 창 정보 JSON 파일로 저장

식별된 창 정보를 JSON 파일로 저장하여 관리합니다.

```json
{
  "managed_tabs": [
    {
      "name": "example_tab_1",
      "window_title": "Example Page - Google Chrome",
      "platform": "windows"
    }
  ]
}
```

Python 코드로 저장 및 로드:

```python
import json

# 저장
with open("tab_handles.json", "w") as f:
    json.dump(tab_info, f, indent=2)

# 불러오기
with open("tab_handles.json", "r") as f:
    managed_tabs = json.load(f)["managed_tabs"]
```

### 3️⃣ 직접 키 입력을 통한 리프레시

PyAutoGUI를 활용해 활성화된 창에 키 입력을 전송하여 리프레시합니다:

```python
import pyautogui
import platform

def refresh_window(window):
    window.activate()  # 창 활성화
    if platform.system() == 'Darwin':  # macOS
        pyautogui.hotkey('command', 'r')
    else:  # Windows
        pyautogui.press('f5')
```

### 4️⃣ 크로스 플랫폼 지원

운영체제별 최적화된 구현으로 Windows와 macOS 모두 지원합니다:

```python
def refresh_browser_tab(browser_name, tab_title):
    system = platform.system()

    if system == "Windows":
        windows = get_windows_by_browser(browser_name)
        for window in windows:
            if tab_title in window.title:
                refresh_window(window)
                return True

    elif system == "Darwin":  # macOS
        if browser_name.lower() == "chrome":
            return refresh_chrome_tab_macos(tab_title)
        # Edge 및 기타 브라우저 지원 로직
```

### 5️⃣ 프로그램 실행 편의성 확보

- PyQt 기반 GUI로 개발하여 비개발자도 쉽게 이용 가능
- 자동 리프레시 기능 (설정 가능한 시간 간격)
- 명령행 매개변수 지원 (`--browser`, `--debug`, `--refresh`, `--auto`)
- 실행 파일(.exe, .app)로 패키징하여 별도의 환경설정 없이 실행 가능

---

## ⚠️ 주의사항 및 추가 팁

- 창이 최소화된 경우 자동으로 활성화하여 리프레시
- 특정 브라우저에서 작동이 원활하지 않을 경우 대체 메서드 제공
- 사용자 설정 및 브라우저 목록 유지 관리

---

## 📌 전략의 주요 이점

- 디버그 모드 필요 없이 빠른 실행 가능
- 브라우저 연결 대기 시간 제거로 성능 향상
- 맥과 윈도우 모두 지원하는 크로스 플랫폼 지원
- GUI를 통한 직관적인 창 선택 및 관리

---
