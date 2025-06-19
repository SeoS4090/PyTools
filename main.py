import sys
import os
import json
import requests
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QTextEdit, 
                             QSystemTrayIcon, QMenu, QAction, QMessageBox, QStyle, QDialog, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont
import psutil
import winreg
import subprocess

from config import config
from updater import UpdateManager

class AutoUpdater(QThread):
    """자동 업데이트를 처리하는 스레드"""
    update_available = pyqtSignal(str)
    update_complete = pyqtSignal()
    update_error = pyqtSignal(str)
    
    def __init__(self, current_version="1.0.0"):
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
        self.version = config.get("version", "1.0.0") or "1.0.0"
        self.tray_icon = None
        self.updater = None
        self.update_manager = UpdateManager(
            self.version,
            config.get("github_repo", "SeoS4090/PyTools") or "SeoS4090/PyTools"
        )
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
        google_action = QAction("구글 연동", self)
        setting_menu.addAction(google_action)
        env_action = QAction("환경 설정", self)
        env_action.triggered.connect(self.show_env_settings)
        setting_menu.addAction(env_action)
        
        # About 메뉴
        about_menu = menubar.addMenu("About")
        help_action = QAction("Help", self)
        help_action.triggered.connect(self.show_about)
        about_menu.addAction(help_action)
        
        # 중앙 위젯 및 기타 UI 요소 제거 (메뉴만 남김)
        self.setCentralWidget(QWidget())
        
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

        # 닫기 버튼 트레이 이동 토글
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

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 마지막 창이 닫혀도 앱이 종료되지 않도록
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 