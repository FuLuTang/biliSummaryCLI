# Bilibili 视频总结 - iOS 快捷指令移植指南

由于 iOS 快捷指令无法直接运行 Python 脚本和本地 Whisper 模型，要实现同样的功能，需要将核心逻辑转为**云端 API 调用**。

## 核心流程图

1. **输入 URL**：接收 Bilibili 视频链接。
2. **解析下载**：利用第三方 API 获取音频下载地址并下载文件。
3. **音频处理**：使用“转换媒体”操作确保音频格式正确（建议转为 M4A/MP3）。
4. **语音转写**：将音频发送至 **OpenAI Whisper API**。
5. **GPT 总结**：将转写文本发送至 **OpenAI GPT API** 自定义模型。
6. **输出结果**：显示或保存生成的 Markdown 总结。

---

## 详细配置步骤

### 1. 获取 B站音频 URL
这是最难的一步，因为快捷指令没有 `yt-dlp`。
- **方案**：使用公开的 B站解析接口（例如 `https://api.bilibili.com/x/player/wbi/playurl`，由于加密较复杂，通常建议在市面上寻找已有的“B站视频下载”快捷指令作为起点，将其下载逻辑集成进来）。

### 2. 音频转换 (快捷指令原生)
- **操作**：使用 `转换媒体` (Encode Media)。
- **设置**：
  - 获取：刚才下载的媒体文件
  - 格式：仅音频 (Audio Only)
  - 目的：M4A 或 MP3 (为了减小体积)

### 3. 调用 OpenAI Whisper API (转写)
- **操作**：使用 `获取 URL 内容` (Get Contents of URL)。
- **URL**: `https://api.openai.com/v1/audio/transcriptions`
- **方法**: `POST`
- **头部 (Headers)**:
  - `Authorization`: `Bearer YOUR_API_KEY`
- **请求体 (Request Body)**: 选择 `表单` (Form)
  - `file`: 选择步骤 2 转换后的音频文件（类型选 "文件"）
  - `model`: 文本 `whisper-1`
  - `language`: 文本 `zh` (可选)

### 4. 调用 OpenAI GPT API (总结)
- **操作**：使用 `获取 URL 内容` (Get Contents of URL)。
- **URL**: `https://api.openai.com/v1/chat/completions`
- **方法**: `POST`
- **头部 (Headers)**:
  - `Authorization`: `Bearer YOUR_API_KEY`
  - `Content-Type`: `application/json`
- **请求体 (Request Body)**: 选择 `JSON`
  - `model`: `gpt-4o-mini` (或者你喜欢的模型)
  - `temperature`: `1`
  - `messages`: (创建一个包含 system 和 user 公式的数组)
    - `system`: "你是一个内容分析专家..."
    - `user`: "请总结以下内容：[Whisper 返回的文本]"

---

## 避坑指南 (关键限制)

1. **25MB 文件限制**：
   OpenAI Whisper API 限制音频文件最大 25MB。如果是长视频，快捷指令目前很难自动切割音频。
   - **对策**：转换音频时调低比特率，或者仅处理 15 分钟以内的视频。

2. **超时问题**：
   iOS 快捷指令的 HTTP 请求有约 25-30 秒的超时限制。如果视频太长，Whisper 转写时间过久，快捷指令可能会断开。
   - **对策**：优先处理短视频。

3. **证书问题**：
   如果遇到证书报错，确保快捷指令设置中允许执行脚本和访问网络。

---

## 替代方案：快捷指令调用 Mac (远程触发)

如果你刚好有一台常开的 Mac，可以用更黑科技的方法：
1. **iOS 快捷指令**：通过 SSH 发送指令到你的 Mac。
2. **Mac 端**：运行我们现在的 Python 脚本（增加一个命令行参数模式）。
3. **回传**：Mac 处理完后通过 iCloud Drive 或 SSH 回传结果到 iPhone。

这种方法可以**省去 Whisper API 的费用**，因为是在 Mac 本地跑模型。
