#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyTools 실행 스크립트
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# src 폴더를 Python 경로에 추가
src_path = os.path.join(project_root, "src")
sys.path.insert(0, src_path)

if __name__ == "__main__":
    from src.main import main
    main() 