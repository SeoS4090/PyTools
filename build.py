#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyTools 애플리케이션 빌드 스크립트
PyInstaller를 사용하여 실행 파일을 생성합니다.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def install_pyinstaller():
    """PyInstaller 설치"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("PyInstaller가 설치되었습니다.")
        return True
    except subprocess.CalledProcessError:
        print("PyInstaller 설치에 실패했습니다.")
        return False

def build_executable():
    """실행 파일 빌드"""
    try:
        # PyInstaller 명령어 구성
        cmd = [
            "pyinstaller",
            "--onefile",  # 단일 실행 파일로 생성
            "--windowed",  # 콘솔 창 숨김
            "--name=PyTools",  # 실행 파일 이름
            "--icon=icon.ico",  # 아이콘 (있는 경우)
            "--add-data=config.json;.",  # 설정 파일 포함
            "main.py"
        ]
        
        # 아이콘이 없으면 아이콘 옵션 제거
        if not os.path.exists("icon.ico"):
            cmd.remove("--icon=icon.ico")
        
        # 설정 파일이 없으면 데이터 옵션 제거
        if not os.path.exists("config.json"):
            cmd.remove("--add-data=config.json;.")
        
        print("빌드를 시작합니다...")
        subprocess.check_call(cmd)
        
        # dist 폴더에서 실행 파일 확인
        dist_path = Path("dist/PyTools.exe")
        if dist_path.exists():
            print(f"빌드가 완료되었습니다: {dist_path}")
            return True
        else:
            print("빌드된 실행 파일을 찾을 수 없습니다.")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"빌드 중 오류가 발생했습니다: {e}")
        return False
    except Exception as e:
        print(f"예상치 못한 오류: {e}")
        return False

def clean_build_files():
    """빌드 임시 파일 정리"""
    try:
        # PyInstaller 생성 파일들 정리
        for folder in ["build", "__pycache__"]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                print(f"{folder} 폴더를 삭제했습니다.")
        
        # .spec 파일 삭제
        spec_file = "PyTools.spec"
        if os.path.exists(spec_file):
            os.remove(spec_file)
            print(f"{spec_file} 파일을 삭제했습니다.")
            
    except Exception as e:
        print(f"정리 중 오류: {e}")

def main():
    print("PyTools 애플리케이션 빌드 도구")
    print("=" * 40)
    
    # PyInstaller 설치 확인
    try:
        import PyInstaller
        print("PyInstaller가 이미 설치되어 있습니다.")
    except ImportError:
        print("PyInstaller를 설치합니다...")
        if not install_pyinstaller():
            sys.exit(1)
    
    # 빌드 실행
    if build_executable():
        print("\n빌드가 성공적으로 완료되었습니다!")
        print("dist 폴더에서 PyTools.exe 파일을 확인하세요.")
        
        # 정리 여부 확인
        response = input("\n빌드 임시 파일들을 정리하시겠습니까? (y/n): ")
        if response.lower() in ['y', 'yes']:
            clean_build_files()
    else:
        print("\n빌드에 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main() 