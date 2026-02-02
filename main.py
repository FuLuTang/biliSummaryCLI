"""
Bilibili 视频总结工具
自动下载B站视频音频，使用Whisper转写，GPT生成结构化总结
"""

# ============================================================
# SSL 证书验证修复 (解决 macOS/Proxy 下模型下载失败问题)
# ============================================================
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# ============================================================
# PyTorch 2.6+ 兼容性补丁 (必须在所有其他导入之前!)
# 解决 Whisper 模型加载时 weights_only=True 导致的错误
# ============================================================
def _apply_pytorch_patch():
    try:
        import torch
        import torch.serialization
        
        # 保存原始函数
        _original_torch_load = torch.load
        
        # 创建兼容版本
        def _patched_load(*args, **kwargs):
            # 强制设置 weights_only=False
            kwargs['weights_only'] = False
            return _original_torch_load(*args, **kwargs)
        
        # 替换 torch.load
        torch.load = _patched_load
        
        # 同时替换 torch.serialization.load (某些库直接使用这个)
        if hasattr(torch.serialization, 'load'):
            torch.serialization.load = _patched_load
            
    except ImportError:
        pass  # torch 还没安装，稍后会自动安装

_apply_pytorch_patch()
# ============================================================

import sys
import os
import shutil
import subprocess

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_and_install_dependencies():
    """检查并自动安装缺失的依赖"""
    required_packages = {
        'PyQt6': 'PyQt6>=6.4.0',
        'yt_dlp': 'yt-dlp>=2024.1.0',
        'openai': 'openai>=1.0.0',
        'whisper': 'openai-whisper>=20231117',
        'requests': 'requests>=2.31.0',
    }
    
    missing_packages = []
    
    for import_name, install_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(install_name)
    
    if missing_packages:
        print("=" * 50)
        print("检测到缺失的依赖包，正在自动安装...")
        print("=" * 50)
        
        for package in missing_packages:
            print(f"\n正在安装: {package}")
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', 
                    package, '--quiet'
                ])
                print(f"  ✓ {package} 安装成功")
            except subprocess.CalledProcessError as e:
                print(f"  ✗ {package} 安装失败: {e}")
                print(f"\n请手动运行: pip install {package}")
                sys.exit(1)
        
        print("\n" + "=" * 50)
        print("所有依赖安装完成！正在启动程序...")
        print("=" * 50 + "\n")


def check_ffmpeg():
    """检查FFmpeg是否已安装"""
    try:
        subprocess.run(
            ['ffmpeg', '-version'], 
            capture_output=True, 
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main(args, parser=None):
    # 首先检查并安装依赖
    check_and_install_dependencies()
    
    # 检查FFmpeg
    if not check_ffmpeg():
        print("=" * 50)
        print("⚠️  警告: 未检测到 FFmpeg")
        print("=" * 50)
        print("\n音频处理需要 FFmpeg，请先安装:")
        print("\n  macOS:   brew install ffmpeg")
        print("  Ubuntu:  sudo apt install ffmpeg")
        print("  Windows: choco install ffmpeg")
        print("\n程序将继续运行，但音频处理可能失败。")
        print("=" * 50 + "\n")
    else:
        print("✓ FFmpeg 已就绪\n")
    
    # 显示系统信息
    print("=" * 60)
    print("📋 系统信息")
    print("=" * 60)
    print(f"Python 版本: {sys.version.split()[0]}")
    
    try:
        import torch
        print(f"PyTorch 版本: {torch.__version__}")
        
        if torch.backends.mps.is_available():
            print("✓ Apple Silicon GPU (MPS) 可用")
        elif torch.cuda.is_available():
            print(f"✓ CUDA GPU 可用: {torch.cuda.get_device_name(0)}")
        else:
            print("⚠️  仅 CPU 模式")
    except:
        pass
    
    print("=" * 60 + "\n")
    
    # CLI 模式 (只有提供了URL且未指定--ui时才运行)
    if args.url and not args.ui:
        run_cli(args.url, args)
        return
    
    # GUI 模式 (指定了 --ui)
    if args.ui:
        # 导入PyQt（此时已确保安装）
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        
        # 启用高DPI缩放
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        # 加载样式表
        style_path = os.path.join(os.path.dirname(__file__), 'ui', 'styles.qss')
        if os.path.exists(style_path):
            with open(style_path, 'r', encoding='utf-8') as f:
                app.setStyleSheet(f.read())
        
        print("🖥️  图形界面已启动，请在窗口中操作\n")
        
        window = MainWindow()
        
        # 如果命令行指定了URL，自动填入
        if args.url:
            window.url_input.setText(args.url)
            # 触发一下预览
            window.on_url_changed(args.url)
            
        window.show()
        
        sys.exit(app.exec())
        
    # 如果既没有 URL 也没有 --ui，打印帮助
    if parser:
        parser.print_help()
    else:
        print("用法错误: 请提供视频 URL 或使用 --ui 启动图形界面")
    
    print("\n提示:")
    print("  - 命令行运行: python main.py <URL>")
    print("  - 启动界面:   python main.py --ui")
    sys.exit(0)


def run_cli(url: str, args):
    """命令行运行模式"""
    import tempfile
    from utils.config import Config
    from core.video_info import VideoInfoFetcher
    from core.downloader import VideoDownloader
    from core.audio_processor import AudioProcessor
    from core.transcriber import Transcriber
    from core.summarizer import Summarizer
    from utils.helpers import safe_filename, ensure_dir

    print("📺 命令行模式启动...")
    print(f"🎯 目标视频: {url}")
    
    # 1. 加载与更新配置
    config = Config()
    
    # 如果命令行提供了参数，更新配置文件
    if args.api_key:
        print(f"⚙️  更新配置: API Key -> {args.api_key[:8]}***")
        config.set_api_key(args.api_key)
    
    if args.whisper_model:
        print(f"⚙️  更新配置: Whisper模型 -> {args.whisper_model}")
        config.set_whisper_model(args.whisper_model)
        
    if args.gpt_model:
        print(f"⚙️  更新配置: GPT模型 -> {args.gpt_model}")
        config.set_gpt_model(args.gpt_model)
        
    if args.output_dir:
        print(f"⚙️  更新配置: 输出目录 -> {args.output_dir}")
        config.set_output_dir(args.output_dir)
    
    # 获取最终使用的配置
    api_key = config.get_api_key()
    if not api_key:
        print("❌ 错误: 未找到 API Key。请使用 --api-key 参数设置或在 GUI 中配置。")
        sys.exit(1)
        
    whisper_model = config.get_whisper_model()
    # 处理 "自定义路径..." 的情况 (虽然 Config set 进去的通常是路径本身，但为了健壮性)
    if whisper_model == '自定义路径...':
        custom_path = config.get_custom_model_path()
        if custom_path:
            whisper_model = custom_path
        else:
            whisper_model = 'base'

    gpt_model = config.get_gpt_model()
    output_dir = config.get_output_dir()
    
    # CPU 模式 (环境变量设置，不持久化到 Config，除非 Config 有对应字段，目前 Config 似乎没有 cpu 字段)
    if args.cpu:
        os.environ['FORCE_CPU'] = '1'
        print("⚠️ 已强制使用 CPU 模式")
    
    ensure_dir(output_dir)
    print(f"📂 输出目录: {output_dir}")
    print(f"🤖 模型设置: Whisper={whisper_model}, GPT={gpt_model}")
    
    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. 获取信息 (优先元数据标题)
            print("\n============ 1. 获取视频信息 ============")
            video_meta = VideoInfoFetcher.get_info(url)
            meta_title = ""
            if video_meta:
                meta_title = video_meta.get('title', '')
                print(f"✓ 标题: {meta_title}")
                print(f"✓ UP主: {video_meta.get('owner', 'Unknown')}")
            else:
                print("⚠️ 无法获取元数据，将尝试直接下载")

            # 2. 下载视频
            print("\n============ 2. 下载视频 ============")
            downloader = VideoDownloader(temp_dir)
            
            # 下载视频
            download_result = downloader.download_video(url, progress_callback=lambda p, s: print(f"  -> {s}") if p % 20 == 0 else None)
            
            if not download_result:
                print("❌ 下载失败")
                sys.exit(1)
            
            # 确定最终标题: 优先使用元数据标题，其次是下载器获取的标题
            final_title = meta_title or download_result.get('title', 'Unknown')
            # 再次清理标题，确保安全
            safe_title = safe_filename(final_title)
            
            video_path = download_result['video_path']
            print(f"✓ 下载完成 (标题锁定: {final_title})")
            
            # 3. 处理音频
            print("\n============ 3. 提取与处理音频 ============")
            processor = AudioProcessor()
            processed_audio = processor.process_audio(video_path, progress_callback=lambda p, s: None)
            print(f"✓ 音频准备就绪")
            
            # 4. 转写
            print("\n============ 4. 语音转写 ============")
            transcriber = Transcriber(whisper_model, api_key=api_key)
            
            def transcribe_progress(p, s):
                if p > 90 or p % 20 == 0: print(f"  -> {s}")
                
            transcribe_result = transcriber.transcribe(processed_audio, progress_callback=transcribe_progress)
            transcript_text = transcribe_result['text']
            
            if 'usage' in transcribe_result:
                usage = transcribe_result['usage']
                if hasattr(usage, 'total_tokens'): # Object
                     print(f"💰 转写 Token: {usage.total_tokens}")
                else: # Dict
                     print(f"💰 转写 Token: {usage}")
                     
            print(f"✓ 转写完成 (长度: {len(transcript_text)} 字符)")
            
            # 5. 总结
            print("\n============ 5. 生成总结 ============")
            summarizer = Summarizer(api_key)
            summary_result = summarizer.generate_summary(
                transcript_text, 
                video_title=final_title,
                model=gpt_model
            )
            print("✓ 总结生成完成")
            
            # 6. 保存文件 (单文件模式)
            print("\n============ 6. 保存文件 ============")
            
            md_filename = f"{safe_title}.md"
            md_filepath = os.path.join(output_dir, md_filename)
            
            # 避免覆盖
            if os.path.exists(md_filepath):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                md_filename = f"{safe_title}_{timestamp}.md"
                md_filepath = os.path.join(output_dir, md_filename)
            
            content = f"# {final_title}\n\n"
            content += f"**URL**: {url}\n"
            content += f"**日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            content += f"## 💡 核心总结\n\n{summary_result.get('summary', '')}\n\n"
            content += f"## 📑 详细大纲\n\n{summary_result.get('outline', '')}\n\n"
            content += f"## 💎 价值内容\n\n{summary_result.get('value_content', '')}\n\n"
            content += f"---\n\n## 📝 语音转写原文\n\n{transcript_text}"
            
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"✅ 总结已保存: {md_filepath}")
            # 临时目录也就是 temp_dir 退出后会自动清理视频和音频，无需手动 move 或 remove

    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        # import traceback
        # traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="Bilibili 视频总结工具")
    parser.add_argument('url', nargs='?', help='视频链接或BV号')
    parser.add_argument('--ui', action='store_true', help='强制启动图形界面')
    parser.add_argument('--api-key', help='OpenAI API Key (覆盖配置)')
    parser.add_argument('--whisper-model', help='Whisper 模型 (覆盖配置)')
    parser.add_argument('--gpt-model', help='GPT 模型 (覆盖配置)')
    parser.add_argument('--output-dir', help='输出目录 (默认 ~/Downloads)')
    parser.add_argument('--cpu', action='store_true', help='强制使用 CPU')
    
    args = parser.parse_args()
    
    main(args, parser)

