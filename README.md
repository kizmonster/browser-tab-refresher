# Browser Tab Refresher (브라우저 탭 새로고침)

자주 사용하는 브라우저 탭들을 자동으로 새로고침해주는 크로스 플랫폼 유틸리티입니다.

## 주요 기능

- 다중 브라우저 지원 (Chrome, Firefox, Edge, Safari)
- 열려 있는 브라우저 탭 자동 감지 및 스캔
- 원하는 탭 다중 선택하여 관리 목록에 추가
- 선택한 탭 수동 또는 자동 새로고침
- 새로고침 간격 설정 가능 (최소 5초)
- 시간 기반 새로고침 예약 기능
- 크로스 플랫폼 지원 (Windows, macOS)
- F5 또는 Ctrl+R 단축키로 빠른 새로고침
- 설정 자동 저장
- 최적화된 UI 레이아웃으로 향상된 사용성

## 최신 업데이트

### UI 개선

- 탭 관리 영역 확장 (전체 창의 57% 차지)
- 스캔된 탭과 관리 중인 탭 목록의 가시성 향상
- 최적화된 레이아웃 비율 (탭 관리: 4, 기타 영역: 각 1)
- 브라우저 선택 UI 개선

### 브라우저 지원 확장

- Firefox와 Safari 브라우저 지원 추가
- 브라우저별 탭 스캔 기능 개선
- OS별 브라우저 창 처리 로직 최적화

### 안정성 개선

- 브라우저 전환 시 탭 목록 자동 초기화
- 탭 정보 처리 방식 개선
- 오류 처리 및 상태 표시 개선

## 스크린샷

(스크린샷 이미지 추가 예정)

## 요구사항

### 공통 요구사항

- Python 3.7 이상
- pip (Python 패키지 관리자)
- Git

### Windows 추가 요구사항

- Windows 10 이상 권장
- Microsoft Visual C++ 14.0 이상
  ```bash
  # Microsoft C++ Build Tools 설치 (관리자 권한 필요)
  winget install Microsoft.VisualStudio.2022.BuildTools
  # 또는 https://visualstudio.microsoft.com/visual-cpp-build-tools/ 에서 다운로드
  ```

### macOS 추가 요구사항

- Homebrew (패키지 관리자)
- Xcode Command Line Tools
  ```bash
  xcode-select --install
  ```
- Python Tkinter
  ```bash
  brew install python-tk
  ```

### Linux 추가 요구사항

- X11 개발 라이브러리

  ```bash
  # Ubuntu/Debian
  sudo apt-get install python3-tk python3-dev
  sudo apt-get install scrot
  sudo apt-get install python3-xlib

  # Fedora
  sudo dnf install python3-tkinter python3-devel
  sudo dnf install scrot
  sudo dnf install python3-xlib
  ```

## 개발 환경 설정

### Windows에서 설정

1. Python 3.7 이상 설치 (https://www.python.org/downloads/)

   - 설치 시 "Add Python to PATH" 옵션 체크
   - 설치 완료 후 터미널에서 확인:
     ```bash
     python --version
     pip --version
     ```

2. Microsoft C++ Build Tools 설치 (위 요구사항 참조)

3. 가상 환경 생성 및 활성화:

   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

4. 필요한 패키지 설치:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

### macOS에서 설정

1. Homebrew 설치 (없는 경우):

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Python 3.7 이상 설치:

   ```bash
   brew install python
   brew install python-tk
   ```

3. Xcode Command Line Tools 설치:

   ```bash
   xcode-select --install
   ```

4. 가상 환경 생성 및 활성화:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. 필요한 패키지 설치:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Linux에서 설정

1. 시스템 패키지 업데이트 및 필수 패키지 설치:

   ```bash
   sudo apt-get update
   sudo apt-get install python3 python3-venv python3-pip python3-tk python3-dev scrot python3-xlib
   # 또는 Fedora:
   # sudo dnf install python3 python3-virtualenv python3-pip python3-tkinter python3-devel scrot python3-xlib
   ```

2. 가상 환경 생성 및 활성화:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. 필요한 패키지 설치:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

## 프로젝트 구조

```
browser-tab-refresher/
├── main.py              # 메인 실행 파일
├── gui.py              # GUI 구현
├── tab_manager.py      # 탭 관리 로직
├── app_packager.py     # 실행 파일 패키징 스크립트
├── requirements.txt    # 필요한 패키지 목록
├── tab_handles.json    # 저장된 탭 정보
├── doc/               # 문서 디렉토리
│   └── Browser_Refresh.md  # 상세 설계 문서
├── LICENSE            # MIT 라이센스
└── README.md         # 이 파일
```

## 설치 방법

1. 저장소 클론:

   ```bash
   git clone https://github.com/kizmonster/browser-tab-refresher.git
   cd browser-tab-refresher
   ```

2. 가상 환경 설정 (위의 개발 환경 설정 참조)

3. 필요한 패키지 설치:
   ```bash
   pip install -r requirements.txt
   ```

## 개발 모드로 실행

가상 환경이 활성화된 상태에서:

```bash
# 기본 실행
python main.py

# 디버그 모드로 실행
python main.py --debug

# Chrome 브라우저로 실행하고 자동 새로고침 활성화
python main.py --browser chrome --auto
```

## 문제 해결

### 가상 환경 관련 문제

1. 가상 환경 활성화가 안 되는 경우:

   - Windows: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` 실행 후 다시 시도
   - Unix: `chmod +x venv/bin/activate` 실행 후 다시 시도

2. 패키지 설치 오류:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. PyAutoGUI 설치 문제 (macOS):
   ```bash
   brew install python-tk
   pip install pyautogui
   ```

### 브라우저 인식 문제

1. Chrome이나 Edge가 인식되지 않는 경우:

   - 브라우저를 완전히 종료 후 재시작
   - 관리자 권한으로 프로그램 실행

2. 새로고침이 작동하지 않는 경우:
   - 브라우저 창이 최소화되어 있지 않은지 확인
   - 다른 프로그램이 키보드 입력을 차단하고 있지 않은지 확인

### 운영체제별 일반적인 문제

#### Windows

1. "Microsoft Visual C++ 14.0 is required" 오류:

   - Microsoft C++ Build Tools 설치 필요 (위 요구사항 참조)

2. PATH 관련 오류:
   - Python이 시스템 PATH에 제대로 추가되었는지 확인
   - 제어판 > 시스템 > 고급 시스템 설정 > 환경 변수에서 확인 및 수정

#### macOS

1. "Tkinter not found" 오류:

   ```bash
   brew install python-tk
   ```

2. "xcrun: error" 오류:

   ```bash
   xcode-select --install
   ```

3. PyAutoGUI 권한 문제:
   - 시스템 환경설정 > 보안 및 개인 정보 보호 > 개인 정보 보호 > 손쉬운 사용에서 터미널 앱 허용

#### Linux

1. 스크린샷 관련 오류:

   ```bash
   sudo apt-get install scrot
   # 또는
   sudo dnf install scrot
   ```

2. X11 관련 오류:
   ```bash
   sudo apt-get install python3-xlib
   # 또는
   sudo dnf install python3-xlib
   ```

## 사용 방법

1. 프로그램 실행:

   ```bash
   python main.py
   ```

2. 브라우저 선택 (Chrome 또는 Edge)

3. '열린 브라우저 탭 스캔' 버튼 클릭하여 현재 열려있는 탭 찾기

4. 스캔된 탭 중 자동 새로고침 하고 싶은 탭을 더블클릭하여 관리 목록에 추가

5. 관리 탭에서 다음 기능 사용:
   - 선택한 탭 새로고침: 선택한 탭만 새로고침
   - 모든 탭 새로고침: 모든 관리 탭 일괄 새로고침
   - 자동 새로고침: 설정한 간격으로 자동 새로고침 활성화

## 명령줄 옵션

```bash
python main.py --help
```

다음과 같은 옵션을 사용할 수 있습니다:

- `--browser {chrome,edge}`: 사용할 브라우저 지정
- `--config CONFIG`: 설정 파일 경로 지정
- `--debug`: 디버그 모드 활성화
- `--refresh`: 시작 시 저장된 모든 탭 즉시 새로고침
- `--auto`: 시작 시 자동 새로고침 활성화

## 빌드하기

실행 파일로 빌드하려면:

```bash
python app_packager.py
```

빌드된 실행 파일은 `dist` 디렉토리에 생성됩니다.

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 기여하기

버그 리포트, 기능 요청, 풀 리퀘스트 모두 환영합니다!

1. 저장소 포크
2. 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add some amazing feature'`)
4. 브랜치 푸시 (`git push origin feature/amazing-feature`)
5. 풀 리퀘스트 오픈

## 연락처

작성자: Kizmonster - GitHub: [@kizmonster](https://github.com/kizmonster)
