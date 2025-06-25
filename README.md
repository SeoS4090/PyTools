# PyTools 애플리케이션

Python으로 개발된 시스템 트레이 기반 데스크톱 애플리케이션입니다. 자동 업데이트, 자동 시작, 설정 관리 등의 기능을 제공합니다.

## 주요 기능

- **시스템 트레이 지원**: 창을 닫으면 트레이로 최소화
- **트레이 메뉴**: 우클릭으로 열기, 정보보기, 설정, 종료 기능
- **자동 시작**: Windows 시작 시 자동 실행
- **자동 업데이트**: GitHub 릴리즈를 통한 자동 업데이트
- **설정 관리**: JSON 기반 설정 파일로 사용자 설정 저장
- **YouTube 뮤직 플레이어**: Google OAuth2.0 인증을 활용한 음악 플레이어

## 구글 OAuth2 연동

- 구글 연동 버튼 클릭 시 브라우저가 열리고, OAuth2 인증을 진행합니다.
- 인증이 완료되면 브라우저 창이 자동으로 닫히며, 애플리케이션에서 사용자 정보를 불러옵니다.
- 연동 해제 시 정보가 초기화되고, UI가 갱신됩니다.

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 애플리케이션 실행

#### 개발 모드 (권장)
```bash
python run.py
```

#### 직접 실행
```bash
python src/main.py
```

### 3. 실행 파일 생성 (선택사항)

```bash
python build/build.py
```

생성된 `dist/PyTools.exe` 파일을 실행하세요.

## 사용법

### 기본 사용법

1. 애플리케이션을 실행하면 메인 창이 나타납니다.
2. 창을 닫으면 자동으로 시스템 트레이로 최소화됩니다.
3. 트레이 아이콘을 더블클릭하면 창이 다시 나타납니다.

### 트레이 메뉴

트레이 아이콘에서 우클릭하면 다음 메뉴가 나타납니다:

- **열기**: 메인 창을 표시
- **정보 보기**: 애플리케이션 정보 확인
- **설정**: 현재 설정 확인
- **종료**: 애플리케이션 완전 종료

### 자동 업데이트

애플리케이션은 설정된 간격(기본 1시간)으로 GitHub에서 업데이트를 확인합니다. 새 버전이 발견되면 사용자에게 알림을 표시하고 업데이트를 진행할 수 있습니다.

## 설정

`data/config.json` 파일에서 다음 설정을 변경할 수 있습니다:

```json
{
  "version": "1.0.0",
  "github_repo": "your-username/your-repo",
  "auto_start": true,
  "check_updates": true,
  "update_interval": 3600,
  "minimize_to_tray": true,
  "window_position": {"x": 100, "y": 100},
  "window_size": {"width": 575, "height": 400},
  "youtube_cookies_browser": "none"
}
```

### 설정 항목 설명

- `version`: 현재 애플리케이션 버전
- `github_repo`: GitHub 저장소 정보 (자동 업데이트용)
- `auto_start`: Windows 시작 시 자동 실행 여부
- `check_updates`: 자동 업데이트 확인 여부
- `update_interval`: 업데이트 확인 간격 (초)
- `minimize_to_tray`: 창 닫기 시 트레이로 최소화 여부
- `window_position`: 창 위치
- `window_size`: 창 크기
- `youtube_cookies_browser`: YouTube 쿠키 브라우저 설정

## 개발

### 프로젝트 구조

```
PyTools/
├── src/                    # 소스 코드
│   ├── main.py            # 메인 애플리케이션
│   ├── config.py          # 설정 관리
│   └── utils/             # 유틸리티 함수들
│       └── __init__.py
├── ui/                    # UI 파일들
│   ├── login_page.ui
│   ├── main_window.ui
│   ├── music_player_page.ui
│   └── themes/            # 테마 파일들
│       ├── dark.qss
│       └── light.qss
├── data/                  # 데이터 파일들
│   ├── config.json
│   ├── playlist.json
│   ├── Cookie.txt
│   └── audio/             # 오디오 파일들
├── build/                 # 빌드 관련
│   ├── build_exe.py
│   ├── build.py
│   ├── updater.py
│   └── admin_manifest.xml
├── dist/                  # 배포 파일들
├── run.py                 # 실행 스크립트
├── requirements.txt
├── README.md
└── .gitignore
```

### 새로운 기능 추가

1. `src/main.py`의 `MainWindow` 클래스에 새로운 UI 요소 추가
2. 필요한 경우 `src/config.py`에 설정 항목 추가
3. 트레이 메뉴에 새로운 액션 추가

### 자동 업데이트 설정

GitHub 릴리즈를 통한 자동 업데이트를 사용하려면:

1. GitHub 저장소에 릴리즈를 생성
2. 릴리즈에 `PyTools-{version}.zip` 형식의 파일 업로드
3. `data/config.json`의 `github_repo` 설정을 실제 저장소로 변경

## 문제 해결

### 일반적인 문제

1. **PyQt5 설치 오류**: `pip install PyQt5==5.15.9`로 재설치
2. **트레이 아이콘 표시 안됨**: Windows 설정에서 시스템 트레이 아이콘 표시 확인
3. **자동 시작 안됨**: 관리자 권한으로 실행하거나 레지스트리 설정 확인

### 로그 확인

애플리케이션 내의 로그 영역에서 오류 메시지를 확인할 수 있습니다.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트나 기능 제안은 GitHub Issues를 통해 제출해주세요.

## 변경 로그

### v1.0.0
- 초기 버전 릴리즈
- 시스템 트레이 기능
- 자동 업데이트 기능
- 설정 관리 기능

### v1.0.2
- 구글 계정 연동 기능 추가 (메뉴에서 구글 로그인/로그아웃, 사용자 정보 표시)
- 환경 설정 다이얼로그 추가 (설정값 실시간 반영)
- 자동 시작(윈도우 부팅 시 실행) 옵션 추가 및 레지스트리 등록 지원
- 트레이 아이콘 우클릭 메뉴 개선 및 알림 기능 강화
- 자동 업데이트 안정성 개선 및 오류 메시지 개선
- 설정 파일(`config.json`) 기본값 및 구조 개선
- 빌드 및 자동 릴리즈 스크립트 추가 (`build.py`)
- 기타 UI 개선 및 버그 수정

## YouTube 뮤직 플레이어

Google OAuth2.0 인증을 활용하여 YouTube 음악을 검색하고 재생할 수 있는 데스크톱 애플리케이션입니다.

### 주요 기능

- Google OAuth2.0 인증 (API 키 불필요)
- YouTube 음악 검색
- 플레이리스트 관리
- 음악 재생/일시정지/정지
- 이전/다음 곡 재생
- 자동 다운로드 및 캐싱
- Google 로그인 시 자동 뮤직 플레이어 실행

### 설치 및 설정

1. **필요한 라이브러리 설치**
   ```bash
   pip install -r requirements.txt
   ```

2. **VLC 미디어 플레이어 설치**
   - [VLC 공식 사이트](https://www.videolan.org/vlc/)에서 VLC를 다운로드하여 설치
   - Python-vlc 라이브러리가 VLC를 사용하므로 필수

3. **FFmpeg 설치** (음악 변환용)
   - [FFmpeg 공식 사이트](https://ffmpeg.org/download.html)에서 다운로드
   - 시스템 PATH에 추가

### 사용법

#### 1. 메인 애플리케이션 실행
```bash
python run.py
```

#### 2. Google 로그인
- Setting > 구글 연동 메뉴 클릭
- Google 로그인 완료
- 로그인 성공 시 뮤직 플레이어 자동 실행 여부 선택

#### 3. 뮤직 플레이어 사용
- **자동 실행**: Google 로그인 완료 시 자동으로 실행
- **수동 실행**: Setting > YouTube 뮤직 플레이어 실행 메뉴 클릭
- **독립 실행**: `python run_youtube_player_oauth.py`

### 뮤직 플레이어 기능

1. **음악 검색**
   - 검색창에 원하는 음악 제목이나 아티스트명 입력
   - "검색" 버튼 클릭 또는 Enter 키

2. **음악 재생**
   - 검색 결과에서 원하는 곡을 더블클릭하여 재생
   - 재생/일시정지, 이전/다음 곡 버튼으로 제어

### 주의사항

- Google OAuth2.0 인증을 사용하므로 API 키 생성이 불필요합니다
- API 할당량이 개인 계정 기준으로 적용됩니다
- 다운로드된 음악은 임시 폴더에 저장되며 프로그램 종료 시 자동 삭제됩니다
- 저작권이 있는 콘텐츠의 사용 시 관련 법규를 준수하세요

### 문제 해결

1. **VLC 오류**
   - VLC가 올바르게 설치되었는지 확인
   - 시스템 PATH에 VLC가 포함되어 있는지 확인

2. **FFmpeg 오류**
   - FFmpeg가 설치되어 있는지 확인
   - 시스템 PATH에 FFmpeg가 포함되어 있는지 확인

3. **OAuth2.0 인증 오류**
   - main.py에서 Google 로그인이 완료되었는지 확인
   - config.json에 google_tokens가 저장되어 있는지 확인
   - 인터넷 연결 상태 확인

4. **뮤직 플레이어 실행 오류**
   - 필요한 라이브러리가 모두 설치되었는지 확인
   - `pip install -r requirements.txt` 실행

## 기타 도구들