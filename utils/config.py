"""
配置管理模块
使用本地JSON文件存储用户配置（保存在程序目录中）
"""
import os
import json
import base64
from typing import Any


class Config:
    """应用配置管理器 - 使用本地JSON文件"""
    
    def __init__(self, config_dir: str = None):
        # 配置文件保存在程序目录下
        if config_dir is None:
            config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.config_file = os.path.join(config_dir, 'config.json')
        self._config = self._load()
    
    def _load(self) -> dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"保存配置失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置配置值并保存"""
        self._config[key] = value
        self._save()
    
    def get_api_key(self) -> str:
        """获取加密存储的API Key"""
        encoded = self.get('openai_api_key', '')
        if encoded:
            try:
                return base64.b64decode(encoded.encode()).decode()
            except Exception:
                return ''
        return ''
    
    def set_api_key(self, key: str):
        """加密存储API Key"""
        if key:
            encoded = base64.b64encode(key.encode()).decode()
            self.set('openai_api_key', encoded)
        else:
            if 'openai_api_key' in self._config:
                del self._config['openai_api_key']
                self._save()
    
    def get_whisper_model(self) -> str:
        """获取Whisper模型设置"""
        return self.get('whisper_model', 'base')
    
    def set_whisper_model(self, model: str):
        """保存Whisper模型设置"""
        self.set('whisper_model', model)
    
    def get_custom_model_path(self) -> str:
        """获取自定义模型路径"""
        return self.get('custom_model_path', '')
    
    def set_custom_model_path(self, path: str):
        """保存自定义模型路径"""
        self.set('custom_model_path', path)
    
    def get_output_dir(self) -> str:
        """获取输出目录"""
        default = os.path.join(os.path.expanduser('~'), 'Downloads')
        return self.get('output_dir', default)
    
    def set_output_dir(self, path: str):
        """保存输出目录"""
        self.set('output_dir', path)
    
    def get_history(self) -> list:
        """获取历史记录"""
        return self.get('history', [])
    
    def add_to_history(self, item: dict):
        """添加到历史记录"""
        history = self.get_history()
        history.insert(0, item)
        # 只保留最近50条
        history = history[:50]
        self.set('history', history)
    
    def get_gpt_model(self) -> str:
        """获取GPT模型设置"""
        return self.get('gpt_model', 'gpt-4o-mini')
    
    def set_gpt_model(self, model: str):
        """保存GPT模型设置"""
        self.set('gpt_model', model)
    
    def clear_history(self):
        """清空历史记录"""
        self.set('history', [])

