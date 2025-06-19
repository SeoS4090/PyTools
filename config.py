import json
import os
from pathlib import Path

class Config:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        # config.json이 있으면 그 값을 default_config로 사용
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.default_config = json.load(f)
        else:
            # config.json이 없을 때만 내부 기본값 사용
            self.default_config = {
                "version": "1.0.2",
                "github_repo": "SeoS4090/PyTools",
                "auto_start": True,
                "check_updates": True,
                "update_interval": 3600,  # 1시간
                "minimize_to_tray": True,
                "window_position": {"x": 100, "y": 100},
                "window_size": {"width": 600, "height": 400}
            }
        self.config = self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 기본값과 병합
                    merged_config = self.default_config.copy()
                    merged_config.update(config)
                    return merged_config
            else:
                # 기본 설정으로 파일 생성
                self.save_config(self.default_config)
                return self.default_config
        except Exception as e:
            print(f"설정 로드 실패: {e}")
            return self.default_config
    
    def save_config(self, config=None):
        """설정 파일 저장"""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"설정 저장 실패: {e}")
            return False
    
    def get(self, key, default=None):
        """설정값 가져오기"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """설정값 설정"""
        self.config[key] = value
        return self.save_config()
    
    def update(self, updates):
        """여러 설정값 한번에 업데이트"""
        self.config.update(updates)
        return self.save_config()
    
    def reset_to_default(self):
        """기본 설정으로 초기화"""
        self.config = self.default_config.copy()
        return self.save_config()

# 전역 설정 인스턴스
config = Config() 