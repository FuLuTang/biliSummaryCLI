"""
语音转写模块
使用OpenAI Whisper进行本地语音转文字
"""
import os
import torch
import whisper
from typing import Callable, Optional
import concurrent.futures

class Transcriber:
    """语音转写器"""
    
    # 可用的模型列表
    AVAILABLE_MODELS = [
        'tiny', 'base', 'small', 'medium', 'large', 'turbo',
        'gpt-4o-transcribe', 'gpt-4o-mini-transcribe', 'whisper-1'
    ]
    
    def __init__(self, model_name_or_path: str = 'base', api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化转写器
        
        Args:
            model_name_or_path: 模型名称或路径
            api_key: OpenAI API Key (如果使用API转写则必须)
            base_url: OpenAI Base URL
        """
        self.model = None
        self.model_name = model_name_or_path
        self.api_key = api_key
        self.base_url = base_url
        self.client = None
        
        # 兼容 turbo 名称
        if self.model_name == 'turbo':
            self.model_name = 'large-v3-turbo'

    def _is_api_model(self):
        """检查是否是API模型"""
        return self.model_name in ['gpt-4o-transcribe', 'gpt-4o-mini-transcribe', 'whisper-1']

    def load_model(
        self,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        """加载Whisper模型"""
        if self._is_api_model():
            if not self.api_key:
                raise ValueError("使用在线转写模型需要提供 API Key")
            if self.client is None:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            return

        if self.model is not None:
            return
        
        if progress_callback:
            progress_callback(75, f"加载模型: {self.model_name}...")
        
        try:
            # 确定设备
            # 允许通过环境变量强制使用 CPU
            if os.environ.get('FORCE_CPU', '0') == '1':
                device = "cpu"
                print("⚠️ 已强制使用 CPU 模式")
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cuda" if torch.cuda.is_available() else "cpu"
            
            print(f"✓ Whisper 运行设备: {device.upper()}")
            
            # 加载模型
            # in_memory=True 可以稍微加速加载，但费内存
            self.model = whisper.load_model(self.model_name, device=device)
            
            if progress_callback:
                progress_callback(80, "模型加载完成")
                
        except Exception as e:
            raise Exception(f"模型加载失败: {str(e)}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> dict:
        """
        转写音频文件
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 确保模型已加载 (或客户端已初始化)
        self.load_model(progress_callback)
        
        if progress_callback:
            progress_callback(82, "开始语音转写...")
        
        # --- API 转写路径 ---
        # --- API 转写路径 ---
        if self._is_api_model():
            # [Fix] 检查音频时长，如果超过 5 分钟强制使用切片模式
            # 防止 gpt-4o-mini 等模型在长音频下静默截断 (silent truncation)
            try:
                from core.audio_processor import AudioProcessor
                processor = AudioProcessor()
                duration = processor.get_audio_duration(audio_path)
                
                # [调整] 阈值设为 4分58秒 (298秒)
                # 用户要求每 4分58秒 切片，所以只要超过这个长度就进入切片模式
                should_chunk = False
                if duration > 298: 
                    print(f"📊 音频详情: 时长 {duration:.1f}s, 大小 {os.path.getsize(audio_path)/(1024*1024):.2f}MB")
                    print(f"⚠️ 视频较长，切换至【并行分段转写】模式 (每片 4m58s)...")
                    should_chunk = True
                else:
                    print(f"📊 音频详情: 时长 {duration:.1f}s, 满足单次请求条件")
            except Exception as e:
                print(f"⚠️ 时长检测记录: {e}")
                should_chunk = False

            if should_chunk:
                if progress_callback:
                    progress_callback(83, f"正在进行分段转写 (总长 {duration:.1f}s)...")
                return self._transcribe_chunked(audio_path, self.model_name, language, progress_callback)

            try:
                if progress_callback:
                    progress_callback(85, f"正在上传至 OpenAI API 转写 (模型: {self.model_name})...")
                
                print(f"📡 使用 OpenAI API 转写 (模型: {self.model_name})")
                
                # gpt-4o-*-transcribe 模型目前只支持 json/text 格式，不支持 verbose_json
                response_fmt = "json" if self.model_name.startswith("gpt-4o") else "verbose_json"
                
                # 检查文件大小，如果超过 24MB，进行压缩
                # import os  <-- remove this
                file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
                if file_size_mb > 24:
                    if progress_callback:
                        progress_callback(83, f"音频文件过大 ({file_size_mb:.1f}MB)，正在压缩...")
                    
                    from core.audio_processor import AudioProcessor
                    processor = AudioProcessor()
                    # 压缩生成新文件
                    try:
                        audio_path = processor.compress_for_api(audio_path, progress_callback=progress_callback)
                    except Exception as e:
                        print(f"⚠️ 压缩失败: {e}，将尝试直接上传...")

                with open(audio_path, "rb") as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model=self.model_name, 
                        file=audio_file,
                        language=language,
                        response_format=response_fmt
                    )
                
                if progress_callback:
                    progress_callback(99, "API 转写完成")
                
                # 尝试提取信息
                result = {
                    'text': transcript.text,
                    # JSON 模式下没有这些元数据，只能给默认值
                    'language': getattr(transcript, 'language', 'auto'),
                    'duration': getattr(transcript, 'duration', 0.0)
                }
                
                # 检查是否有 usage 信息
                if hasattr(transcript, 'usage') and transcript.usage:
                   result['usage'] = transcript.usage
                   print(f"💰 API 消耗统计: {transcript.usage}")
                
                print(f"✅ 转写成功: 收到文本 {len(transcript.text)} 字符")
                return result
                
            except Exception as e:
                error_str = str(e)
                
                # 策略 1: 如果是 Token 超限或文件过大，触发自动切片
                if "input_too_large" in error_str or "maximum context" in error_str:
                    print(f"⚠️ API 报错: 内容过长 ({error_str})")
                    print("🔄 触发自动切片转写模式 (Smart Chunking)...")
                    return self._transcribe_chunked(audio_path, self.model_name, language, progress_callback)

                # 策略 2: 其他错误，尝试回退到 whisper-1
                if self.model_name != "whisper-1":
                    print(f"⚠️ 模型 {self.model_name} 调用失败: {e}")
                    print("🔄 尝试回退到通用模型 whisper-1 ...")
                    try:
                        with open(audio_path, "rb") as audio_file:
                            transcript = self.client.audio.transcriptions.create(
                                model="whisper-1", 
                                file=audio_file,
                                language=language,
                                response_format="verbose_json"
                            )
                        return {
                            'text': transcript.text,
                            'language': getattr(transcript, 'language', 'auto'),
                            'duration': getattr(transcript, 'duration', 0.0)
                        }
                    except Exception as e2:
                        raise Exception(f"OpenAI API 转写失败 (回退也失败): {str(e2)}")
                
                raise Exception(f"OpenAI API 转写失败: {str(e)}")

        # --- 本地 Whisper 转写路径 ---
        try:
            # 准备参数
            # mps 上 fp16 可能会出现 NaN，如果遇到问题可以自动回退
            # 默认尝试开启 fp16 (包括 MPS)
            fp16 = True
            
            # 转写
            result = self.model.transcribe(
                audio_path,
                language=language,
                verbose=False, # 我们自己打印进度，不用自带的
                fp16=fp16
            )
            
            if progress_callback:
                print(f"  - 检测到的语言: {result.get('language', 'unknown')}")
                print(f"  - 文本长度: {len(result.get('text', ''))} 字符")
                progress_callback(99, "转写完成")
            
            return result
            
        except RuntimeError as e:
            if "NaN" in str(e) and fp16:
                print("⚠️ 检测到 NaN 错误，尝试禁用 fp16 重试...")
                return self.model.transcribe(
                    audio_path,
                    language=language,
                    fp16=False
                )
            raise e
        except Exception as e:
            raise Exception(f"语音转写失败: {str(e)}")
            
    def unload_model(self):
        """手动释放模型内存"""
        if self.model:
            del self.model
            # 强制垃圾回收
            import gc
            gc.collect() 
            import torch
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.model = None

    def format_segments(self, segments: list) -> str:
        """格式化分段信息为带时间戳的文本"""
        lines = []
        for seg in segments:
            start = self._format_time(seg.get('start', 0))
            end = self._format_time(seg.get('end', 0))
            text = seg.get('text', '').strip()
            lines.append(f"[{start} -> {end}] {text}")
        return '\n'.join(lines)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _transcribe_part(self, i: int, total_chunks: int, chunk_path: str, model_name: str, language: str) -> dict:
        """转写单个切片 (用于并发)"""
        print(f"  -> [线程启动] 处理片段 {i+1}/{total_chunks}...")
        try:
            with open(chunk_path, "rb") as audio_file:
                # 并行模式下无法使用上文 context prompt，因为上文还没出来
                response = self.client.audio.transcriptions.create(
                    model=model_name,
                    file=audio_file,
                    language=language,
                    response_format="json"
                )
                print(f"  √ [片段完成] {i+1}/{total_chunks}")
                return {
                    "index": i,
                    "text": response.text,
                    "usage": getattr(response, 'usage', None)
                }
        except Exception as e:
            print(f"⚠️ [片段失败] {i+1}/{total_chunks}: {e}")
            raise e

    def _transcribe_chunked(self, audio_path: str, model_name: str, language: str, progress_callback: Optional[Callable] = None) -> dict:
        """
        分片转写逻辑 (并行加速)
        """
        from core.audio_processor import AudioProcessor
        processor = AudioProcessor()
        
        # 1. 切片 (每4分58秒一段 = 298秒)
        chunk_duration = 298
        if progress_callback:
            progress_callback(84, f"正在进行智能切片 (每段 {chunk_duration}s)...")
        
        chunks = processor.split_audio(audio_path, segment_seconds=chunk_duration)
        total_chunks = len(chunks)
        print(f"🔪 音频已切分为 {total_chunks} 个片段")
        
        results = [None] * total_chunks
        total_usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        
        # 2. 并发请求
        # 限制并发数为 4，避免触发 API 速率限制 (429)
        max_workers = 4
        print(f"🚀 启动并发转写 (并发数: {max_workers})...")
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_index = {
                    executor.submit(
                        self._transcribe_part, i, total_chunks, chunk_path, model_name, language
                    ): i 
                    for i, chunk_path in enumerate(chunks)
                }
                
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        # 获取结果，如果有异常会在这里抛出
                        data = future.result()
                        results[index] = data['text']
                        
                        # 统计 usage
                        if data['usage']:
                            u = data['usage']
                            # 兼容不同字段名 (openai standard vs some compatible apis)
                            p_tokens = getattr(u, 'prompt_tokens', 0) or getattr(u, 'input_tokens', 0)
                            c_tokens = getattr(u, 'completion_tokens', 0) or getattr(u, 'output_tokens', 0)
                            
                            total_usage['prompt_tokens'] += p_tokens
                            total_usage['completion_tokens'] += c_tokens
                            total_usage['total_tokens'] += getattr(u, 'total_tokens', 0)
                            
                        completed_count += 1
                        if progress_callback:
                            progress = 85 + (completed_count / total_chunks) * 14
                            progress_callback(progress, f"并发转写中... ({completed_count}/{total_chunks})")
                            
                    except Exception as e:
                        # 任何一个失败，直接终止整个流程
                        raise Exception(f"片段 {index+1} 转写失败，流程终止。错误: {str(e)}")

        finally:
            # 清理切片文件
            for chunk_path in chunks:
                if os.path.exists(chunk_path):
                    try:
                        os.remove(chunk_path)
                    except:
                        pass
        
        # 3. 拼合结果
        # results 列表已经按照 index 位置填充好了
        # 用户要求段之间多加回车，使用 double newline 分隔
        combined_text = "\n\n".join(results)
        
        if progress_callback:
            progress_callback(99, "所有片段转写成功，已合并")

        return {
            "text": combined_text,
            "language": language,
            "segments": [], 
            "usage": total_usage
        }
