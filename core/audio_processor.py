"""
音频处理模块
直接使用FFmpeg处理音频（避免pydub的Python版本兼容性问题）
"""
import os
import subprocess
import json
from typing import Callable, Optional


class AudioProcessor:
    """音频处理器 - 使用FFmpeg"""
    
    # Whisper最佳格式: 16kHz, mono, WAV
    TARGET_SAMPLE_RATE = 16000
    TARGET_CHANNELS = 1
    MAX_FILE_SIZE_MB = 25  # Whisper API限制
    
    def __init__(self):
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "FFmpeg未安装或不在PATH中。\n"
                "请安装FFmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Ubuntu: sudo apt install ffmpeg\n"
                "  Windows: choco install ffmpeg"
            )
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长（秒）"""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                audio_path
            ], capture_output=True, text=True, check=True)
            
            info = json.loads(result.stdout)
            return float(info.get('format', {}).get('duration', 0))
        except Exception:
            return 0
    
    def process_audio(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        处理音频文件，转换为Whisper最佳格式
        
        Args:
            input_path: 输入音频路径
            output_path: 输出路径（可选，默认同目录下.wav）
            progress_callback: 进度回调
        
        Returns:
            处理后的音频文件路径
        """
        if progress_callback:
            progress_callback(55, "加载音频文件...")
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"音频文件不存在: {input_path}")
        
        # 生成输出路径
        if not output_path:
            base = os.path.splitext(input_path)[0]
            output_path = f"{base}_processed.wav"
        
        if progress_callback:
            progress_callback(60, "转换音频格式...")
        
        try:
            # 获取原始时长用于计算比特率
            duration = self._get_audio_duration(input_path)
            
            # 计算目标比特率（如果需要压缩）
            # 估算：16kHz mono 16bit = 约 256 kbps 未压缩
            # 对于25MB限制和长音频，可能需要降低
            target_bitrate = None
            if duration > 0:
                # 目标大小 20MB（留些余量），计算需要的比特率
                target_size_bits = 20 * 1024 * 1024 * 8
                needed_bitrate = int(target_size_bits / duration / 1000)  # kbps
                if needed_bitrate < 128:  # 如果需要低于128kbps，说明文件很长
                    target_bitrate = max(needed_bitrate, 32)  # 最低32kbps
            
            if progress_callback:
                progress_callback(65, "优化音频大小...")
            
            # 使用FFmpeg转换
            cmd = [
                'ffmpeg', '-y',  # 覆盖输出文件
                '-i', input_path,
                '-ar', str(self.TARGET_SAMPLE_RATE),  # 采样率
                '-ac', str(self.TARGET_CHANNELS),  # 声道数
                '-acodec', 'pcm_s16le',  # 16bit PCM
            ]
            
            # 如果需要压缩，先转成mp3再转wav
            if target_bitrate and target_bitrate < 128:
                # 两步转换：先压缩成mp3
                temp_mp3 = output_path.replace('.wav', '_temp.mp3')
                compress_cmd = [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-ar', str(self.TARGET_SAMPLE_RATE),
                    '-ac', str(self.TARGET_CHANNELS),
                    '-b:a', f'{target_bitrate}k',
                    temp_mp3
                ]
                
                if progress_callback:
                    progress_callback(68, f"压缩音频 (目标: {target_bitrate}kbps)...")
                
                subprocess.run(
                    compress_cmd,
                    capture_output=True,
                    check=True
                )
                
                # 再转成wav
                cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_mp3,
                    '-ar', str(self.TARGET_SAMPLE_RATE),
                    '-ac', str(self.TARGET_CHANNELS),
                    '-acodec', 'pcm_s16le',
                    output_path
                ]
                
                subprocess.run(cmd, capture_output=True, check=True)
                
                # 清理临时文件
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
            else:
                # 直接转换
                cmd.append(output_path)
                subprocess.run(cmd, capture_output=True, check=True)
            
            if progress_callback:
                progress_callback(75, "音频处理完成")
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            raise Exception(f"音频处理失败: {error_msg}")
        except Exception as e:
            raise Exception(f"音频处理失败: {str(e)}")
    def compress_for_api(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        max_size_mb: int = 24,  # 留1MB缓冲
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        专门为API转写压缩音频（目标MP3格式，严格控制大小）
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"音频文件不存在: {input_path}")
            
        if not output_path:
            base = os.path.splitext(input_path)[0]
            output_path = f"{base}_compressed.mp3"
            
        duration = self._get_audio_duration(input_path)
        if duration <= 0:
            # 此时无法计算，使用非常保守的默认值
            bitrate_kbps = 32
        else:
            # 计算目标比特率
            # size (bits) = duration (s) * bitrate (bps)
            # bitrate = size / duration
            target_size_bits = max_size_mb * 1024 * 1024 * 8
            target_bitrate_kbps = int(target_size_bits / duration / 1000)
            
            # 限制范围：
            # 最低 12kbps (对于纯语音，Opus/MP3 VBR勉强可辨识，Whisper鲁棒性很强)
            # 最高 64kbps (不需要太高)
            bitrate_kbps = min(max(target_bitrate_kbps, 12), 64)
        
        if progress_callback:
            progress_callback(62, f"正在压缩音频以适应 API 限制 (目标码率: {bitrate_kbps}k)...")

        # 使用 ffmpeg 压缩为 MP3
        # -ac 1: 单声道 (节省一半码率)
        # -ar 16000: 16kHz (语音足够)
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-ar', '16000',
            '-ac', '1', 
            '-b:a', f'{bitrate_kbps}k',
            output_path
        ]
        
        try:
             subprocess.run(cmd, capture_output=True, check=True)
             
             # 验证压缩后的大小，如果还是太大，可能ffmpeg没严格遵守（VBR情况）
             # 这里暂不重试，因为如果12kbps都超标，那只能切片了
             return output_path
        except subprocess.CalledProcessError as e:
             # 如果失败，抛出异常
             error_msg = e.stderr.decode() if e.stderr else str(e)
             raise Exception(f"压缩失败: {error_msg}")
    def split_audio(
        self,
        input_path: str,
        segment_seconds: int = 300,
        output_dir: Optional[str] = None
    ) -> list[str]:
        """
        将音频分割成多个片段 (用于 API 切片上传)
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"音频文件不存在: {input_path}")
            
        if not output_dir:
            output_dir = os.path.dirname(input_path)
            
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        # 输出模板: filename_part000.mp3
        output_pattern = os.path.join(output_dir, f"{base_name}_part%03d.mp3")
        
        # 使用 ffmpeg segment 分割
        # 强制转为 mp3 16k mono，适合 API
        # 针对 2013 年老版本 FFmpeg 的极限兼容性命令
        # 注意：老版本 FFmpeg 对参数顺序极其敏感
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-map', '0:a',        # [关键修复] 显式映射流，2013版FFmpeg必须项！
            '-ar', '16000',
            '-ac', '1',
            '-acodec', 'libmp3lame', 
            '-f', 'segment',
            '-segment_time', str(segment_seconds),
            output_pattern
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"音频切片失败: {e.stderr.decode() if e.stderr else str(e)}")
        
        # 收集生成的文件
        import glob
        search_pattern = os.path.join(output_dir, f"{base_name}_part???.mp3")
        chunks = sorted(glob.glob(search_pattern))
        return chunks

    def get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长（秒）- 公共方法"""
        return self._get_audio_duration(audio_path)
