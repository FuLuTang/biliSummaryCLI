"""
视频下载模块
使用yt-dlp下载Bilibili视频音频
"""
import os
import tempfile
from typing import Callable, Optional

import yt_dlp

from utils.helpers import ensure_dir, safe_filename


class VideoDownloader:
    """Bilibili视频下载器"""
    
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or tempfile.gettempdir()
        ensure_dir(self.output_dir)
    
    def download_video(
        self,
        url: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> dict:
        """
        下载视频 (包含音频)
        
        Args:
            url: Bilibili视频链接或BV/AV号
            progress_callback: 进度回调函数 (进度百分比, 状态文本)
        
        Returns:
            dict: {
                'video_path': 视频文件路径,
                'title': 视频标题,
                'duration': 时长(秒),
                'thumbnail': 封面URL
            }
        """
        # 构建完整URL
        if not url.startswith('http'):
            if url.upper().startswith('BV'):
                base_url = f"https://www.bilibili.com/video/{url}"
            elif url.lower().startswith('av'):
                base_url = f"https://www.bilibili.com/video/{url}"
            else:
                base_url = url
        else:
            base_url = url
            
        # 使用用户提供的 91vrchat 前缀直接获取视频文件
        url = f"https://biliplayer.91vrchat.com/player/?url={base_url}"
        
        result = {
            'video_path': None,
            'title': '',
            'duration': 0,
            'thumbnail': ''
        }
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d and d['total_bytes'] > 0:
                    percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                elif 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
                    percent = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
                else:
                    percent = 0
                
                if progress_callback:
                    progress_callback(percent * 0.5, f"下载中: {percent:.1f}%")
            
            elif d['status'] == 'finished':
                if progress_callback:
                    progress_callback(50, "下载完成，处理中...")
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(self.output_dir, '%(title).50s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if progress_callback:
                    progress_callback(0, "获取视频信息...")
                
                print(f"  - 解析链接: {url}")
                
                # 获取视频信息
                info = ydl.extract_info(url, download=True)
                
                if info:
                    print(f"  - 视频标题: {info.get('title', 'Unknown')}")
                    print(f"  - 下载中...")
                
                if info:
                    result['title'] = info.get('title', 'Unknown')
                    result['duration'] = info.get('duration', 0)
                    result['thumbnail'] = info.get('thumbnail', '')
                    
                    # 查找下载的视频文件
                    safe_title = safe_filename(result['title'], 50)
                    # 可能的扩展名
                    exts = ['mp4', 'mkv', 'webm', 'flv']
                    
                    # 1. 尝试直接构造路径
                    for ext in exts:
                        p = os.path.join(self.output_dir, f"{safe_title}.{ext}")
                        if os.path.exists(p):
                            result['video_path'] = p
                            break
                    
                    # 2. 如果没找到，尝试通过文件名查找 (有时候 yt-dlp 会处理文件名)
                    if not result['video_path']:
                        # 简单的模糊匹配
                        prefix = safe_title[:20] 
                        for f in os.listdir(self.output_dir):
                            if f.startswith(prefix) and any(f.endswith(e) for e in exts):
                                full_path = os.path.join(self.output_dir, f)
                                if os.path.getctime(full_path) > os.path.getctime(__file__):
                                     result['video_path'] = full_path
                                     break

                if progress_callback:
                    progress_callback(55, "视频下载完成")
                    
        except yt_dlp.utils.DownloadError as e:
            raise Exception(f"下载失败: {str(e)}")
        except Exception as e:
            raise Exception(f"下载过程出错: {str(e)}")
        
        if not result['video_path'] or not os.path.exists(result['video_path']):
            raise Exception("视频文件未找到，下载可能失败")
        
        return result
