import requests
import json
from typing import Dict, Optional
from utils.helpers import validate_bilibili_url

class VideoInfoFetcher:
    """
    Bilibili 视频信息获取器
    使用公开 API 获取视频标题、封面、UP主等数据
    """
    
    API_URL = "https://api.bilibili.com/x/web-interface/view"
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

    @classmethod
    def get_info(cls, url_or_id: str) -> Optional[Dict]:
        """
        通过 URL 或 ID 获取视频信息
        """
        valid, video_id = validate_bilibili_url(url_or_id)
        if not valid:
            return None
            
        params = {}
        if video_id.lower().startswith('bv'):
            params['bvid'] = video_id
        else:
            params['aid'] = video_id.replace('av', '')
            
        headers = {
            "User-Agent": cls.USER_AGENT,
            "Referer": "https://www.bilibili.com"
        }
        
        try:
            response = requests.get(cls.API_URL, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if data.get('code') == 0:
                vdata = data.get('data', {})
                return {
                    'title': vdata.get('title'),
                    'bvid': vdata.get('bvid'),
                    'aid': vdata.get('aid'),
                    'pic': vdata.get('pic'),
                    'desc': vdata.get('desc'),
                    'owner': vdata.get('owner', {}).get('name'),
                    'pubdate': vdata.get('pubdate'),
                    'duration': vdata.get('duration'),
                    'view': vdata.get('stat', {}).get('view')
                }
            else:
                print(f"B站 API 返回错误: {data.get('message')}")
                return None
                
        except Exception as e:
            print(f"获取视频信息失败: {str(e)}")
            return None
