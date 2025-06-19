#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyTools 애플리케이션 실행 스크립트
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import main
    main()
except ImportError as e:
    print(f"필요한 모듈을 가져올 수 없습니다: {e}")
    print("requirements.txt의 패키지들을 설치해주세요:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"애플리케이션 실행 중 오류가 발생했습니다: {e}")
    sys.exit(1) 