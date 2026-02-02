# Bilibili 视频总结工具 (Bili-Summarizer)

这是一个全自动的 Bilibili 视频总结工具，能够下载视频音频，使用 Whisper 进行精准转写，并利用 LLM (GPT) 生成结构化的内容总结。

## ✨ 功能特点

- **全自动流程**：输入链接，自动完成下载 -> 音频提取 -> 语音转写 -> 内容总结。
- **双模式运行**：
  - **GUI 界面**：直观的图形界面，支持参数配置、进度预览和历史记录。
  - **命令行 (CLI)**：适合脚本集成或极简操作。
- **智能转写**：集成 OpenAI Whisper 模型（支持 GPU 加速），精准识别视频语音。
- **AI 总结**：使用 GPT 模型生成三个层次的总结：核心摘要、详细大纲、价值内容提取。
- **自动环境配置**：首次运行自动检测并安装 Python 依赖。
- **多平台支持**：支持 Windows 和 macOS（针对 Apple Silicon 优化 MPS 加速）。

## 🛠️ 安装说明

### 1. 前置要求
- **Python 3.8+**: 请确保已安装 Python 环境。
- **FFmpeg**: **必须安装**，用于音频处理。

**安装 FFmpeg:**
- **macOS**: `brew install ffmpeg`
- **Windows**: `choco install ffmpeg` 或下载编译好的 exe 加入环境变量。
- **Ubuntu**: `sudo apt install ffmpeg`

### 2. 获取代码
```bash
git clone <repository-url>
cd bili视频总结
```

### 3. 安装依赖
程序会在首次运行时自动尝试安装依赖，也可以手动安装：
```bash
pip install -r requirements.txt
```

## 🚀 使用指南

### 方式一：图形界面 (推荐)
直接运行启动脚本或使用命令：
```bash
python main.py --ui
```
或者在 Windows 上双击 `启动程序.bat`，macOS 上运行 `启动程序.command`。

在界面中：
1. 输入 Bilibili 视频链接 (支持短链)。
2. 首次使用请在“设置”中配置 **OpenAI API Key**。
3. 点击“开始处理”。

### 方式二：命令行模式
直接在命令行后跟视频链接：
```bash
python main.py "https://www.bilibili.com/video/BV1xxxxxx"
```
支持的参数：
- `--api-key`: 临时指定 API Key。
- `--output-dir`: 指定输出目录 (默认 `~/Downloads`)。
- `--cpu`: 强制使用 CPU (默认会自动检测 GPU)。

## ⚙️ 配置说明

所有配置（API Key、模型选择等）会自动保存到本地的 `config.json` 文件中（该文件已在 `.gitignore` 中忽略，确保隐私安全）。

- **Whisper 模型**: 推荐使用 `base` 或 `small` 以平衡速度和精度。
- **GPT 模型**: 默认使用 `gpt-4o-mini`，性价比最高。

## ⚠️ 注意事项

- 本工具需要联网使用 (OpenAI API)。
- 请确保视频有清晰的语音，背景音乐过大会影响转写质量。
- **隐私提醒**: 您的 API Key 仅保存在本地 `config.json`，不会上传到任何第三方服务器。请勿将包含 Key 的 `config.json` 提交到版本控制系统中。

## 📝 License
MIT License
