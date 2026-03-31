# 智能语音助手 🎙️

实时语音转文字 + DeepSeek AI 对话 + 记忆搜索

## 项目结构

```
voice_assistant/
├── main.py              ← 启动入口
├── config.py            ← 所有配置项
├── requirements.txt     ← Python 依赖
├── core/
│   ├── memory.py        ← 对话记忆 & 搜索
│   ├── ai.py            ← DeepSeek AI 对话
│   └── stt.py           ← 实时语音识别
├── ui/
│   ├── main_window.py   ← 主窗口
│   └── widgets.py       ← 消息气泡等组件
├── model/               ← 放语音模型（见下方）
└── output/
    └── memory.json      ← 自动生成，保存对话历史
```

---

## 安装步骤

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 下载语音识别模型

将模型文件放入项目根目录的 `model/` 文件夹（如果不存在请手动创建）。

**推荐模型（中英文双语，约 200MB）：**

```
https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2
```

下载解压后，把里面的文件全部复制到 `model/` 目录：

```
model/
├── encoder-epoch-99-avg-1.int8.onnx   ← encoder
├── decoder-epoch-99-avg-1.onnx        ← decoder
├── joiner-epoch-99-avg-1.int8.onnx    ← joiner
└── tokens.txt
```

> 程序会自动识别 Transducer 或 CTC 两种格式，文件名不必完全一致。
> 只要目录下有 `encoder*.onnx`、`decoder*.onnx`、`joiner*.onnx`、`tokens.txt` 即可。

**其他可用模型：**

| 模型名 | 大小 | 特点 |
|--------|------|------|
| sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20 | ~200MB | 中英双语，推荐 |
| sherpa-onnx-streaming-zipformer-small-ctc-zh-2025-04-01 | ~87MB | 纯中文，较小 |
| sherpa-onnx-streaming-zipformer-zh-int8-2025-06-30 | ~60MB | 纯中文，量化版 |

所有模型下载地址：https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models

### 3. 配置 DeepSeek API Key

**方式一：环境变量（推荐）**
```bash
# macOS / Linux
export DEEPSEEK_API_KEY=sk-xxxxxxxx

# Windows (CMD)
set DEEPSEEK_API_KEY=sk-xxxxxxxx

# Windows (PowerShell)
$env:DEEPSEEK_API_KEY="sk-xxxxxxxx"
```

**方式二：启动后在界面左侧填写**

DeepSeek API Key 申请地址：https://platform.deepseek.com

---

## 启动程序

```bash
python main.py
```

---

## 使用说明

### 语音输入
1. 在左侧选择正确的麦克风
2. 点击「开始录音」
3. 说话，停顿约 1-2 秒后自动识别并发送给 AI

### 文字输入
在底部输入框直接输入，按 Enter 或点击「发送」

### 记忆搜索
程序会自动检测以下查询意图，并从历史记录中搜索相关内容：

| 示例输入 | 行为 |
|----------|------|
| 帮我查一下明天的行程 | 搜索明天日期相关记录 |
| 今天有什么安排？ | 搜索今天相关记录 |
| 我之前说过什么会议？ | 关键词"会议"全局搜索 |
| 查找一下我的待办事项 | 关键词"待办"全局搜索 |

---

## 配置修改

编辑 `config.py` 可以调整所有参数：

```python
# 切换 AI 模型
DEEPSEEK_MODEL = "deepseek-chat"       # 普通版
DEEPSEEK_MODEL = "deepseek-reasoner"   # 推理版（R1）

# 调整断句灵敏度（越小越容易断句）
STT_RULE1_MIN_TRAILING_SILENCE = 2.4

# 对话上下文轮数
MEMORY_CONTEXT_TURNS = 10
```
