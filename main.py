import sys
import os
import json
import requests
import webbrowser
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu, QAction, QMessageBox, QStyle, QDialog, QVBoxLayout, QCheckBox, QPushButton, QLabel, QHBoxLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
import psutil
import winreg
import subprocess

from config import config
from updater import UpdateManager

# --- Google OAuth2 관련 상수 ---
GOOGLE_CLIENT_ID = "44798885024-pf7otl5hsn6a0am4cagg1dlcssr5b6ng.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_REDIRECT_URI = "http://localhost"
GOOGLE_SCOPE = "openid email profile"

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.version = config.get("version", "1.0.2") or "1.0.2"
        self.tray_icon = None
        self.updater = None
        self.update_manager = UpdateManager(
            self.version,
            config.get("github_repo", "SeoS4090/PyTools") or "SeoS4090/PyTools"
        )
        # 구글 연동 상태 변수
        self.google_connected = False
        self.google_userinfo = None
        self.google_tokens = None
        self.init_ui()
        self.setup_tray()
        if bool(config.get("auto_start", True)):
            self.setup_autostart()
        if config.get("check_updates", True):
            self.start_auto_updater()
        
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(f"PyTools 애플리케이션 v{self.version}")
        
        # 메뉴바 생성
        menubar = self.menuBar()
        
        # File 메뉴
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open", self)
        save_action = QAction("Save", self)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_application)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # Setting 메뉴
        setting_menu = menubar.addMenu("Setting")
        self.google_action = QAction("구글 연동", self)
        self.google_action.triggered.connect(self.google_auth)
        setting_menu.addAction(self.google_action)
        self.google_disconnect_action = QAction("구글 연동 해제", self)
        self.google_disconnect_action.triggered.connect(self.google_disconnect)
        setting_menu.addAction(self.google_disconnect_action)
        env_action = QAction("환경 설정", self)
        env_action.triggered.connect(self.show_env_settings)
        setting_menu.addAction(env_action)
        
        # About 메뉴
        about_menu = menubar.addMenu("About")
        help_action = QAction("Help", self)
        help_action.triggered.connect(self.show_about)
        about_menu.addAction(help_action)
        
        # 중앙 위젯 및 기타 UI 요소 제거 (메뉴만 남김)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # 오른쪽 상단 사용자 정보 표시용 레이아웃
        self.user_info_layout = QHBoxLayout()
        self.user_info_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.user_icon_label = QLabel()
        self.user_name_label = QLabel()
        self.user_info_layout.addWidget(self.user_icon_label)
        self.user_info_layout.addWidget(self.user_name_label)
        # 메인 레이아웃에 사용자 정보 레이아웃만 추가 (상단 우측 정렬)
        main_layout = QVBoxLayout(central_widget)
        main_layout.addLayout(self.user_info_layout)
        main_layout.addStretch(1)
        self.update_google_userinfo_ui()
        self.update_google_menu_state()
        
    def setup_tray(self):
        """시스템 트레이 설정"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # 아이콘 설정 (기본 아이콘 사용)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        
        # 트레이 메뉴 생성
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
        
    def show_about(self):
        """정보 보기 및 Help 다이얼로그"""
        about_text = f"""
PyTools 애플리케이션\n\n버전: {self.version}\n기능:\n- 시스템 트레이 지원\n- 자동 시작\n- 자동 업데이트\n- 설정 관리\n\n개발자: Your Name\nGitHub: {config.get("github_repo", "your-username/your-repo")}\n문의: your.email@example.com\n        """
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

        # 윈도우 시작시 자동 실행 토글
        auto_start_chk = QCheckBox("윈도우 시작시 자동 실행")
        auto_start_chk.setChecked(bool(config.get("auto_start", True)))
        layout.addWidget(auto_start_chk)

        # 닫기 버튼을 누르면 트레이로 이동 토글
        tray_chk = QCheckBox("닫기 버튼을 누르면 트레이로 이동")
        tray_chk.setChecked(bool(config.get("minimize_to_tray", True)))
        layout.addWidget(tray_chk)

        # Save 버튼
        save_btn = QPushButton("Save")
        layout.addWidget(save_btn)

        def save_settings():
            config.set("auto_start", auto_start_chk.isChecked())
            config.set("minimize_to_tray", tray_chk.isChecked())
            # 즉시 적용
            if auto_start_chk.isChecked():
                self.setup_autostart()
            else:
                # 레지스트리에서 자동 시작 제거
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Run",
                        0,
                        winreg.KEY_SET_VALUE
                    )
                    winreg.DeleteValue(key, "PyTools")
                    winreg.CloseKey(key)
                except Exception:
                    pass
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
        QApplication.quit()
        
    def setup_autostart(self):
        """자동 시작 설정"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            
            app_path = sys.argv[0]
            if app_path.endswith('.py'):
                # 개발 모드에서는 Python 스크립트로 실행
                app_path = f'pythonw "{app_path}"'
            else:
                # 배포 모드에서는 실행 파일로 실행
                app_path = f'"{app_path}"'
                
            winreg.SetValueEx(key, "PyTools", 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
            self.log_message("자동 시작이 설정되었습니다.")
        except Exception as e:
            self.log_message(f"자동 시작 설정 실패: {str(e)}")
            
    def start_auto_updater(self):
        """자동 업데이트 시작"""
        self.updater = AutoUpdater(self.version)
        self.updater.update_available.connect(self.on_update_available)
        self.updater.update_error.connect(self.on_update_error)
        self.updater.start()
        
    def on_update_available(self, new_version):
        """업데이트 가능 시 처리"""
        reply = QMessageBox.question(
            self,
            "업데이트 알림",
            f"새로운 버전 {new_version}이 사용 가능합니다.\n지금 업데이트하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.perform_update(new_version)
            
    def perform_update(self, new_version):
        """업데이트 수행"""
        try:
            self.log_message(f"업데이트를 시작합니다: {new_version}")
            
            # 업데이트 다운로드 및 설치
            download_url = f"https://github.com/{config.get('github_repo')}/releases/latest/download/PyTools-{new_version}.zip"
            update_file = f"update-{new_version}.zip"
            
            if self.update_manager.download_update(download_url, update_file):
                if self.update_manager.install_update(update_file):
                    # 재시작 스크립트 생성 및 실행
                    restart_script = self.update_manager.create_restart_script()
                    subprocess.Popen([sys.executable, restart_script])
                    self.quit_application()
                else:
                    QMessageBox.critical(self, "업데이트 실패", "업데이트 설치에 실패했습니다.")
            else:
                QMessageBox.critical(self, "업데이트 실패", "업데이트 파일 다운로드에 실패했습니다.")
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "업데이트 실패",
                f"업데이트 중 오류가 발생했습니다:\n{str(e)}"
            )
            
    def on_update_error(self, error_message):
        """업데이트 오류 처리"""
        self.log_message(f"업데이트 오류: {error_message}")
        
    def log_message(self, message):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(self, "log_text") and self.log_text is not None:
            self.log_text.append(f"[{timestamp}] {message}")
        # 로그 창이 없으면 아무것도 하지 않음
        
    def closeEvent(self, event):
        """창 닫기 이벤트 처리"""
        if bool(config.get("minimize_to_tray", True)):
            event.ignore()
            self.minimize_to_tray()
        else:
            # 창 위치와 크기 저장
            config.update({
                "window_position": {"x": self.x(), "y": self.y()},
                "window_size": {"width": self.width(), "height": self.height()}
            })
            event.accept()
            self.quit_application()

    # --- 구글 OAuth2 연동 ---
    def update_google_menu_state(self):
        """구글 연동 상태에 따라 메뉴 활성화/비활성화 및 사용자 정보 UI 갱신"""
        if self.google_connected:
            self.google_action.setEnabled(False)
            self.google_disconnect_action.setEnabled(True)
        else:
            self.google_action.setEnabled(True)
            self.google_disconnect_action.setEnabled(False)
        self.update_google_userinfo_ui()

    def update_google_userinfo_ui(self):
        """오른쪽 상단에 구글 사용자 정보(아이콘, 이름) 표시"""
        if self.google_connected and self.google_userinfo:
            name = self.google_userinfo.get("name", "")
            self.user_name_label.setText(name)
            # 프로필 이미지 표시
            picture_url = self.google_userinfo.get("picture")
            if picture_url:
                try:
                    import urllib.request
                    data = urllib.request.urlopen(picture_url).read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(data)
                    self.user_icon_label.setPixmap(
                        pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    )
                except Exception:
                    self.user_icon_label.clear()
            else:
                self.user_icon_label.clear()
        else:
            self.user_name_label.clear()
            self.user_icon_label.clear()

    def google_auth(self):
        try:
            code = self._google_get_auth_code()
            if not code:
                QMessageBox.warning(self, "구글 연동", "인증 코득에 실패했습니다.")
                return
            tokens = self._google_get_tokens(code)
            if "access_token" not in tokens:
                QMessageBox.warning(self, "구글 연동", f"토큰 획득 실패: {tokens}")
                return
            userinfo = self._google_get_userinfo(tokens["access_token"])
            if "email" in userinfo:
                msg = f"구글 인증 성공!\n\n이메일: {userinfo['email']}\n이름: {userinfo.get('name', '')}"
                self.google_connected = True
                self.google_userinfo = userinfo
                self.google_tokens = tokens
                self.update_google_menu_state()
            else:
                msg = f"사용자 정보 획득 실패: {userinfo}"
            QMessageBox.information(self, "구글 연동 결과", msg)
        except Exception as e:
            QMessageBox.critical(self, "구글 연동 오류", f"구글 인증 중 오류 발생:\n{str(e)}")

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
        def start_server():
            httpd = HTTPServer(("localhost", 80), OAuthHandler)
            httpd.handle_request()
        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope={GOOGLE_SCOPE}&"
            "access_type=offline"
        )
        Thread(target=start_server, daemon=True).start()
        webbrowser.open(auth_url)
        while OAuthHandler.code is None:
            QApplication.processEvents()
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
        self.google_connected = False
        self.google_userinfo = None
        self.google_tokens = None
        self.update_google_menu_state()
        QMessageBox.information(self, "구글 연동 해제", "구글 연동이 해제되었습니다.")

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 마지막 창이 닫혀도 앱이 종료되지 않도록
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 