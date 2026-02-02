"""
工具函数模块
"""
import re
import os


def validate_bilibili_url(url: str) -> tuple[bool, str]:
    """
    验证Bilibili链接格式
    
    返回: (是否有效, 错误信息或视频ID)
    """
    if not url:
        return False, "链接不能为空"
    
    url = url.strip()
    
    # 支持的链接格式:
    # https://www.bilibili.com/video/BV1xx411c7XW
    # https://b23.tv/BV1xx411c7XW
    # BV1xx411c7XW
    # av170001
    
    # BV号格式
    bv_pattern = r'(BV[a-zA-Z0-9]{10})'
    # AV号格式
    av_pattern = r'av(\d+)'
    
    bv_match = re.search(bv_pattern, url, re.IGNORECASE)
    if bv_match:
        return True, bv_match.group(1)
    
    av_match = re.search(av_pattern, url, re.IGNORECASE)
    if av_match:
        return True, f"av{av_match.group(1)}"
    
    return False, "无效的Bilibili链接格式，请输入完整链接或BV/AV号"


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    """格式化时长"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def ensure_dir(path: str) -> str:
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def safe_filename(name: str, max_length: int = 50) -> str:
    """生成安全的文件名"""
    # 移除非法字符
    illegal_chars = r'[<>:"/\\|?*]'
    safe_name = re.sub(illegal_chars, '_', name)
    # 限制长度
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]
    return safe_name.strip()
