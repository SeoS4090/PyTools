import os
import sys
import requests
import zipfile
import shutil
import subprocess
from pathlib import Path

class UpdateManager:
    def __init__(self, current_version="1.0.2", github_repo="your-username/your-repo"):
        self.current_version = current_version
        self.github_repo = github_repo
        self.update_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
        
    def check_for_updates(self):
        """GitHub에서 최신 버전 확인"""
        try:
            response = requests.get(self.update_url, timeout=10)
            if response.status_code == 200:
                release_data = response.json()
                latest_version = release_data['tag_name'].lstrip('v')
                
                if self.compare_versions(latest_version, self.current_version) > 0:
                    return {
                        'available': True,
                        'version': latest_version,
                        'download_url': release_data['html_url'],
                        'release_notes': release_data.get('body', '')
                    }
            return {'available': False}
        except Exception as e:
            print(f"업데이트 확인 실패: {e}")
            return {'available': False, 'error': str(e)}
    
    def compare_versions(self, version1, version2):
        """버전 비교"""
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0
    
    def download_update(self, download_url, target_path):
        """업데이트 파일 다운로드"""
        try:
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"다운로드 실패: {e}")
            return False
    
    def install_update(self, update_file_path):
        """업데이트 설치 (실제 덮어쓰기는 재시작 스크립트에서 진행)"""
        try:
            # 백업 생성
            backup_dir = Path("backup")
            backup_dir.mkdir(exist_ok=True)
            current_files = [f for f in Path(".").iterdir() if f.is_file() and f.suffix in ['.py', '.exe']]
            for file in current_files:
                shutil.copy2(file, backup_dir / file.name)
            # 업데이트 파일 압축 해제 (temp_update 폴더에만)
            with zipfile.ZipFile(update_file_path, 'r') as zip_ref:
                zip_ref.extractall("temp_update")
            # 임시 파일 및 zip 삭제는 재시작 스크립트에서 처리
            return True
        except Exception as e:
            print(f"설치 실패: {e}")
            return False
    
    def create_restart_script(self):
        """재시작 스크립트(.bat) 생성: 실행 중인 exe 종료 후 덮어쓰기 및 재실행"""
        script = r'''
@echo off
REM 2초 대기
ping 127.0.0.1 -n 3 > nul
REM 기존 exe가 완전히 종료될 때까지 대기
:loop
TASKLIST | find /I "PyTools.exe" >nul 2>&1
if not errorlevel 1 (
    ping 127.0.0.1 -n 2 > nul
    goto loop
)
REM 새 파일로 덮어쓰기
copy /Y temp_update\PyTools.exe PyTools.exe
REM 임시 폴더 및 zip 삭제
rmdir /S /Q temp_update
if exist update-*.zip del update-*.zip
REM 프로그램 재실행
start "" PyTools.exe
exit
'''
        script_path = "restart_update.bat"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)
        return script_path 