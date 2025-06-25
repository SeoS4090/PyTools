import sys
import os
import json
import requests
import webbrowser
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from threading import Thread
import tempfile
import time
import base64
import zipfile
import shutil
from PyQt5 import uic

# 미디어 플레이어 백엔드 설정 (DirectShow 오류 방지)
os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmedia'

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu, QAction, QMessageBox, QStyle, QDialog, 
    QVBoxLayout, QCheckBox, QPushButton, QLabel, QHBoxLayout, QLineEdit, QListWidget, QSlider, QFrame,
    QListWidgetItem, QGraphicsDropShadowEffect, QProgressDialog, QStackedWidget, QRadioButton, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QImage, QFont, QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

import psutil
if sys.platform == "win32":
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None
import subprocess
import yt_dlp

# 프로젝트 루트 경로 설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.config import config
from build.updater import UpdateManager

# --- Google OAuth2 & YouTube API 관련 상수 ---
GOOGLE_CLIENT_ID = "44798885024-pf7otl5hsn6a0am4cagg1dlcssr5b6ng.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_REDIRECT_URI = "http://localhost"
GOOGLE_SCOPE = "openid email profile https://www.googleapis.com/auth/youtube.readonly"

# --- FFmpeg 자동 설치 클래스 ---
class FFmpegInstaller(QThread):
    progress_updated = pyqtSignal(str)
    installation_complete = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        # 더 안정적인 gyan.dev의 essentials 빌드 링크로 변경
        self.ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        self.install_dir = os.path.join(os.path.expanduser("~"), "PyTools", "ffmpeg")
        
    def is_ffmpeg_installed(self):
        """FFmpeg가 설치되어 있는지 확인"""
        # 로컬 설치 확인 먼저 (더 빠름)
        ffmpeg_path = os.path.join(self.install_dir, "bin", "ffmpeg.exe")
        if os.path.exists(ffmpeg_path):
            return True

        # 시스템 PATH에서 확인
        try:
            subprocess.run(['ffmpeg', '-version'], 
                           capture_output=True, text=True, check=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            return False
    
    def download_ffmpeg(self):
        """FFmpeg 다운로드"""
        try:
            self.progress_updated.emit("FFmpeg 다운로드 중...")
            
            # 다운로드 받을 임시 폴더
            temp_dir = tempfile.gettempdir()
            zip_path = os.path.join(temp_dir, "ffmpeg-download.zip")
            
            response = requests.get(self.ffmpeg_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(f"다운로드 중... {progress}%")
            
            return zip_path
            
        except Exception as e:
            raise Exception(f"FFmpeg 다운로드 실패: {str(e)}")
    
    def install_ffmpeg(self, zip_file):
        """FFmpeg 설치"""
        try:
            self.progress_updated.emit("FFmpeg 설치 중...")
            
            # 기존 설치 폴더가 있으면 비우기
            if os.path.exists(self.install_dir):
                shutil.rmtree(self.install_dir)
            os.makedirs(self.install_dir, exist_ok=True)
            
            # 압축 해제
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(self.install_dir)
            
            # 임시 압축 파일 삭제
            os.remove(zip_file)
            
            # 폴더 구조 정리 (내부 폴더의 내용물을 상위로 이동)
            # gyan.dev 빌드는 'ffmpeg-X.X.X-essentials_build' 같은 폴더에 압축이 풀림
            extracted_dir_name = next(d for d in os.listdir(self.install_dir) if os.path.isdir(os.path.join(self.install_dir, d)))
            extracted_path = os.path.join(self.install_dir, extracted_dir_name)
            
            for item in os.listdir(extracted_path):
                shutil.move(os.path.join(extracted_path, item), self.install_dir)
            
            # 빈 폴더 삭제
            os.rmdir(extracted_path)
            
            # PATH에 추가
            self.add_to_path()
            
            return True
            
        except Exception as e:
            # 실패 시 정리
            if os.path.exists(self.install_dir):
                shutil.rmtree(self.install_dir)
            raise Exception(f"FFmpeg 설치 실패: {str(e)}")
    
    def add_to_path(self):
        """시스템 PATH에 FFmpeg 경로 추가"""
        try:
            if not winreg: return

            ffmpeg_bin = os.path.join(self.install_dir, "bin")
            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
            try:
                path, reg_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                path, reg_type = "", winreg.REG_SZ
            
            if ffmpeg_bin not in path.split(';'):
                new_path = path + ";" + ffmpeg_bin if path else ffmpeg_bin
                winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
            
            winreg.CloseKey(key)
                
        except Exception as e:
            print(f"PATH 설정 실패: {e}")
    
    def run(self):
        """FFmpeg 설치 실행"""
        try:
            if self.is_ffmpeg_installed():
                self.installation_complete.emit(True, "FFmpeg가 이미 설치되어 있습니다.")
                return
            
            self.progress_updated.emit("FFmpeg 설치를 시작합니다...")
            
            zip_file = self.download_ffmpeg()
            self.install_ffmpeg(zip_file)
            
            self.progress_updated.emit("FFmpeg 설치 완료!")
            self.installation_complete.emit(True, "FFmpeg 설치가 완료되었습니다. 프로그램을 다시 시작하면 적용됩니다.")
            
        except Exception as e:
            self.installation_complete.emit(False, str(e))

# --- 아이콘 로더 ---
ICONS = {}
def get_icon(name, color="white"):
    if (name, color) in ICONS:
        return ICONS[(name, color)]
    
    icon = QIcon()
    base_path = os.path.join(os.path.dirname(__file__), "icons") # 아이콘 폴더가 있다고 가정
    if not os.path.exists(base_path):
        base_path = "" # 폴더가 없으면 Qt 기본 아이콘 사용 시도

    # 아이콘 파일명 규칙: player_play.png, player_pause.png 등
    icon_path = os.path.join(base_path, f"player_{name}.png")

    print("icon_path: " + icon_path + " " + str(os.path.exists(icon_path)))

    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        if color != "white": # 간단한 색상 변경 로직 (예시)
            mask = pixmap.createMaskFromColor(Qt.GlobalColor.transparent)
            pixmap.fill(QColor(color))
            pixmap.setMask(mask)
        icon.addPixmap(pixmap)
    else:
        # Qt 기본 아이콘 사용
        try:
            standard_icon = getattr(QStyle, f"SP_Media{name.capitalize()}")
            icon = QApplication.style().standardIcon(standard_icon)
        except AttributeError:
            # 적절한 아이콘이 없을 경우 빈 아이콘 반환
            pass
    
    ICONS[(name, color)] = icon
    return icon

# --- 뮤직 플레이어 관련 클래스 ---
class YouTubeAPIOAuth:
    def __init__(self, access_token):
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def search(self, query, max_results=25):
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoCategoryId": "10",  # Music category
            "maxResults": max_results,
        }
        response = requests.get(url, params=params, headers=self.headers)
        return response.json()

class MusicStreamer(QThread):
    stream_ready = pyqtSignal(str, str, str)  # video_id, stream_url, title
    stream_error = pyqtSignal(str, str) # video_id, error_message
    progress_updated = pyqtSignal(str, str) # video_id, message
    fallback_download = pyqtSignal(str, str) # video_id, title (다운로드 방식으로 폴백)
    
    def __init__(self, video_id, title):
        super().__init__()
        self.video_id = video_id
        self.title = title
        self.temp_dir = tempfile.gettempdir()
        
    def run(self):
        try:
            self.progress_updated.emit(self.video_id, "스트림 정보 가져오는 중...")
            
            # yt-dlp 옵션 설정 (스트리밍용)
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,  # 전체 정보 추출
                'no_download': True,    # 다운로드하지 않고 URL만 추출
                'ignoreerrors': False,  # 오류 발생 시 즉시 중단
                'no_check_certificate': True,  # 인증서 검증 건너뛰기
                'extractor_retries': 3,  # 추출 재시도 횟수
                'fragment_retries': 3,   # 조각 다운로드 재시도
            }
            
            # 쿠키 설정 추가 (권한 오류 방지)
            browser = config.get("youtube_cookies_browser", "none")
            if browser != "none":
                try:
                    ydl_opts['cookiesfrombrowser'] = ('chrome', 'Default')  # 또는 'Profile 1'
                except Exception as e:
                    print(f"브라우저 쿠키 접근 실패: {e}. 쿠키 없이 진행합니다.")
            
            # 스트림 URL 추출
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # video_id가 이미 완전한 URL인지 확인
                    if self.video_id.startswith(('http://', 'https://')):
                        url = self.video_id
                    else:
                        # video_id만 있는 경우 완전한 URL로 변환
                        url = f"https://www.youtube.com/watch?v={self.video_id}"
                    
                    print(f"처리할 URL: {url}")
                    info_dict = ydl.extract_info(url, download=False)
                except Exception as extract_error:
                    print(f"영상 정보 추출 실패: {extract_error}")
                    # 추출 실패 시 다운로드 방식으로 폴백
                    self.fallback_download.emit(self.video_id, self.title)
                    return
                
                if not info_dict:
                    print("영상 정보가 비어있습니다. 다운로드 방식으로 폴백합니다.")
                    self.fallback_download.emit(self.video_id, self.title)
                    return
                
                # 최적의 오디오 스트림 URL 찾기 (더 포괄적인 방법)
                formats = info_dict.get('formats', [])
                
                # 1. 순수 오디오 포맷 먼저 찾기 (mhtml 제외)
                audio_formats = [
                    f for f in formats 
                    if f.get('acodec') != 'none' 
                    and f.get('vcodec') == 'none'
                    and f.get('ext') != 'mhtml'  # mhtml 제외
                    and f.get('url')  # URL이 있는 것만
                ]
                
                # 2. 순수 오디오가 없으면 비디오+오디오 포맷에서 오디오만 추출 가능한 것 찾기
                if not audio_formats:
                    audio_formats = [
                        f for f in formats 
                        if f.get('acodec') != 'none' 
                        and f.get('url')
                        and f.get('ext') != 'mhtml'  # mhtml 제외
                    ]
                
                # 3. 여전히 없으면 모든 포맷에서 URL이 있는 것 찾기 (mhtml 제외)
                if not audio_formats:
                    audio_formats = [
                        f for f in formats 
                        if f.get('url')
                        and f.get('ext') != 'mhtml'  # mhtml 제외
                    ]
                
                if not audio_formats:
                    # 디버깅을 위한 포맷 정보 출력
                    print(f"사용 가능한 포맷: {len(formats)}개")
                    for i, fmt in enumerate(formats[:5]):  # 처음 5개만 출력
                        print(f"  {i}: {fmt.get('format_id', 'N/A')} - {fmt.get('ext', 'N/A')} - acodec: {fmt.get('acodec', 'N/A')} - vcodec: {fmt.get('vcodec', 'N/A')}")
                    
                    # YouTube Premium 사용자에게 특별 안내
                    browser = config.get("youtube_cookies_browser", "none")
                    if browser != "none":
                        raise Exception("이 콘텐츠는 DRM으로 보호되어 다운로드할 수 없습니다. (YouTube Premium 콘텐츠)")
                    else:
                        raise Exception("이 콘텐츠는 DRM으로 보호되어 다운로드할 수 없습니다. 브라우저 쿠키를 사용해보세요.")
                
                # 가장 좋은 품질의 오디오 스트림 선택 (여러 기준으로)
                def get_quality_score(fmt):
                    score = 0
                    # 비트레이트가 높을수록 좋음
                    score += fmt.get('abr', 0) or 0
                    # 파일 크기가 클수록 좋음 (일반적으로)
                    score += fmt.get('filesize', 0) or 0
                    # 순수 오디오 포맷 우선
                    if fmt.get('vcodec') == 'none':
                        score += 1000
                    return score
                
                best_audio = max(audio_formats, key=get_quality_score)
                stream_url = best_audio.get('url')
                
                # 스트림 URL이 None이거나 빈 문자열인 경우 처리
                if not stream_url or stream_url is None:
                    # 대안 URL 필드들 확인
                    alternative_urls = [
                        best_audio.get('fragment_base_url'),
                        best_audio.get('base_url'),
                        best_audio.get('manifest_url')
                    ]
                    
                    for alt_url in alternative_urls:
                        if alt_url and alt_url is not None:
                            stream_url = alt_url
                            break
                    
                    if not stream_url or stream_url is None:
                        raise Exception("스트림 URL을 가져올 수 없습니다. (URL이 None입니다)")
                
                print(f"선택된 스트림: {best_audio.get('format_id', 'N/A')} - {best_audio.get('ext', 'N/A')} - {best_audio.get('abr', 'N/A')}kbps")
                
                self.progress_updated.emit(self.video_id, "스트림 준비 완료")
                self.stream_ready.emit(self.video_id, stream_url, self.title)
                
        except Exception as e:
            error_str = str(e)
            if 'NoneType' in error_str and 'decode' in error_str:
                # NoneType decode 오류는 스트림 URL 문제
                print(f"스트림 URL 추출 실패 (NoneType decode): {self.video_id}")
                self.fallback_download.emit(self.video_id, self.title)
                return
            elif 'Unsupported URL' in error_str:
                msg = "지원하지 않는 URL입니다."
            elif 'Video unavailable' in error_str:
                msg = "영상을 재생할 수 없습니다."
            elif 'HTTP Error 429' in error_str:
                msg = "너무 많은 요청을 보냈습니다. 잠시 후 다시 시도하세요."
            elif 'DRM으로 보호되어 다운로드할 수 없습니다' in error_str:
                # YouTube Premium 사용자에게 특별 안내
                browser = config.get("youtube_cookies_browser", "none")
                if browser != "none":
                    msg = "이 콘텐츠는 DRM으로 보호되어 다운로드할 수 없습니다.\n\nYouTube Premium 콘텐츠는 DRM 보호가 적용되어 yt-dlp로 다운로드할 수 없습니다.\n\n해결 방법:\n1. 일반 YouTube 영상으로 시도해보세요\n2. 브라우저에서 직접 재생하세요\n3. 다른 음악으로 시도해보세요"
                else:
                    msg = "이 콘텐츠는 DRM으로 보호되어 다운로드할 수 없습니다.\n\nYouTube Premium 사용자라면:\n1. config.json에서 'youtube_cookies_browser'를 'chrome'으로 설정\n2. Chrome에서 YouTube Premium으로 로그인\n3. 브라우저 완전 종료 후 관리자 권한으로 실행\n\n또는 일반 YouTube 영상으로 시도해보세요."
            elif '오디오 스트림을 찾을 수 없습니다' in error_str:
                # 스트리밍 실패 시 다운로드 방식으로 폴백
                print(f"스트림 실패, 다운로드 방식으로 폴백: {self.video_id}")
                self.fallback_download.emit(self.video_id, self.title)
                return
            else:
                msg = (error_str[:100] + '...') if len(error_str) > 100 else error_str
            self.stream_error.emit(self.video_id, f"스트림 준비 중 오류 발생:\n{msg}")

class SongItemWidget(QWidget):
    def __init__(self, video_id, title, channel, thumbnail_url, parent=None):
        super().__init__(parent)
        self.video_id = video_id
        self.title_text = title
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(64, 64)
        self.thumbnail_label.setStyleSheet("border-radius: 5px;")
        self.thumbnail_label.setScaledContents(True)
        layout.addWidget(self.thumbnail_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(10, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.title_label.setStyleSheet("color: white;")
        
        self.channel_label = QLabel(channel)
        self.channel_label.setFont(QFont("Arial", 9))
        self.channel_label.setStyleSheet("color: #aaa;")

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.channel_label)
        text_layout.addStretch()

        layout.addLayout(text_layout)
        layout.addStretch()

        self.status_label = QLabel("대기")
        self.status_label.setStyleSheet("color: #ccc; font-style: italic;")
        layout.addWidget(self.status_label)

        self.load_thumbnail(thumbnail_url)

    def load_thumbnail(self, url):
        # 썸네일 로딩을 위한 스레드 (선택적이지만 UI 프리징 방지에 좋음)
        self._thumbnail_thread = threading.Thread(target=self._fetch_thumbnail, args=(url,), daemon=True)
        self._thumbnail_thread.start()

    def _fetch_thumbnail(self, url):
        try:
            data = requests.get(url).content
            image = QImage()
            image.loadFromData(data)
            pixmap = QPixmap.fromImage(image)
            self.thumbnail_label.setPixmap(pixmap)
        except Exception as e:
            print(f"썸네일 로딩 실패: {e}")
            self.thumbnail_label.setText("X") # 로딩 실패 시

class MusicPlayerPage(QWidget):
    song_downloaded = pyqtSignal(str)
    
    def __init__(self, youtube_api, parent=None):
        super().__init__(parent)
        self.youtube_api = youtube_api
        self.download_cache = {}
        self.current_playlist = [] # (video_id, title)
        self.current_index = -1
        self.media_player = QMediaPlayer(self)
        self.media_player.error.connect(self.on_media_error)
        try:
            self.media_player.setProperty("audioRole", "music")
        except Exception as e:
            print(f"미디어 플레이어 백엔드 설정 실패: {e}")
        # Qt Designer UI 불러오기
        ui_path = os.path.join(PROJECT_ROOT, "ui", "music_player_page.ui")
        uic.loadUi(ui_path, self)
        
        # UI 텍스트 설정
        self.search_input.setPlaceholderText("노래를 검색하세요...")
        self.playlist_title.setText("재생목록")
        self.btn_remove.setText("삭제")
        self.btn_save.setText("저장")
        self.song_title_label.setText("노래 제목")
        self.song_artist_label.setText("아티스트")
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        
        # PlaylistManager 초기화
        self.playlist_manager = PlaylistManager()
        self.load_user_playlist()

        self.connect_signals()
        
    def init_ui(self):
        # 전체를 감싸는 HBox (좌: 메인, 우: 재생목록 패널)
        self.outer_layout = QHBoxLayout(self)
        self.outer_layout.setContentsMargins(0,0,0,0)
        self.outer_layout.setSpacing(0)

        # --- 메인 플레이어 영역 ---
        main_widget = QWidget(self)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # 상단 바 (검색 + 우측 확장 버튼)
        search_bar = QFrame(main_widget)
        search_bar.setLayout(QHBoxLayout())
        search_bar.layout().setContentsMargins(10,10,10,10)
        search_bar.setFixedHeight(50)
        self.search_input = QLineEdit(main_widget)
        self.search_input.setPlaceholderText("Search for a song...")
        self.search_input.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; border-radius: 5px; padding: 5px;")
        search_bar.layout().addWidget(self.search_input)
        search_bar.layout().addStretch()
        # 우측 상단 확장/축소 버튼
        self.toggle_playlist_btn = QPushButton("≡", main_widget)
        self.toggle_playlist_btn.setFixedSize(32,32)
        self.toggle_playlist_btn.setStyleSheet("border: none; color: #fff; font-size: 20px; background: #444; border-radius: 5px;")
        search_bar.layout().addWidget(self.toggle_playlist_btn)

        # 검색 목록
        self.playlist_widget = QListWidget(main_widget)
        self.playlist_widget.setStyleSheet("""
            QListWidget {
                background-color: #181818;
                border: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #333;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #555;
            }
        """)

        # 하단 컨트롤 바
        control_bar = self.create_control_bar()

        main_layout.addWidget(search_bar)
        main_layout.addWidget(self.playlist_widget)
        main_layout.addWidget(control_bar)
        main_widget.setLayout(main_layout)

        # --- 우측 재생목록 패널 ---
        self.playlist_panel = self.user_playlist_widget.parentWidget()
        self.playlist_panel.setStyleSheet("background: #232323; border-left: 1px solid #444;")
        playlist_panel_layout = QVBoxLayout(self.playlist_panel)
        playlist_panel_layout.setContentsMargins(10,10,10,10)
        playlist_panel_layout.setSpacing(5)
        title = QLabel("재생목록 관리", self.playlist_panel)
        title.setStyleSheet("color: #fff; font-weight: bold; font-size: 16px;")
        playlist_panel_layout.addWidget(title)
        # 재생목록 리스트
        self.user_playlist_widget = QListWidget(self.playlist_panel)
        self.user_playlist_widget.setStyleSheet("background: #232323; color: #fff; border: none;")
        playlist_panel_layout.addWidget(self.user_playlist_widget, 1)
        # 하단 버튼들
        btn_layout = QHBoxLayout()
        self.btn_remove = QPushButton("삭제")
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_save = QPushButton("저장")
        for b in [self.btn_remove, self.btn_up, self.btn_down, self.btn_save]:
            b.setStyleSheet("background: #444; color: #fff; border-radius: 4px; padding: 4px 8px;")
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addWidget(self.btn_save)
        playlist_panel_layout.addLayout(btn_layout)
        self.playlist_panel.setLayout(playlist_panel_layout)
        self.playlist_panel.hide()

        # 레이아웃 배치
        self.outer_layout.addWidget(main_widget, stretch=1)
        self.outer_layout.addWidget(self.playlist_panel, stretch=0)
        self.setLayout(self.outer_layout)

        # 토글 버튼 연결
        self.toggle_playlist_btn.clicked.connect(self.toggle_playlist_panel)

        # PlaylistManager 인스턴스 생성
        self.playlist_manager = PlaylistManager()
        self.load_user_playlist()
        # 시그널 연결
        self.user_playlist_widget.itemDoubleClicked.connect(self.play_song_from_user_playlist)
        self.btn_remove.clicked.connect(self.remove_selected_song)
        self.btn_up.clicked.connect(self.move_selected_song_up)
        self.btn_down.clicked.connect(self.move_selected_song_down)
        self.btn_save.clicked.connect(self.save_user_playlist)

        self.playlist_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.show_search_context_menu)

    def create_control_bar(self):
        bar = QFrame(self)
        bar.setStyleSheet("""
            background-color: #181818;
            border-radius: 10px;
            border: 1px solid #222;
        """)
        bar.setFixedHeight(100)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(5)

        # 상단: 메인 컨트롤 (좌/중앙/우)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # 좌측: (볼륨, 반복, 셔플, 펼치기 등은 그대로)
        left_layout = QHBoxLayout()
        # (이전/재생/다음 버튼은 아래 seek_layout으로 이동)
        top_layout.addLayout(left_layout)

        # 중앙: 앨범 아트 + 곡 정보
        center_layout = QVBoxLayout()
        center_layout.setSpacing(0)
        self.album_art_label = QLabel()
        self.album_art_label.setFixedSize(48, 48)
        self.album_art_label.setStyleSheet("border-radius: 8px; background: #222;")
        self.album_art_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.album_art_label, alignment=Qt.AlignHCenter)
        self.song_title_label = QLabel("노래 제목")
        self.song_title_label.setStyleSheet("color: #fff; font-weight: bold; font-size: 18px;")
        self.song_artist_label = QLabel("아티스트 · 곡명")
        self.song_artist_label.setStyleSheet("color: #aaa; font-size: 13px;")
        center_layout.addWidget(self.song_title_label, alignment=Qt.AlignHCenter)
        center_layout.addWidget(self.song_artist_label, alignment=Qt.AlignHCenter)
        top_layout.addLayout(center_layout, stretch=2)

        # 우측: 볼륨, 반복, 셔플, 펼치기(아래 화살표)
        right_layout = QHBoxLayout()
        right_layout.setSpacing(10)
        self.volume_button = QPushButton("")
        self.volume_button.setObjectName("volume_button")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.repeat_button = QPushButton("")
        self.repeat_button.setObjectName("repeat_button")
        self.shuffle_button = QPushButton("")
        self.shuffle_button.setObjectName("shuffle_button")
        self.expand_button = QPushButton("")
        self.expand_button.setObjectName("expand_button")
        for btn in [self.volume_button, self.repeat_button, self.shuffle_button, self.expand_button]:
            btn.setFixedSize(28, 28)
        right_layout.addWidget(self.volume_button)
        right_layout.addWidget(self.volume_slider)
        right_layout.addWidget(self.repeat_button)
        right_layout.addWidget(self.shuffle_button)
        right_layout.addWidget(self.expand_button)
        top_layout.addLayout(right_layout)

        layout.addLayout(top_layout)

        # 하단: 재생 위치 슬라이더 + 시간 + 컨트롤 버튼
        seek_layout = QHBoxLayout()
        seek_layout.setSpacing(8)
        self.prev_button = QPushButton("")
        self.prev_button.setObjectName("prev_button")
        self.play_pause_button = QPushButton("")
        self.play_pause_button.setObjectName("play_pause_button")
        self.next_button = QPushButton("")
        self.next_button.setObjectName("next_button")
        for btn in [self.prev_button, self.play_pause_button, self.next_button]:
            btn.setFixedSize(36, 36)
            btn.setStyleSheet("border: none; background: transparent;")
        seek_layout.addWidget(self.prev_button)
        seek_layout.addWidget(self.play_pause_button)
        seek_layout.addWidget(self.next_button)
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("color: #aaa; font-size: 12px;")
        seek_layout.addWidget(self.current_time_label)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setStyleSheet("QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; } QSlider::handle:horizontal { background: #fff; border: 1px solid #888; width: 12px; margin: -5px 0; border-radius: 6px; }")
        seek_layout.addWidget(self.seek_slider)
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("color: #aaa; font-size: 12px;")
        seek_layout.addWidget(self.total_time_label)
        layout.addLayout(seek_layout)

        return bar
        
    def connect_signals(self):
        self.search_input.returnPressed.connect(self.search_songs)
        self.playlist_widget.itemDoubleClicked.connect(self.play_song_from_list)
        
        # 미디어 플레이어 시그널
        self.media_player.stateChanged.connect(self.update_play_pause_button)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        
        # 컨트롤 버튼 시그널
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.next_button.clicked.connect(self.play_next)
        self.prev_button.clicked.connect(self.play_previous)
        self.seek_slider.sliderMoved.connect(self.media_player.setPosition)
        self.volume_slider.valueChanged.connect(self.media_player.setVolume)
        self.volume_button.clicked.connect(self.toggle_mute)
        
        # 재생목록 관리 시그널
        self.toggle_playlist_btn.clicked.connect(self.toggle_playlist_panel)
        self.user_playlist_widget.itemDoubleClicked.connect(self.play_song_from_user_playlist)
        self.btn_remove.clicked.connect(self.remove_selected_song)
        self.btn_up.clicked.connect(self.move_selected_song_up)
        self.btn_down.clicked.connect(self.move_selected_song_down)
        self.btn_save.clicked.connect(self.save_user_playlist)
        
        # 컨텍스트 메뉴
        self.playlist_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.show_search_context_menu)
        
        self.song_downloaded.connect(self.on_song_downloaded)

    def search_songs(self):
        query = self.search_input.text()
        if not query:
            return
        
        self.playlist_widget.clear()
        self.current_playlist = []
        
        try:
            results = self.youtube_api.search(query)
            if "items" not in results:
                print("API Error:", results)
                return

            for item in results.get("items", []):
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                channel = item["snippet"]["channelTitle"]
                thumbnail = item["snippet"]["thumbnails"]["default"]["url"]
                
                self.current_playlist.append((video_id, title, channel, thumbnail))

                list_item = QListWidgetItem(self.playlist_widget)
                list_item.setSizeHint(QSize(0, 80))
                widget = SongItemWidget(video_id, title, channel, thumbnail)
                self.playlist_widget.addItem(list_item)
                self.playlist_widget.setItemWidget(list_item, widget)

        except Exception as e:
            QMessageBox.critical(self, "API Error", f"Failed to search: {e}")
            
    def play_song_from_list(self, item):
        row = self.playlist_widget.row(item)
        self.play_song_at_index(row)

    def play_song_at_index(self, index):
        if 0 <= index < len(self.current_playlist):
            self.current_index = index
            video_id, title, channel, thumb_url = self.current_playlist[index]
            
            self.song_title_label.setText(title)
            self.song_artist_label.setText(channel)
            self._update_album_art(thumb_url)
            
            list_item = self.playlist_widget.item(index)
            widget = self.playlist_widget.itemWidget(list_item)
            
            if video_id in self.download_cache:
                stream_url = self.download_cache[video_id]
                # 스트림 URL을 QUrl로 변환하여 재생
                self.media_player.setMedia(QMediaContent(QUrl(stream_url)))
                self.media_player.play()
                if widget: widget.status_label.setText("재생 중")
            else:
                if widget: widget.status_label.setText("스트림 준비 중...")
                streamer = MusicStreamer(video_id, title)
                streamer.stream_ready.connect(self.on_stream_ready)
                streamer.stream_error.connect(self.on_stream_error)
                streamer.progress_updated.connect(self.on_stream_progress)
                streamer.fallback_download.connect(self.on_fallback_download)
                streamer.start()
                # 스레드가 GC되지 않도록 self에 저장
                if not hasattr(self, 'streamers'):
                    self.streamers = []
                self.streamers.append(streamer)

    def on_stream_progress(self, video_id, message):
        """스트림 진행 상태를 리스트 위젯에 업데이트"""
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            widget = self.playlist_widget.itemWidget(item)
            if widget and widget.video_id == video_id:
                widget.status_label.setText(message)
                break
    
    def on_stream_ready(self, video_id, stream_url, title):
        self.download_cache[video_id] = stream_url
        
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            widget = self.playlist_widget.itemWidget(item)
            if widget.video_id == video_id:
                widget.status_label.setText("준비 완료")
                if self.current_index == i:
                     # 스트림 URL을 QUrl로 변환하여 재생
                     self.media_player.setMedia(QMediaContent(QUrl(stream_url)))
                     self.media_player.play()
                     widget.status_label.setText("재생 중")
                break
                
    def on_stream_error(self, video_id, error_message):
        print(f"Error downloading {video_id}: {error_message}")
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            widget = self.playlist_widget.itemWidget(item)
            if widget.video_id == video_id:
                widget.status_label.setText("다운로드 실패")
                break

    def on_song_downloaded(self, video_id):
        if self.current_playlist and self.current_playlist[self.current_index][0] == video_id:
            stream_url = self.download_cache.get(video_id)
            if stream_url:
                # 스트림 URL을 QUrl로 변환하여 재생
                self.media_player.setMedia(QMediaContent(QUrl(stream_url)))
                self.media_player.play()

    def toggle_play_pause(self):
        if self.media_player.state() == QMediaPlayer.State.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def update_play_pause_button(self, state):
        pass  # QSS에서만 아이콘 관리

    def play_next(self):
        if self.current_index < len(self.current_playlist) - 1:
            self.play_song_at_index(self.current_index + 1)
        # Add logic for shuffle/repeat if needed

    def play_previous(self):
        if self.media_player.position() < 3000 and self.current_index > 0: # 3초 이내에 누르면 이전 곡
            self.play_song_at_index(self.current_index - 1)
        else:
            self.media_player.setPosition(0) # 아니면 처음부터 다시 재생

    def update_position(self, position):
        self.seek_slider.setValue(position)
        self.current_time_label.setText(self.format_time(position))
        
    def update_duration(self, duration):
        self.seek_slider.setRange(0, duration)
        self.total_time_label.setText(self.format_time(duration))

    def format_time(self, ms):
        seconds = int((ms/1000) % 60)
        minutes = int((ms/(1000*60)) % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _update_album_art(self, url):
        thread = threading.Thread(target=self.__fetch_album_art, args=(url,), daemon=True)
        thread.start()

    def __fetch_album_art(self, url):
        try:
            data = requests.get(url).content
            image = QImage()
            image.loadFromData(data)
            pixmap = QPixmap.fromImage(image)
            self.album_art_label.setPixmap(pixmap.scaled(self.album_art_label.width(), self.album_art_label.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception as e:
            print(f"Error fetching album art: {e}")
            self.album_art_label.setText("X") # 로딩 실패 시

    def toggle_mute(self):
        if self.media_player.isMuted():
            self.media_player.setMuted(False)
            # 아이콘 변경 제거 (QSS에서만 관리)
        else:
            self.media_player.setMuted(True)
            # 아이콘 변경 제거 (QSS에서만 관리)

    def closeEvent(self, event):
        # 플레이어 닫을 때 미디어 정리
        self.media_player.stop()
        # 임시 파일 정리 (선택적)
        # for path in self.download_cache.values():
        #     if os.path.exists(path):
        #         os.remove(path)
        # super().closeEvent(event) # QWidget에는 closeEvent가 다른 방식으로 동작

    def on_media_error(self, error, error_string=""):
        """미디어 플레이어 오류 처리"""
        error_messages = {
            QMediaPlayer.Error.NoError: "오류 없음",
            QMediaPlayer.Error.ResourceError: f"리소스 오류: {error_string}",
            QMediaPlayer.Error.NetworkError: f"네트워크 오류: {error_string}",
            QMediaPlayer.Error.FormatError: f"포맷 오류: {error_string}",
            QMediaPlayer.Error.AccessDeniedError: f"접근 거부: {error_string}"
        }
        
        error_msg = error_messages.get(error, f"알 수 없는 오류 ({error}): {error_string}")
        print(f"미디어 플레이어 오류: {error_msg}")
        
        # 사용자에게 오류 알림
        QMessageBox.warning(self, "재생 오류", 
                          f"음악 재생 중 오류가 발생했습니다:\n{error_msg}\n\n"
                          "다운로드된 파일이 손상되었을 수 있습니다.")

    def on_fallback_download(self, video_id, title):
        """스트리밍 실패 시 다운로드 방식으로 폴백"""
        print(f"스트리밍 실패, 다운로드 방식으로 폴백: {video_id}")
        
        # 다운로드 방식으로 재시도
        downloader = MusicDownloader(video_id, title)
        downloader.download_finished.connect(self.on_download_finished)
        downloader.download_error.connect(self.on_stream_error)  # 같은 오류 처리 사용
        downloader.progress_updated.connect(self.on_stream_progress)  # 같은 진행 상태 사용
        downloader.start()
        
        # 스레드가 GC되지 않도록 self에 저장
        if not hasattr(self, 'downloaders'):
            self.downloaders = []
        self.downloaders.append(downloader)

    def on_download_finished(self, video_id, file_path, title):
        """다운로드 완료 처리 (폴백용)"""
        self.download_cache[video_id] = file_path
        
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            widget = self.playlist_widget.itemWidget(item)
            if widget.video_id == video_id:
                widget.status_label.setText("준비 완료")
                if self.current_index == i:
                     self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
                     self.media_player.play()
                     widget.status_label.setText("재생 중")
                break

    def toggle_playlist_panel(self):
        if self.playlist_panel.isVisible():
            self.playlist_panel.hide()
        else:
            self.playlist_panel.show()

    def load_user_playlist(self):
        self.user_playlist_widget.clear()
        for song in self.playlist_manager.get_all():
            item = QListWidgetItem(f"{song['title']} - {song['channel']}")
            self.user_playlist_widget.addItem(item)

    def play_song_from_user_playlist(self, item):
        row = self.user_playlist_widget.row(item)
        song = self.playlist_manager.get_all()[row]
        # 재생목록에 곡이 없으면 추가
        found = False
        for idx, entry in enumerate(self.current_playlist):
            if entry[0] == song['video_id']:
                self.play_song_at_index(idx)
                found = True
                break
        if not found:
            # 곡을 현재 플레이리스트에 추가 후 재생
            self.current_playlist.append((song['video_id'], song['title'], song['channel'], song['thumbnail']))
            list_item = QListWidgetItem(self.playlist_widget)
            list_item.setSizeHint(QSize(0, 80))
            widget = SongItemWidget(song['video_id'], song['title'], song['channel'], song['thumbnail'])
            self.playlist_widget.addItem(list_item)
            self.playlist_widget.setItemWidget(list_item, widget)
            self.play_song_at_index(len(self.current_playlist)-1)

    def remove_selected_song(self):
        row = self.user_playlist_widget.currentRow()
        if row >= 0:
            self.playlist_manager.remove_song(row)
            self.load_user_playlist()

    def move_selected_song_up(self):
        row = self.user_playlist_widget.currentRow()
        if row > 0:
            self.playlist_manager.move_song(row, row-1)
            self.load_user_playlist()
            self.user_playlist_widget.setCurrentRow(row-1)

    def move_selected_song_down(self):
        row = self.user_playlist_widget.currentRow()
        if 0 <= row < len(self.playlist_manager.get_all())-1:
            self.playlist_manager.move_song(row, row+1)
            self.load_user_playlist()
            self.user_playlist_widget.setCurrentRow(row+1)

    def save_user_playlist(self):
        self.playlist_manager.save()
        QMessageBox.information(self, "저장 완료", "재생목록이 저장되었습니다.")

    # 곡을 재생목록에 추가하는 함수 예시 (검색 결과에서 우클릭 등으로 호출 가능)
    def add_song_to_user_playlist(self, video_id, title, channel, thumbnail):
        self.playlist_manager.add_song({
            'video_id': video_id,
            'title': title,
            'channel': channel,
            'thumbnail': thumbnail
        })
        self.load_user_playlist()

    def show_search_context_menu(self, pos):
        item = self.playlist_widget.itemAt(pos)
        if not item:
            return
        row = self.playlist_widget.row(item)
        if not (0 <= row < len(self.current_playlist)):
            return
        video_id, title, channel, thumbnail = self.current_playlist[row]
        menu = QMenu(self)
        add_action = QAction("재생목록에 추가", self)
        menu.addAction(add_action)
        def add_to_playlist():
            # 이미 재생목록에 있는 곡은 중복 추가 방지
            for song in self.playlist_manager.get_all():
                if song['video_id'] == video_id:
                    QMessageBox.information(self, "알림", "이미 재생목록에 있는 곡입니다.")
                    return
            self.add_song_to_user_playlist(video_id, title, channel, thumbnail)
            
        add_action.triggered.connect(add_to_playlist)
        menu.exec_(self.playlist_widget.mapToGlobal(pos))

# --- 자동 업데이트 클래스 ---
class AutoUpdater(QThread):
    """자동 업데이트를 처리하는 스레드"""
    update_available = pyqtSignal(str)
    update_complete = pyqtSignal()
    update_error = pyqtSignal(str)
    
    def __init__(self, current_version="1.0.2"):
        super().__init__()
        self.current_version = current_version
        self.github_repo = config.get("github_repo", "your-username/your-repo")
        self.update_interval = config.get("update_interval", 3600)
        self.running = True
        # github_repo가 None이 아닌지 확인하여 타입 오류 방지
        if self.github_repo is None:
            self.github_repo = "your-username/your-repo"
        self.update_manager = UpdateManager(
            current_version,
            config.get("github_repo", "SeoS4090/PyTools") or "SeoS4090/PyTools"
        )
        
    def run(self):
        while self.running:
            try:
                self.check_for_updates()
                interval = self.update_interval if isinstance(self.update_interval, int) and self.update_interval > 0 else 3600
                for _ in range(interval):
                    if not self.running:
                        break
                    self.msleep(1000)  # 1초씩 쪼개서 체크
            except Exception as e:
                self.update_error.emit(f"업데이트 체크 중 오류: {str(e)}")
                interval = self.update_interval if isinstance(self.update_interval, int) and self.update_interval > 0 else 3600
                for _ in range(interval):
                    if not self.running:
                        break
                    self.msleep(1000)
    def check_for_updates(self):
        """GitHub에서 최신 버전 확인"""
        try:
            result = self.update_manager.check_for_updates()
            if result.get('available', False):
                self.update_available.emit(result['version'])
        except Exception as e:
            self.update_error.emit(f"업데이트 확인 실패: {str(e)}")
    
    def stop(self):
        self.running = False

# --- 메인 애플리케이션 창 ---
class LoginPage(QWidget):
    """구글 로그인을 위한 UI 페이지"""
    login_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(PROJECT_ROOT, "ui", "login_page.ui")
        uic.loadUi(ui_path, self)
        
        # UI 텍스트 설정
        self.title_label.setText("PyTools")
        self.subtitle_label.setText("YouTube 뮤직 플레이어")
        self.login_button.setText("Google로 로그인")
        self.status_label.setText("로그인을 시작하려면 버튼을 클릭하세요.")
        
        self.login_button.clicked.connect(self.login_requested)

    def set_status(self, message):
        """로그인 페이지에 상태 메시지를 설정합니다."""
        self.status_label.setText(message)
        QApplication.processEvents()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_path = os.path.join(PROJECT_ROOT, "ui", "main_window.ui")
        uic.loadUi(ui_path, self)
        self.version = config.get("version", "1.0.2") or "1.0.2"
        self.tray_icon = None
        self.updater = None
        self.music_player_page = None
        self.youtube_api = None
        self.ffmpeg_installer = None
        self.update_manager = UpdateManager(
            self.version,
            config.get("github_repo", "SeoS4090/PyTools") or "SeoS4090/PyTools"
        )
        self.google_connected = False
        self.google_userinfo = None
        self.google_tokens = None
        self.init_ui()
        self.load_theme(config.get("theme", "dark"))
        self.setup_tray()
        self.try_auto_login()
        if bool(config.get("auto_start", True)):
            self.setup_autostart()
        if config.get("check_updates", True):
            self.start_auto_updater()
        
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(f"PyTools v{self.version}")
        self.resize(800, 600)

        # --- 메뉴바 생성 ---
        self.create_menubar()

        # --- 상태바 생성 및 사용자 정보 위젯 추가 ---
        self.status_bar = self.statusBar()
        self.user_icon_label = QLabel()
        self.user_name_label = QLabel()
        
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0,0,5,0)
        status_layout.addStretch()
        status_layout.addWidget(self.user_icon_label)
        status_layout.addWidget(self.user_name_label)
        
        self.status_bar.addPermanentWidget(status_container)

        # --- 중앙 위젯을 QStackedWidget으로 설정 ---
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # 1. 로그인 페이지 생성
        self.login_page = LoginPage()
        self.login_page.login_requested.connect(self.google_auth)
        self.stacked_widget.addWidget(self.login_page)

        # 2. 뮤직 플레이어 페이지 (초기에는 비어있음)
        
        self.update_google_menu_state()
        
    def create_menubar(self):
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("File")
        load_cookie_action = QAction("쿠키 파일 불러오기", self)
        load_cookie_action.triggered.connect(self.load_cookie_file)
        file_menu.addAction(load_cookie_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_application)
        file_menu.addAction(exit_action)
        
        # 계정 메뉴
        account_menu = menubar.addMenu("Account")
        self.google_action = QAction("Google 로그인", self)
        self.google_action.triggered.connect(self.google_auth)
        account_menu.addAction(self.google_action)
        self.google_disconnect_action = QAction("Google 로그아웃", self)
        self.google_disconnect_action.triggered.connect(self.google_disconnect)
        account_menu.addAction(self.google_disconnect_action)
        
        # 기능 메뉴
        feature_menu = menubar.addMenu("Features")
        self.music_player_action = QAction("YouTube 뮤직 플레이어", self)
        self.music_player_action.triggered.connect(self.show_music_player_page)
        feature_menu.addAction(self.music_player_action)
        
        # 설정 메뉴
        setting_menu = menubar.addMenu("Setting")
        
        # 테마 서브메뉴
        theme_menu = setting_menu.addMenu("Theme")
        dark_theme_action = QAction("Dark", self)
        dark_theme_action.setCheckable(True)
        dark_theme_action.triggered.connect(lambda: self.apply_theme("dark"))
        light_theme_action = QAction("Light", self)
        light_theme_action.setCheckable(True)
        light_theme_action.triggered.connect(lambda: self.apply_theme("light"))
        theme_menu.addAction(dark_theme_action)
        theme_menu.addAction(light_theme_action)
        self.theme_actions = {"dark": dark_theme_action, "light": light_theme_action}

        setting_menu.addSeparator()

        # 쿠키 설정 액션 추가
        cookies_action = QAction("YouTube 쿠키 설정", self)
        cookies_action.triggered.connect(self.show_cookie_settings)
        setting_menu.addAction(cookies_action)

        env_action = QAction("환경 설정", self)
        env_action.triggered.connect(self.show_env_settings)
        setting_menu.addAction(env_action)
        
        # 도움말 메뉴
        about_menu = menubar.addMenu("About")
        help_action = QAction("Help", self)
        help_action.triggered.connect(self.show_about)
        about_menu.addAction(help_action)
        
    def setup_tray(self):
        """시스템 트레이 설정"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        
        tray_menu = QMenu()
        
        show_action = QAction("열기", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        about_action = QAction("정보 보기", self)
        about_action.triggered.connect(self.show_about)
        tray_menu.addAction(about_action)
        
        settings_action = QAction("설정", self)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("종료", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
        
    def tray_icon_activated(self, reason):
        """트레이 아이콘 클릭 처리"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()
    
    def show_window(self):
        """창을 보이게 하고 포커스"""
        self.show()
        self.raise_()
        self.activateWindow()
        
    def minimize_to_tray(self):
        """트레이로 최소화"""
        self.hide()
        if self.tray_icon:
            self.tray_icon.showMessage(
                "PyTools",
                "애플리케이션이 트레이로 최소화되었습니다.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        
    def apply_theme(self, theme_name):
        config.set("theme", theme_name)
        self.load_theme(theme_name)

    def load_theme(self, theme_name):
        """QSS 파일을 읽어 테마를 적용"""
        # 테마 액션 상태 업데이트
        for name, action in self.theme_actions.items():
            action.setChecked(name == theme_name)
            
        theme_path = os.path.join(PROJECT_ROOT, "ui", "themes", f"{theme_name}.qss")
        if os.path.exists(theme_path):
            with open(theme_path, "r", encoding="utf-8") as f:
                style_sheet = f.read()
                # 상대경로를 절대경로로 치환
                icon_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "ui", "icons"))
                style_sheet = style_sheet.replace(
                    "url(../icons/", f"url({icon_dir.replace('\\', '/')}/"
                )
                self.setStyleSheet(style_sheet)
        else:
            print(f"테마 파일을 찾을 수 없습니다: {theme_path}")
            self.setStyleSheet("") # 기본 스타일로 복원

    def show_music_player_page(self):
        """뮤직 플레이어 페이지로 전환"""
        if self.music_player_page:
            self.stacked_widget.setCurrentWidget(self.music_player_page)

    def show_about(self):
        about_text = f"""
PyTools 애플리케이션\n\n버전: {self.version}\n기능:\n- 시스템 트레이 지원\n- 자동 시작\n- 자동 업데이트\n- Google 연동 YouTube 플레이어\n\n개발자: SeoS4090\nGitHub: {config.get("github_repo", "SeoS4090/PyTools")}
        """
        QMessageBox.information(self, "프로그램 정보 (Help)", about_text)
        
    def show_settings(self):
        """설정 창 표시"""
        settings_text = f"""
현재 설정:

버전: {self.version}
GitHub 저장소: {config.get("github_repo")}
자동 시작: {'활성화' if config.get("auto_start") else '비활성화'}
자동 업데이트: {'활성화' if config.get("check_updates") else '비활성화'}
업데이트 간격: {config.get("update_interval")}초
        """
        QMessageBox.information(self, "설정", settings_text)
        
    def show_env_settings(self):
        """환경 설정 다이얼로그 표시"""
        dlg = QDialog(self)
        dlg.setWindowTitle("환경 설정")
        dlg.setModal(True)
        dlg.resize(300, 150)
        layout = QVBoxLayout(dlg)

        auto_start_chk = QCheckBox("윈도우 시작시 자동 실행")
        auto_start_chk.setChecked(bool(config.get("auto_start", True)))
        if not winreg:
            auto_start_chk.setEnabled(False)
            auto_start_chk.setText("윈도우 시작시 자동 실행 (Windows 전용)")
        layout.addWidget(auto_start_chk)

        tray_chk = QCheckBox("닫기 버튼을 누르면 트레이로 이동")
        tray_chk.setChecked(bool(config.get("minimize_to_tray", True)))
        layout.addWidget(tray_chk)

        save_btn = QPushButton("Save")
        layout.addWidget(save_btn)

        def save_settings():
            config.set("auto_start", auto_start_chk.isChecked())
            config.set("minimize_to_tray", tray_chk.isChecked())
            
            if winreg:
                if auto_start_chk.isChecked():
                    self.setup_autostart()
                else:
                    try:
                        key = winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0,
                            winreg.KEY_SET_VALUE
                        )
                        winreg.DeleteValue(key, "PyTools")
                        winreg.CloseKey(key)
                    except FileNotFoundError:
                        pass # 키나 값이 없으면 무시
                    except Exception as e:
                        self.log_message(f"자동 시작 해제 실패: {e}")

            QMessageBox.information(self, "환경 설정", "설정이 저장되었습니다.")
            dlg.accept()

        save_btn.clicked.connect(save_settings)
        dlg.exec_()
        
    def quit_application(self):
        """애플리케이션 종료"""
        if self.updater:
            self.updater.stop()
        if self.tray_icon:
            self.tray_icon.hide()
        
        # 플레이어 페이지가 존재하면 정리 로직 호출
        if self.music_player_page:
            self.music_player_page.closeEvent(None) 
            
        QApplication.quit()
        
    def setup_autostart(self):
        """자동 시작 설정"""
        if not winreg:
            self.log_message("자동 시작 설정은 Windows에서만 지원됩니다.")
            return
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            
            app_path = sys.executable
            if app_path.endswith('pythonw.exe'): # 개발 환경
                script_path = os.path.abspath(__file__)
                app_path = f'"{app_path}" "{script_path}"'
            else: # 배포 환경
                app_path = f'"{app_path}"'
                
            winreg.SetValueEx(key, "PyTools", 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
            self.log_message("자동 시작이 설정되었습니다.")
        except Exception as e:
            self.log_message(f"자동 시작 설정 실패: {str(e)}")
            
    def start_auto_updater(self):
        self.updater = AutoUpdater(self.version)
        self.updater.update_available.connect(self.on_update_available)
        self.updater.update_error.connect(self.on_update_error)
        self.updater.start()
        
    def on_update_available(self, new_version):
        reply = QMessageBox.question(
            self,
            "업데이트 알림",
            f"새로운 버전 {new_version}이 사용 가능합니다.\n지금 업데이트하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.perform_update(new_version)
            
    def perform_update(self, new_version):
        try:
            self.log_message(f"업데이트를 시작합니다: {new_version}")
            download_url = f"https://github.com/{config.get('github_repo')}/releases/latest/download/PyTools-{new_version}.zip"
            update_file = f"update-{new_version}.zip"
            
            if self.update_manager.download_update(download_url, update_file):
                if self.update_manager.install_update(update_file):
                    restart_script = self.update_manager.create_restart_script()
                    subprocess.Popen([sys.executable, restart_script])
                    self.quit_application()
                else:
                    QMessageBox.critical(self, "업데이트 실패", "업데이트 설치에 실패했습니다.")
            else:
                QMessageBox.critical(self, "업데이트 실패", "업데이트 파일 다운로드에 실패했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "업데이트 실패", f"업데이트 중 오류가 발생했습니다:\n{str(e)}")
            
    def on_update_error(self, error_message):
        self.log_message(f"업데이트 오류: {error_message}")
        
    def log_message(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def closeEvent(self, event):
        if bool(config.get("minimize_to_tray", True)):
            event.ignore()
            self.minimize_to_tray()
        else:
            config.update({
                "window_position": {"x": self.x(), "y": self.y()},
                "window_size": {"width": self.width(), "height": self.height()}
            })
            event.accept()
            self.quit_application()

    # --- 구글 OAuth2 연동 ---
    def update_google_menu_state(self):
        """구글 연동 상태에 따라 메뉴 활성화/비활성화"""
        self.google_connected = self.youtube_api is not None
        self.google_action.setEnabled(not self.google_connected)
        self.google_disconnect_action.setEnabled(self.google_connected)
        self.music_player_action.setEnabled(self.google_connected)
        self.update_google_userinfo_ui()

    def update_google_userinfo_ui(self):
        """상태바에 구글 사용자 정보(아이콘, 이름) 표시"""
        if self.google_connected and self.google_userinfo:
            name = self.google_userinfo.get("name", "")
            self.user_name_label.setText(f"  {name}  ")
            picture_url = self.google_userinfo.get("picture")
            if picture_url:
                thread = Thread(target=self._load_user_picture, args=(picture_url,), daemon=True)
                thread.start()
        else:
            self.user_name_label.clear()
            self.user_icon_label.clear()
            
    def _load_user_picture(self, url):
        try:
            data = requests.get(url).content
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.user_icon_label.setPixmap(
                pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        except Exception as e:
            self.log_message(f"Failed to load user picture: {e}")
            self.user_icon_label.clear()

    def launch_music_player(self):
        """YouTube 뮤직 플레이어 실행"""
        if not self.youtube_api:
            QMessageBox.warning(self, "로그인 필요", "뮤직 플레이어를 사용하려면 먼저 Google 로그인을 완료해주세요.")
            return
        
        if self.music_player_page and self.music_player_page.isVisible():
            self.music_player_page.activateWindow()
            return
        
        # FFmpeg 확인 및 자동 설치
        self.check_and_install_ffmpeg()
    
    def check_and_install_ffmpeg(self):
        """FFmpeg 확인 및 자동 설치"""
        installer = FFmpegInstaller()
        
        if installer.is_ffmpeg_installed():
            # FFmpeg가 이미 설치되어 있으면 바로 플레이어 실행
            self.create_music_player()
        else:
            # FFmpeg 설치 필요
            reply = QMessageBox.question(
                self, 
                "FFmpeg 설치 필요", 
                "음악 재생을 위해 FFmpeg가 필요합니다.\n\n자동으로 설치하시겠습니까? (약 50MB 다운로드)",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.install_ffmpeg_with_progress()
            else:
                QMessageBox.information(self, "설치 취소", "FFmpeg 설치가 취소되었습니다.\n음악 재생 기능을 사용할 수 없습니다.")
    
    def install_ffmpeg_with_progress(self):
        """진행률 표시와 함께 FFmpeg 설치"""
        # 진행률 다이얼로그 생성
        self.progress_dialog = QProgressDialog("FFmpeg 설치 중...", "취소", 0, 0, self)
        self.progress_dialog.setWindowTitle("FFmpeg 설치")
        self.progress_dialog.setModal(True)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        
        # FFmpeg 설치기 생성 및 시그널 연결
        self.ffmpeg_installer = FFmpegInstaller()
        self.ffmpeg_installer.progress_updated.connect(self.update_ffmpeg_progress)
        self.ffmpeg_installer.installation_complete.connect(self.on_ffmpeg_installation_complete)
        
        # 설치 시작
        self.ffmpeg_installer.start()
        self.progress_dialog.show()
    
    def update_ffmpeg_progress(self, message):
        """FFmpeg 설치 진행률 업데이트"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setLabelText(message)
            QApplication.processEvents()
    
    def on_ffmpeg_installation_complete(self, success, message):
        """FFmpeg 설치 완료 처리"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        if success:
            QMessageBox.information(self, "FFmpeg 설치 완료", message)
            self.on_login_success() # 로그인 성공 후처리 호출
        else:
            QMessageBox.critical(self, "FFmpeg 설치 실패", message)
    
    def on_login_success(self):
        """로그인 성공 후 공통 처리 (플레이어 생성 및 전환)"""
        # FFmpeg가 설치되어 있는지 먼저 확인
        installer = FFmpegInstaller()
        if not installer.is_ffmpeg_installed():
             # FFmpeg가 없으면 설치 프로세스 시작
            self.check_and_install_ffmpeg()
        else:
            # FFmpeg가 있으면 플레이어 페이지 생성 및 표시
            self.create_music_player()
            self.show_music_player_page()

    def create_music_player(self):
        """뮤직 플레이어 페이지를 생성하고 스택에 추가"""
        if self.music_player_page is not None:
            return # 이미 생성되었으면 아무것도 안 함

        try:
            self.music_player_page = MusicPlayerPage(self.youtube_api)
            self.stacked_widget.addWidget(self.music_player_page)
            # 테마가 즉시 적용되도록 스타일시트 다시 적용
            self.load_theme(config.get("theme", "dark"))
        except Exception as e:
            QMessageBox.critical(self, "오류", f"뮤직 플레이어 생성 중 오류가 발생했습니다:\n{str(e)}")
            self.music_player_page = None

    def google_auth(self):
        try:
            code = self._google_get_auth_code()
            if not code:
                QMessageBox.warning(self, "Google 연동", "인증 코득에 실패했습니다.")
                return
            tokens = self._google_get_tokens(code)
            if "access_token" not in tokens:
                QMessageBox.warning(self, "Google 연동", f"토큰 획득 실패: {tokens}")
                return
                
            userinfo = self._google_get_userinfo(tokens["access_token"])
            if "email" in userinfo:
                self.google_userinfo = userinfo
                self.google_tokens = tokens
                self.youtube_api = YouTubeAPIOAuth(tokens['access_token'])
                
                config.set('google_tokens', tokens)
                
                self.update_google_menu_state()
                QMessageBox.information(self, "Google 연동 성공", f"성공적으로 로그인되었습니다: {userinfo['email']}")
                
                # 로그인 성공 공통 처리
                self.on_login_success()
            else:
                QMessageBox.warning(self, "Google 연동 실패", f"사용자 정보 획득 실패: {userinfo}")
        except Exception as e:
            QMessageBox.critical(self, "Google 연동 오류", f"Google 인증 중 오류 발생:\n{str(e)}")

    def _google_get_auth_code(self):
        class OAuthHandler(BaseHTTPRequestHandler):
            code = None
            def do_GET(self):
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                if "code" in params:
                    OAuthHandler.code = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write("<h1>인증이 완료되었습니다. 창을 닫으세요.</h1>".encode("utf-8"))
                else:
                    self.send_response(400)
                    self.end_headers()
        
        server = HTTPServer(("localhost", 80), OAuthHandler)
        thread = Thread(target=server.handle_request, daemon=True)
        thread.start()

        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope={GOOGLE_SCOPE}&"
            "access_type=offline"
        )
        webbrowser.open(auth_url)

        # 타임아웃 추가
        timeout = 60  # 60초
        start_time = time.time()
        while OAuthHandler.code is None and time.time() - start_time < timeout:
            QApplication.processEvents()
            time.sleep(0.1)
        
        server.server_close()
        return OAuthHandler.code

    def _google_get_tokens(self, code):
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        response = requests.post(token_url, data=data)
        return response.json()

    def _google_get_userinfo(self, access_token):
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(userinfo_url, headers=headers)
        return response.json()

    def google_disconnect(self):
        """구글 연동 해제"""
        self.youtube_api = None
        self.google_userinfo = None
        self.google_tokens = None
        
        config.delete('google_tokens')
        
        # 뮤직 플레이어 페이지 정리 및 로그인 페이지로 전환
        if self.music_player_page:
            self.music_player_page.closeEvent(None) # 정리
            self.stacked_widget.removeWidget(self.music_player_page)
            self.music_player_page.deleteLater()
            self.music_player_page = None
        
        self.stacked_widget.setCurrentWidget(self.login_page) # 로그인 페이지로 전환
        
        self.update_google_menu_state()
        QMessageBox.information(self, "Google 연동 해제", "Google 연동이 해제되었습니다.")

    def show_cookie_settings(self):
        """YouTube 쿠키 설정 다이얼로그 표시"""
        dlg = QDialog(self)
        dlg.setWindowTitle("YouTube 쿠키 설정")
        layout = QVBoxLayout(dlg)

        explanation = """
<b>왜 이 설정이 필요한가요?</b><br><br>
YouTube 정책상 연령 제한 등 일부 콘텐츠는<br>
로그인된 사용자만 접근할 수 있습니다.<br><br>
이 앱은 Google 계정으로 로그인하지만, 보안 정책상<br>
해당 로그인 정보를 동영상 다운로드에 직접<br>
사용할 수 없습니다.<br><br>
대신, 실제 웹 브라우저의 인증 정보(쿠키)를<br>
안전하게 사용하여 해당 콘텐츠에 접근합니다.<br><br>
<b>주로 사용하시는 브라우저를 선택해주세요.</b>
"""
        label = QLabel(explanation)
        layout.addWidget(label)
        
        current_browser = config.get("youtube_cookies_browser", "none")
        
        self.rb_none = QRadioButton("사용 안함")
        self.rb_none.setChecked(current_browser == "none")
        layout.addWidget(self.rb_none)
        
        self.rb_chrome = QRadioButton("Chrome")
        self.rb_chrome.setChecked(current_browser == "chrome")
        layout.addWidget(self.rb_chrome)

        self.rb_firefox = QRadioButton("Firefox")
        self.rb_firefox.setChecked(current_browser == "firefox")
        layout.addWidget(self.rb_firefox)

        self.rb_edge = QRadioButton("Edge")
        self.rb_edge.setChecked(current_browser == "edge")
        layout.addWidget(self.rb_edge)

        button_box = QHBoxLayout()
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(dlg.accept)
        button_box.addStretch()
        button_box.addWidget(save_btn)
        layout.addLayout(button_box)

        if dlg.exec_():
            new_browser = "none"
            if self.rb_chrome.isChecked(): new_browser = "chrome"
            elif self.rb_firefox.isChecked(): new_browser = "firefox"
            elif self.rb_edge.isChecked(): new_browser = "edge"
            
            config.set("youtube_cookies_browser", new_browser)
            QMessageBox.information(self, "설정 저장", f"쿠키 설정이 '{new_browser}' (으)로 저장되었습니다.")

    def try_auto_login(self):
        """앱 시작 시 자동 로그인 시도"""
        tokens = config.get('google_tokens')
        if not tokens or 'refresh_token' not in tokens:
            return

        self.login_page.set_status("자동 로그인 시도 중...")
        
        # 1. 기존 access_token으로 사용자 정보 가져오기 시도
        userinfo = self._google_get_userinfo(tokens['access_token'])

        # 2. 실패 시 (토큰 만료 등), refresh_token으로 갱신 시도
        if 'error' in userinfo:
            new_tokens = self._google_refresh_token(tokens['refresh_token'])
            if not new_tokens or 'access_token' not in new_tokens:
                self.login_page.set_status("자동 로그인 실패. 다시 로그인해주세요.")
                config.delete('google_tokens')
                return
            
            # 기존 토큰에 새로운 값 업데이트
            tokens.update(new_tokens)
            userinfo = self._google_get_userinfo(tokens['access_token'])

        # 3. 최종적으로 사용자 정보 획득에 실패한 경우
        if 'error' in userinfo:
            self.login_page.set_status("자동 로그인 실패. 다시 로그인해주세요.")
            config.delete('google_tokens')
            return

        # 4. 자동 로그인 성공
        self.login_page.set_status("자동 로그인 성공!")
        self.google_userinfo = userinfo
        self.google_tokens = tokens
        self.youtube_api = YouTubeAPIOAuth(tokens['access_token'])
        config.set('google_tokens', tokens)
        self.update_google_menu_state()
        self.on_login_success()

    def _google_refresh_token(self, refresh_token):
        """refresh_token으로 새로운 access_token을 발급받습니다."""
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        response = requests.post(token_url, data=data)
        return response.json()

    def load_cookie_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "쿠키 파일 선택", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                import shutil
                dest_path = os.path.join(os.path.dirname(__file__), 'Cookie.txt')
                shutil.copyfile(file_path, dest_path)
                QMessageBox.information(self, "성공", "쿠키 파일이 성공적으로 복사되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"쿠키 파일 복사 중 오류 발생: {e}")

class MusicDownloader(QThread):
    """폴백용 다운로드 클래스"""
    download_finished = pyqtSignal(str, str, str)  # video_id, file_path, title
    download_error = pyqtSignal(str, str) # video_id, error_message
    progress_updated = pyqtSignal(str, str) # video_id, message
    
    def __init__(self, video_id, title):
        super().__init__()
        self.video_id = video_id
        self.title = title
        self.temp_dir = tempfile.gettempdir()
        
        # FFmpeg 경로 설정
        self.ffmpeg_path = self.find_ffmpeg()

    def find_ffmpeg(self):
        """FFmpeg 실행 파일 경로 찾기"""
        # 시스템 PATH에서 확인
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return 'ffmpeg'  # PATH에 있으면 그대로 사용
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 로컬 설치 경로 확인
        local_ffmpeg = os.path.join(os.path.expanduser("~"), "PyTools", "ffmpeg", "bin", "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
            
        return None
        
    def run(self):
        # 1. 캐시 폴더 생성
        cache_dir = os.path.join(os.path.dirname(__file__), 'music_cache')
        os.makedirs(cache_dir, exist_ok=True)
        final_mp3_path = os.path.join(cache_dir, f"{self.video_id}.mp3")
        source_audio_path = None
        try:
            # 2. 캐시에 mp3 파일이 이미 있는지 확인
            if os.path.exists(final_mp3_path):
                self.download_finished.emit(self.video_id, final_mp3_path, self.title)
                return

            # 3. yt-dlp 옵션 설정 (오디오만 다운로드, 쿠키 파일 우선)
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(cache_dir, f'{self.video_id}.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True, # 오류 무시하고 계속
            }
            # Cookie.txt 파일이 있으면 우선 사용
            cookie_path = os.path.join(os.path.dirname(__file__), 'Cookie.txt')
            used_cookie = False
            if os.path.exists(cookie_path):
                ydl_opts['cookies'] = cookie_path
                used_cookie = True
            else:
                # 브라우저 쿠키 설정이 있으면 사용
                browser = config.get("youtube_cookies_browser", "none")
                if browser != "none":
                    try:
                        ydl_opts['cookiesfrombrowser'] = (browser, 'Default')
                        used_cookie = True
                    except Exception as e:
                        print(f"브라우저 쿠키 접근 실패: {e}. 쿠키 없이 진행합니다.")

            if self.ffmpeg_path and self.ffmpeg_path != 'ffmpeg':
                ydl_opts['ffmpeg_location'] = os.path.dirname(self.ffmpeg_path)

            # 4. 다운로드 실행
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # video_id가 이미 완전한 URL인지 확인
                if self.video_id.startswith(('http://', 'https://')):
                    url = self.video_id
                else:
                    url = f"https://www.youtube.com/watch?v={self.video_id}"
                print(f"다운로드할 URL: {url}")
                info_dict = ydl.extract_info(url, download=True)
                if info_dict:
                    source_audio_path = info_dict.get('requested_downloads', [{}])[0].get('filepath')
                    if not source_audio_path:
                        source_audio_path = ydl.prepare_filename(info_dict)
                else:
                    source_audio_path = None

            if not source_audio_path or not os.path.exists(source_audio_path):
                raise FileNotFoundError("yt-dlp did not produce an output file.")

            # 5. FFmpeg로 MP3 변환 시도 (ffmpeg가 있을 때만)
            if self.ffmpeg_path and not source_audio_path.endswith('.mp3'):
                self.progress_updated.emit(self.video_id, "변환 중...")
                try:
                    ffmpeg_cmd = [
                        self.ffmpeg_path,
                        '-i', source_audio_path,
                        '-vn',
                        '-acodec', 'libmp3lame',
                        '-q:a', '2',
                        '-y',
                        final_mp3_path
                    ]
                    startupinfo = None
                    if sys.platform == "win32":
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.run(ffmpeg_cmd, check=True, capture_output=True, startupinfo=startupinfo)
                    if os.path.exists(final_mp3_path):
                        os.remove(source_audio_path)
                        self.download_finished.emit(self.video_id, final_mp3_path, self.title)
                        return
                except Exception as ffmpeg_error:
                    print(f"FFmpeg conversion failed: {ffmpeg_error}. Playing original format.")
                    self.download_finished.emit(self.video_id, source_audio_path, self.title)
                    return
            # 6. 변환이 필요 없거나 시도하지 않은 경우
            self.download_finished.emit(self.video_id, source_audio_path, self.title)
        except Exception as e:
            if source_audio_path and os.path.exists(source_audio_path):
                os.remove(source_audio_path)
            error_str = str(e)
            # 쿠키 없이 다운로드 실패 시 안내 메시지 추가
            if (not used_cookie) and (('login' in error_str.lower()) or ('age' in error_str.lower()) or ('cookies' in error_str.lower()) or ('sign in' in error_str.lower()) or ('private' in error_str.lower())):
                msg = ("다운로드에 실패했습니다.\n이 영상은 연령 제한, 로그인 필요, 또는 비공개 영상일 수 있습니다.\n\n" 
                       "해결 방법:\n1. 브라우저에서 로그인된 상태의 쿠키를 Cookie.txt로 저장해 주세요.\n2. 또는 프로그램의 쿠키 설정에서 브라우저를 지정해 주세요.")
            elif 'Unsupported URL' in error_str:
                msg = "지원하지 않는 URL입니다."
            elif 'Video unavailable' in error_str:
                msg = "영상을 재생할 수 없습니다."
            elif 'HTTP Error 429' in error_str:
                msg = "너무 많은 요청을 보냈습니다. 잠시 후 다시 시도하세요."
            else:
                msg = (error_str[:100] + '...') if len(error_str) > 100 else error_str
            self.download_error.emit(self.video_id, f"다운로드 중 오류 발생:\n{msg}")

class PlaylistManager:
    def __init__(self, playlist_file=None):
        if playlist_file is None:
            playlist_file = os.path.join(PROJECT_ROOT, 'data', 'playlist.json')
        self.playlist_file = playlist_file
        self.playlist = []
        self.load()

    def load(self):
        if os.path.exists(self.playlist_file):
            try:
                with open(self.playlist_file, 'r', encoding='utf-8') as f:
                    self.playlist = json.load(f)
            except Exception:
                self.playlist = []
        else:
            self.playlist = []

    def save(self):
        try:
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                json.dump(self.playlist, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"재생목록 저장 실패: {e}")

    def add_song(self, song):
        self.playlist.append(song)
        self.save()

    def remove_song(self, index):
        if 0 <= index < len(self.playlist):
            self.playlist.pop(index)
            self.save()

    def move_song(self, from_idx, to_idx):
        if 0 <= from_idx < len(self.playlist) and 0 <= to_idx < len(self.playlist):
            song = self.playlist.pop(from_idx)
            self.playlist.insert(to_idx, song)
            self.save()

    def get_all(self):
        return self.playlist

def main():
    # 애플리케이션에 대한 고유 ID 설정 (Windows 작업 표시줄 아이콘 그룹화 방지)
    if sys.platform == "win32":
        import ctypes
        myappid = 'seos4090.pytools.1.0' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # 테마 폴더 및 기본 테마 파일 생성
    themes_dir = os.path.join(PROJECT_ROOT, "ui", "themes")
    os.makedirs(themes_dir, exist_ok=True)
    dark_qss_path = os.path.join(themes_dir, "dark.qss")
    if not os.path.exists(dark_qss_path):
        with open(dark_qss_path, "w", encoding="utf-8") as f:
            f.write("""
/* Dark Theme */
QWidget {
    background-color: #121212;
    color: #ffffff;
    border: none;
}
QMainWindow, QDialog {
    background-color: #1e1e1e;
}
QMenuBar {
    background-color: #2c2c2c;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 8px;
}
QMenuBar::item:selected {
    background-color: #555555;
}
QMenu {
    background-color: #2c2c2c;
    border: 1px solid #555555;
}
QMenu::item:selected {
    background-color: #555555;
}
QPushButton {
    background-color: #333333;
    border: 1px solid #555555;
    padding: 8px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #454545;
}
QPushButton:pressed {
    background-color: #555555;
}
QLineEdit, QListWidget {
    background-color: #2c2c2c;
    border: 1px solid #555555;
    padding: 5px;
    border-radius: 4px;
}
QSlider::groove:horizontal {
    border: 1px solid #555;
    height: 8px;
    background: #333;
    margin: 2px 0;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #777;
    border: 1px solid #555;
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
            """)
    
    light_qss_path = os.path.join(themes_dir, "light.qss")
    if not os.path.exists(light_qss_path):
        with open(light_qss_path, "w", encoding="utf-8") as f:
            f.write("""
/* Light Theme */
QWidget {
    background-color: #f0f0f0;
    color: #000000;
    border: none;
}
QMainWindow, QDialog {
    background-color: #ffffff;
}
QMenuBar {
    background-color: #e8e8e8;
}
QMenuBar::item:selected {
    background-color: #dcdcdc;
}
QMenu {
    background-color: #ffffff;
    border: 1px solid #dcdcdc;
}
QMenu::item:selected {
    background-color: #dcdcdc;
}
QPushButton {
    background-color: #e0e0e0;
    border: 1px solid #cccccc;
    padding: 8px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #dcdcdc;
}
QPushButton:pressed {
    background-color: #cccccc;
}
QLineEdit, QListWidget {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    padding: 5px;
    border-radius: 4px;
}
QSlider::groove:horizontal {
    border: 1px solid #bbb;
    height: 8px;
    background: #ddd;
    margin: 2px 0;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #888;
    border: 1px solid #777;
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
            """)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # 아이콘 설정
    app.setWindowIcon(QIcon("icon.ico")) # icon.ico 파일이 있다고 가정
    
    window = MainWindow()
    
    # 창 위치, 크기 복원
    pos = config.get("window_position")
    if pos:
        window.move(pos['x'], pos['y'])

    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 