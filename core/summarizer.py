"""
GPT总结模块
调用OpenAI API生成三段式总结
"""
from typing import Callable, Optional

from openai import OpenAI


class Summarizer:
    """GPT总结生成器"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """
        初始化总结器
        
        Args:
            api_key: OpenAI API Key
            base_url: API基础URL（可选，用于第三方服务）
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None
        )
    
    def generate_summary(
        self,
        transcript: str,
        video_title: str = "",
        model: str = "gpt-4o-mini",
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> dict:
        """
        生成三段式总结 (不包含原文，原文由 Python 直接拼接)
        
        Args:
            transcript: 转写文本
            video_title: 视频标题
            model: GPT模型名称
            progress_callback: 进度回调
        
        Returns:
            dict: {
                'summary': 主要内容与评价,
                'outline': 内容概述,
                'value_content': 价值内容
            }
        """
        if progress_callback:
            progress_callback(92, "正在生成总结...")
        
        # 限制转写文本长度（避免超出token限制）
        max_chars = 15000
        truncated_transcript = transcript[:max_chars]
        if len(transcript) > max_chars:
            truncated_transcript += "\n...[内容已截断]..."
        
        prompt = f"""请根据以下视频转写内容，生成极简、深刻的结构化总结。
        
        视频标题：{video_title}
        
        转写内容（仅供理解，严禁在回复中重复原文）：
        {truncated_transcript}
        
        请严格按照以下 3 个部分输出，严禁输出第四部分，严禁重复原文内容：
        
        ## 一、主要内容与主观评价
        简要概述（2-3句话）。然后主观评价这视频有用吗还是只是消遣还是很有价值还是将信将疑还是什么...
        
        ## 二、内容概述
        按视频逻辑主线，重新理一遍视频大概说了什么内容。每部分一句话。
        
        ## 三、价值内容
        总结该视频带来的道理、方法论或启示。
        
        ---
        注意：请直接开始输出 MARKDOWN 内容。严禁重复转写文稿中的原话！"""

        try:
            # 构造请求参数
            params = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的内容分析助手，擅长总结和评价视频内容。请用中文回复。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 1.0,
                "max_completion_tokens": 2000  # 使用新版参数名以兼容 o1 等模型
            }
            
            # OpenAI o1 系列模型不支持 temperature 参数，如果用户输入的是 o1 开头的模型则移除
            if model.startswith("o1"):
                params.pop("temperature", None)

            response = self.client.chat.completions.create(**params)
            
            summary_text = response.choices[0].message.content.strip()
            
            if progress_callback:
                progress_callback(98, "总结生成完成")
            
            # 解析生成的内容
            result = self._parse_summary(summary_text)
            result['transcript'] = transcript
            
            # 添加 token 使用统计
            if response.usage:
                u = response.usage
                result['usage'] = {
                    'prompt_tokens': getattr(u, 'prompt_tokens', 0) or getattr(u, 'input_tokens', 0),
                    'completion_tokens': getattr(u, 'completion_tokens', 0) or getattr(u, 'output_tokens', 0),
                    'total_tokens': getattr(u, 'total_tokens', 0)
                }
            
            return result
            
        except Exception as e:
            raise Exception(f"GPT API调用失败: {str(e)}")
    
    def _parse_summary(self, text: str) -> dict:
        """解析GPT生成的总结"""
        result = {
            'summary': '',
            'outline': '',
            'value_content': '',
            'transcript': ''
        }
        
        # 尝试按章节分割
        sections = text.split('## ')
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            if '主要内容' in section or '一、' in section:
                # 移除标题行
                lines = section.split('\n', 1)
                if len(lines) > 1:
                    result['summary'] = lines[1].strip()
                else:
                    result['summary'] = section
            
            elif '内容概述' in section or '二、' in section:
                lines = section.split('\n', 1)
                if len(lines) > 1:
                    result['outline'] = lines[1].strip()
                else:
                    result['outline'] = section

            elif '价值内容' in section or '三、' in section:
                lines = section.split('\n', 1)
                if len(lines) > 1:
                    result['value_content'] = lines[1].strip()
                else:
                    result['value_content'] = section
        
        # 如果解析失败，使用完整文本
        if not result['summary'] and not result['outline']:
            result['summary'] = text
        
        return result
    
    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
