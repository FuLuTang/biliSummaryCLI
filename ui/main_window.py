"""
主窗口模块
Bilibili视频总结工具的主界面
"""
import os
import tempfile
import shutil
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QProgressBar, QTextEdit, QTabWidget, QFileDialog,
    QMessageBox, QStatusBar, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from utils.config import Config
from utils.helpers import validate_bilibili_url, format_duration, safe_filename
from core.downloader import VideoDownloader
from core.audio_processor import AudioProcessor
from core.transcriber import Transcriber
from core.summarizer import Summarizer
from core.video_info import VideoInfoFetcher


class VideoInfoThread(QThread):
    """异步获取视频信息的线程"""
    info_received = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            info = VideoInfoFetcher.get_info(self.url)
            if info:
                self.info_received.emit(info)
            else:
                self.error.emit("无法获取视频信息")
        except Exception as e:
            self.error.emit(str(e))


class ProcessThread(QThread):
    """后台处理线程"""
    progress = pyqtSignal(float, str)  # 进度百分比, 状态文本
    finished = pyqtSignal(dict)  # 处理结果
    error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, url: str, api_key: str, model: str, custom_model_path: str = "", gpt_model: str = "gpt-4o-mini", output_dir: str = ""):
        super().__init__()
        self.url = url
        self.api_key = api_key
        self.model = model
        self.custom_model_path = custom_model_path
        self.gpt_model = gpt_model
        self.output_dir = output_dir or os.path.join(os.path.expanduser('~'), 'Downloads')
        self.temp_dir = tempfile.mkdtemp(prefix="bili_summary_")
    
    def run(self):
        try:
            print("\n" + "="*60)
            print("🚀 开始处理视频")
            print("="*60)
            
            # 0. 先尝试获取详细视频信息 (用于更精准的标题)
            print("\n📡 获取视频元数据...")
            self.progress.emit(2, "获取视频元数据...")
            video_meta = VideoInfoFetcher.get_info(self.url)
            meta_title = video_meta.get('title', '') if video_meta else ""
            
            if video_meta:
                print(f"✓ 视频标题: {meta_title}")
                print(f"✓ UP主: {video_meta.get('owner', '未知')}")
                print(f"✓ BV号: {video_meta.get('bvid', '')}")
            
            # 1. 下载视频 (代理方式)
            print("\n⬇️  开始下载视频...")
            self.progress.emit(5, "初始化下载器...")
            downloader = VideoDownloader(self.temp_dir)
            download_result = downloader.download_video(
                self.url, 
                progress_callback=self.progress.emit
            )
            
            # 如果 meta_title 为空，使用下载器获取的标题
            final_title = meta_title or download_result.get('title', 'Unknown')
            duration = download_result.get('duration', 0)
            print(f"✓ 音频下载完成 (时长: {int(duration//60)}分{int(duration%60)}秒)")
            
            # 2. 处理音频
            print("\n🎵 处理音频格式...")
            processor = AudioProcessor()
            processed_audio = processor.process_audio(
                download_result['video_path'],
                progress_callback=self.progress.emit
            )
            
            # 获取音频文件大小
            import os
            audio_size = os.path.getsize(processed_audio)
            if audio_size >= 1024 * 1024:
                size_str = f"{audio_size / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{audio_size / 1024:.2f} KB"
            
            print(f"✓ 音频处理完成")
            print(f"  - 文件路径: {processed_audio}")
            print(f"  - 萃取后大小: {size_str}")
            
            # 3. 语音转写
            print(f"\n🎙️  开始语音转写 (使用 {self.model} 模型)...")
            model_to_use = self.custom_model_path if self.custom_model_path else self.model
            transcriber = Transcriber(model_to_use, api_key=self.api_key)
            transcribe_result = transcriber.transcribe(
                processed_audio,
                progress_callback=self.progress.emit
            )
            
            detected_lang = transcribe_result.get('language', 'unknown')
            text_length = len(transcribe_result.get('text', ''))
            print(f"✓ 转写完成")
            print(f"  - 检测到的语言: {detected_lang}")
            print(f"  - 文本长度: {text_length} 字符")
            
            # 4. 生成总结 (使用用户选择的GPT模型)
            print(f"\n🤖 使用 {self.gpt_model} 生成总结...")
            summarizer = Summarizer(self.api_key)
            summary_result = summarizer.generate_summary(
                transcribe_result['text'],
                video_title=final_title,
                model=self.gpt_model,
                progress_callback=self.progress.emit
            )
            
            print("✓ 总结生成完成")
            
            print("\n📂 正在保存结果...")
            self.progress.emit(98, "正在保存文件...")
            
            # 6. 保存 Markdown (只输出这一个文件)
            safe_title = safe_filename(final_title)
            # 使用简单的标题作为文件名
            md_filename = f"{safe_title}.md"
            md_filepath = os.path.join(self.output_dir, md_filename)
            
            # 避免重名覆盖
            if os.path.exists(md_filepath):
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
                md_filename = f"{safe_title}_{timestamp_str}.md"
                md_filepath = os.path.join(self.output_dir, md_filename)

            md_content = f"# {final_title}\n\n"
            md_content += f"**URL**: {self.url}\n"
            md_content += f"**日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            md_content += f"## 💡 核心总结\n\n{summary_result.get('summary', '')}\n\n"
            md_content += f"## 📑 详细大纲\n\n{summary_result.get('outline', '')}\n\n"
            md_content += f"## 💎 价值内容\n\n{summary_result.get('value_content', '')}\n\n"
            md_content += f"---\n\n## 📝 语音转写原文\n\n{transcribe_result['text']}"
            
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
            print(f"✓ 文件已保存至: {md_filepath}")
            self.progress.emit(100, "处理完成！")
            
            # 返回结果，包含路径信息
            result = {
                'title': final_title,
                'md_path': md_filepath,
                'duration': download_result.get('duration', 0),
                'language': transcribe_result.get('language', ''),
                'summary': summary_result.get('summary', ''),
                'outline': summary_result.get('outline', ''),
                'value_content': summary_result.get('value_content', ''),
                'transcript': transcribe_result.get('text', ''),
                'timestamp': datetime.now().isoformat()
            }
            if video_meta:
                result['owner'] = video_meta.get('owner')
                result['bvid'] = video_meta.get('bvid')
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))
        
        finally:
            # 清理临时文件
            try:
                if os.path.exists(self.temp_dir):
                    shutil.rmtree(self.temp_dir)
            except Exception:
                pass


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.process_thread: Optional[ProcessThread] = None
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("Bilibili 视频总结工具")
        self.setMinimumSize(1000, 750)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 顶部标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("📺 Bilibili 视频总结工具")
        title_label.setProperty("heading", True)
        title_label.setFont(QFont(".AppleSystemUIFont", 22, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)
        
        # 2. 中间主体 (使用 Splitter 分为左右两部分)
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- 左侧侧边栏 (设置 & 输入) ---
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 10, 0)
        sidebar_layout.setSpacing(16)
        
        # === 设置区域 ===
        settings_group = QGroupBox("⚙️ 配置")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setSpacing(10)
        
        # API Key
        settings_layout.addWidget(QLabel("OpenAI API Key:"), 0, 0)
        key_hbox = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        key_hbox.addWidget(self.api_key_input)
        
        self.show_key_btn = QPushButton("👁")
        self.show_key_btn.setFixedWidth(35)
        self.show_key_btn.setProperty("secondary", True)
        self.show_key_btn.clicked.connect(self.toggle_api_key_visibility)
        key_hbox.addWidget(self.show_key_btn)
        settings_layout.addLayout(key_hbox, 0, 1)
        
        # GPT模型
        settings_layout.addWidget(QLabel("GPT 模型:"), 1, 0)
        self.gpt_model_combo = QComboBox()
        self.gpt_model_combo.setEditable(True)
        self.gpt_model_combo.addItems(['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'])
        self.gpt_model_combo.setPlaceholderText("选择或输入模型")
        settings_layout.addWidget(self.gpt_model_combo, 1, 1)
        
        # Whisper模型
        settings_layout.addWidget(QLabel("Whisper 模型:"), 2, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            'tiny', 'base', 'small', 'medium', 'large', 'turbo', 
            'gpt-4o-transcribe', 'gpt-4o-mini-transcribe',
            '自定义路径...'
        ])
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        settings_layout.addWidget(self.model_combo, 2, 1)
        
        # 强制 CPU 模式复选框
        self.cpu_mode_check = QCheckBox("强制使用 CPU (解决 NaN 报错)")
        self.cpu_mode_check.setToolTip("如果遇到 'Input contains NaN' 或 'Tensor invalid values' 错误，请勾选此项")
        settings_layout.addWidget(self.cpu_mode_check, 3, 1)
        
        # 自定义模型路径
        # 自定义模型路径 (顺延行号)
        self.custom_model_label = QLabel("模型文件:")
        self.custom_model_label.setVisible(False)
        settings_layout.addWidget(self.custom_model_label, 4, 0)
        
        path_hbox = QHBoxLayout()
        self.custom_model_input = QLineEdit()
        self.custom_model_input.setPlaceholderText("选择.pt文件")
        self.custom_model_input.setVisible(False)
        path_hbox.addWidget(self.custom_model_input)
        
        self.browse_model_btn = QPushButton("📁")
        self.browse_model_btn.setFixedWidth(35)
        self.browse_model_btn.setProperty("secondary", True)
        self.browse_model_btn.setVisible(False)
        self.browse_model_btn.clicked.connect(self.browse_model_path)
        path_hbox.addWidget(self.browse_model_btn)
        settings_layout.addLayout(path_hbox, 4, 1)
        
        # 卸载模型按钮
        self.unload_model_btn = QPushButton("🗑️ 清理模型缓存 (释放硬盘)")
        self.unload_model_btn.setProperty("secondary", True)
        self.unload_model_btn.clicked.connect(self.unload_whisper_model)
        settings_layout.addWidget(self.unload_model_btn, 5, 0, 1, 2)
        
        sidebar_layout.addWidget(settings_group)
        
        # === 视频输入区域 ===
        input_group = QGroupBox("🔗 视频任务")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(10)
        
        input_layout.addWidget(QLabel("Bilibili 链接 / BV号:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("例如: BV1xr6GB5EnH")
        self.url_input.setMinimumHeight(35)
        self.url_input.returnPressed.connect(self.start_process)
        input_layout.addWidget(self.url_input)
        
        self.process_btn = QPushButton("🚀 开始处理")
        self.process_btn.setMinimumHeight(45)
        self.process_btn.clicked.connect(self.start_process)
        input_layout.addWidget(self.process_btn)
        
        sidebar_layout.addWidget(input_group)
        
        # === 视频预览区域 (默认隐藏) ===
        self.video_info_group = QGroupBox("🎬 视频预览")
        self.video_info_group.setVisible(False)
        info_vbox = QVBoxLayout(self.video_info_group)
        
        self.video_title_label = QLabel("")
        self.video_title_label.setWordWrap(True)
        self.video_title_label.setStyleSheet("font-weight: bold; color: #fff;")
        info_vbox.addWidget(self.video_title_label)
        
        self.video_owner_label = QLabel("")
        self.video_owner_label.setStyleSheet("color: #aaa; font-size: 11px;")
        info_vbox.addWidget(self.video_owner_label)
        
        sidebar_layout.addWidget(self.video_info_group)
        
        # 绑定 URL 变化事件
        self.url_input.textChanged.connect(self.on_url_changed)
        
        # === 进度区域 ===
        progress_group = QGroupBox("📊 当前状态")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("等待任务开始...")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        progress_layout.addWidget(self.status_label)
        
        sidebar_layout.addWidget(progress_group)
        sidebar_layout.addStretch() # 将内容推到顶部
        
        # --- 右侧主面板 (结果显示) ---
        main_panel = QWidget()
        panel_layout = QVBoxLayout(main_panel)
        panel_layout.setContentsMargins(10, 0, 0, 0)
        panel_layout.setSpacing(10)
        
        result_group = QGroupBox("📝 总结结果")
        result_layout = QVBoxLayout(result_group)
        
        self.result_tabs = QTabWidget()
        self.result_tabs.setDocumentMode(True)
        
        # 主要内容与评价
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.result_tabs.addTab(self.summary_text, "📋 核心总结")
        
        # 内容概述
        self.outline_text = QTextEdit()
        self.outline_text.setReadOnly(True)
        self.result_tabs.addTab(self.outline_text, "📝 逻辑大纲")

        # 价值内容
        self.value_text = QTextEdit()
        self.value_text.setReadOnly(True)
        self.result_tabs.addTab(self.value_text, "💡 价值内容")
        
        # 原始转写
        self.transcript_text = QTextEdit()
        self.transcript_text.setReadOnly(True)
        self.result_tabs.addTab(self.transcript_text, "📄 完整转录")
        
        result_layout.addWidget(self.result_tabs)
        
        # 底部操作栏
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        self.export_btn = QPushButton("💾 导出结果 (.md)")
        self.export_btn.setFixedWidth(150)
        self.export_btn.setProperty("secondary", True)
        self.export_btn.clicked.connect(self.export_result)
        self.export_btn.setEnabled(False)
        footer_layout.addWidget(self.export_btn)
        
        result_layout.addLayout(footer_layout)
        panel_layout.addWidget(result_group)
        
        # 将左右面板加入 Splitter
        content_splitter.addWidget(sidebar_widget)
        content_splitter.addWidget(main_panel)
        content_splitter.setStretchFactor(0, 1) # 左侧占比小
        content_splitter.setStretchFactor(1, 4) # 右侧占比更大
        content_splitter.setSizes([280, 720])
        
        main_layout.addWidget(content_splitter)
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

    
    def load_settings(self):
        """加载保存的设置"""
        # API Key
        api_key = self.config.get_api_key()
        if api_key:
            self.api_key_input.setText(api_key)
        
        # Whisper模型
        model = self.config.get_whisper_model()
        if model in ['tiny', 'base', 'small', 'medium', 'large', 'turbo', 'gpt-4o-transcribe', 'gpt-4o-mini-transcribe']:
            self.model_combo.setCurrentText(model)
        else:
            self.model_combo.setCurrentText('自定义路径...')
            self.custom_model_input.setText(model)
        
        # GPT模型
        gpt_model = self.config.get_gpt_model()
        # 如果是预设模型，选中它；否则直接设置文本
        index = self.gpt_model_combo.findText(gpt_model)
        if index >= 0:
            self.gpt_model_combo.setCurrentIndex(index)
        else:
            self.gpt_model_combo.setCurrentText(gpt_model)
    
    def save_settings(self):
        """保存设置"""
        self.config.set_api_key(self.api_key_input.text().strip())
        
        if self.model_combo.currentText() == '自定义路径...':
            self.config.set_whisper_model(self.custom_model_input.text().strip())
        else:
            self.config.set_whisper_model(self.model_combo.currentText())
        
        # 保存GPT模型选择
        self.config.set_gpt_model(self.gpt_model_combo.currentText())
    
    def toggle_api_key_visibility(self):
        """切换API Key显示状态"""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("🙈")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("👁")
    
    def on_model_changed(self, text: str):
        """模型选择变化"""
        is_custom = text == '自定义路径...'
        self.custom_model_label.setVisible(is_custom)
        self.custom_model_input.setVisible(is_custom)
        self.browse_model_btn.setVisible(is_custom)
    
    def browse_model_path(self):
        """浏览模型文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择Whisper模型文件", "",
            "PyTorch模型 (*.pt);;所有文件 (*)"
        )
        if path:
            self.custom_model_input.setText(path)

    def unload_whisper_model(self):
        """卸载模型并清理硬盘缓存"""
        try:
            # 1. 清理内存中的模型（如果有）
            # 注意：由于模型是在线程中加载的，且线程结束后会自动释放，这里主要清理硬盘
            
            # 2. 清理硬盘缓存 
            # faster-whisper 使用 HuggingFace cache (~/.cache/huggingface/hub)
            hf_cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            # 同时也检查旧的 whisper 缓存
            old_cache_dir = os.path.expanduser("~/.cache/whisper")
            
            total_size = 0
            found_dirs = []
            
            # 扫描 HuggingFace 缓存 (只扫描 whisper 相关的)
            if os.path.exists(hf_cache_dir):
                for d in os.listdir(hf_cache_dir):
                    if "whisper" in d.lower():
                        full_path = os.path.join(hf_cache_dir, d)
                        size = sum(os.path.getsize(os.path.join(dirpath, filename)) for dirpath, _, filenames in os.walk(full_path) for filename in filenames)
                        total_size += size
                        found_dirs.append(full_path)

            # 扫描旧缓存
            if os.path.exists(old_cache_dir):
                files = os.listdir(old_cache_dir)
                if files:
                   size = sum(os.path.getsize(os.path.join(old_cache_dir, f)) for f in files)
                   total_size += size
                   found_dirs.append(old_cache_dir)
            
            if total_size == 0:
                QMessageBox.information(self, "清理完成", "未发现 Whisper 模型缓存。")
                return

            size_mb = total_size / (1024 * 1024)
            size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"
                
            reply = QMessageBox.question(
                self, "确认清理", 
                f"检测到缓存模型文件，共占用 {size_str} 硬盘空间。\n\n"
                "确定要全部删除吗？\n"
                "(下次使用时需要重新下载)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                import shutil
                for d in found_dirs:
                    if os.path.isfile(d): # 虽然目前逻辑d都是目录，但为了安全
                        os.remove(d)
                    else:
                        shutil.rmtree(d)
                        # 如果是旧缓存目录，重建它
                        if d == old_cache_dir:
                            os.makedirs(d)
                            
                QMessageBox.information(self, "成功", "已清空模型缓存，释放了硬盘空间！")
                self.statusBar.showMessage(f"已释放 {size_str} 硬盘空间")
            else:
                QMessageBox.information(self, "提示", "未找到默认缓存目录，可能暂无缓存。")
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"清理失败: {str(e)}")
    
    def validate_inputs(self) -> tuple[bool, str]:
        """验证输入"""
        # 验证API Key
        api_key = self.api_key_input.text().strip()
        if not api_key:
            return False, "请输入OpenAI API Key"
        
        if not api_key.startswith('sk-'):
            return False, "API Key格式不正确，应以'sk-'开头"
        
        # 验证URL
        url = self.url_input.text().strip()
        valid, msg = validate_bilibili_url(url)
        if not valid:
            return False, msg
        
        # 验证模型
        if self.model_combo.currentText() == '自定义路径...':
            custom_path = self.custom_model_input.text().strip()
            if not custom_path:
                return False, "请选择自定义模型文件"
            if not os.path.exists(custom_path):
                return False, "模型文件不存在"
        
        return True, ""
    
    def start_process(self):
        """开始处理"""
        # 验证输入
        valid, error = self.validate_inputs()
        if not valid:
            QMessageBox.warning(self, "输入错误", error)
            return
        
        # 保存设置
        self.save_settings()
        
        # 清空结果
        self.summary_text.clear()
        self.outline_text.clear()
        self.value_text.clear()
        self.transcript_text.clear()
        self.export_btn.setEnabled(False)
        
        # 禁用输入
        self.set_inputs_enabled(False)
        
        # 获取参数
        url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        gpt_model = self.gpt_model_combo.currentText()
        custom_path = ""
        
        if model == '自定义路径...':
            model = 'base'
            custom_path = self.custom_model_input.text().strip()
        
        # 获取 CPU 模式选项
        force_cpu = self.cpu_mode_check.isChecked()
        if force_cpu:
            os.environ['FORCE_CPU'] = '1'
        else:
            os.environ['FORCE_CPU'] = '0'
        
        # 启动处理线程
        output_dir = self.config.get_output_dir()
        self.process_thread = ProcessThread(url, api_key, model, custom_path, gpt_model, output_dir=output_dir)
        self.process_thread.progress.connect(self.on_progress)
        self.process_thread.finished.connect(self.on_finished)
        self.process_thread.error.connect(self.on_error)
        self.process_thread.start()
    
    def set_inputs_enabled(self, enabled: bool):
        """启用/禁用输入控件"""
        self.api_key_input.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.custom_model_input.setEnabled(enabled)
        self.url_input.setEnabled(enabled)
        self.process_btn.setEnabled(enabled)
        self.browse_model_btn.setEnabled(enabled)
    
    def on_progress(self, percent: float, status: str):
        """更新进度"""
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(status)
        self.statusBar.showMessage(f"处理中: {status}")
    
    def on_finished(self, result: dict):
        """处理完成"""
        self.set_inputs_enabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ 处理完成！")
        self.statusBar.showMessage(f"完成: {result.get('title', '')}")
        
        # 显示结果
        self.summary_text.setPlainText(result.get('summary', ''))
        self.outline_text.setPlainText(result.get('outline', ''))
        self.value_text.setPlainText(result.get('value_content', ''))
        self.transcript_text.setPlainText(result.get('transcript', ''))
        
        self.export_btn.setEnabled(True)
        
        # 保存当前结果供导出
        self._current_result = result
        
        # 弹窗提示并询问是否打开文件夹
        # 弹窗提示并询问是否打开文件
        md_path = result.get('md_path')
        if md_path and os.path.exists(md_path):
            reply = QMessageBox.question(
                self, "任务完成", 
                f"视频处理与总结已完成！\n\n文件已保存至:\n{md_path}\n\n是否立即打开文件？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess
                try:
                    if os.name == 'nt': # Windows
                        os.startfile(md_path)
                    else: # macOS / Linux
                        subprocess.run(['open', md_path])
                except:
                    pass
    
    def on_error(self, error: str):
        """处理错误"""
        self.set_inputs_enabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"❌ 错误: {error}")
        self.statusBar.showMessage("处理失败")
        
        QMessageBox.critical(self, "处理失败", f"处理过程中发生错误:\n\n{error}")
    
    def export_result(self):
        """导出结果"""
        if not hasattr(self, '_current_result'):
            return
        
        result = self._current_result
        
        # 生成默认文件名
        safe_title = safe_filename(result.get('title', '视频总结'))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        default_filename = f"{safe_title}_{timestamp}.md"
        
        # 选择保存路径
        path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", 
            default_filename,
            "Markdown文件 (*.md);;文本文件 (*.txt)"
        )
        
        if not path:
            return
        
        # 生成Markdown内容
        content = f"""# {result.get('title', '视频总结')}

生成时间: {result.get('timestamp', '')}

---

## 一、主要内容与主观评价

{result.get('summary', '')}

---

## 二、内容概述

{result.get('outline', '')}

---

## 三、价值内容

{result.get('value_content', '')}

---

## 四、原始转写

{result.get('transcript', '')}
"""
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            QMessageBox.information(self, "导出成功", f"结果已导出到:\n{path}")
            self.statusBar.showMessage(f"已导出: {path}")
            
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出失败: {str(e)}")
    
    def on_url_changed(self, text: str):
        """当URL输入框内容改变时"""
        url = text.strip()
        if not url:
            self.video_info_group.setVisible(False)
            return

        # 简单验证一下，避免乱搜
        if not ('BV' in url.upper() or 'av' in url.lower() or 'bilibili.com' in url):
            return

        # 如果已有线程在跑，先不管或停止它
        if hasattr(self, 'info_thread') and self.info_thread and self.info_thread.isRunning():
            return # 或者 self.info_thread.terminate()

        self.info_thread = VideoInfoThread(url)
        self.info_thread.info_received.connect(self.update_video_preview)
        self.info_thread.start()

    def update_video_preview(self, info: dict):
        """更新视频预览面板"""
        self.video_title_label.setText(info.get('title', ''))
        owner = info.get('owner', '未知UP主')
        bvid = info.get('bvid', '')
        self.video_owner_label.setText(f"UP主: {owner}  |  {bvid}")
        self.video_info_group.setVisible(True)

    def closeEvent(self, event):
        """关闭窗口时保存设置"""
        self.save_settings()
        
        # 停止信息获取线程
        if hasattr(self, 'info_thread') and self.info_thread and self.info_thread.isRunning():
            self.info_thread.terminate()
            self.info_thread.wait()

        # 停止后台处理线程
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.terminate()
            self.process_thread.wait()
        
        event.accept()
