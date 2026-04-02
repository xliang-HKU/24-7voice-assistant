# 老年人语音助手

一个面向 `macOS` 桌面的极简语音陪伴助手。

当前版本的核心能力：

- 情感陪伴：接入豆包端到端实时语音，对话自然、连续
- 长期记忆：保存完整对话，并额外抽取人物事实记忆
- 自动提醒：听到提醒类语句后直接记下，不再二次确认
- 到点提醒：程序开着时，会由实时语音主动开口提醒
- 极简界面：只有开始/结束对话按钮，以及左上角待提醒事项框

## 当前流程

现在的提醒流程是：

1. 用户说“明天下午三点记得吃药”
2. 程序立即把提醒记到左上角列表
3. 后台再用 LLM 把提醒文案润色得更自然
4. 到点时由实时语音主动说出提醒

注意：

- 不再使用本地 TTS 做确认或到点播报
- 不再要求用户说“可以”来确认提醒
- 提醒只在程序保持开启时生效

## 运行环境

- `macOS`
- `Python 3.10+`，推荐 `3.11`
- 首次启动时需要给应用授予麦克风权限

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 配置

程序运行时读取 `output/settings.json`。

建议不要直接编辑仓库里现成的 `output/settings.json` 去分发，而是按下面的方式生成自己的本地配置：

```bash
mkdir -p output
cp settings.example.json output/settings.json
```

然后填写你自己的密钥。

### 最小可用配置

默认主流程只依赖两部分：

- `realtime`：豆包 Dialog 实时语音
- `llm`：用于提醒文案润色，非必需，但强烈建议配置

`tts` 现在默认关闭，仅作为保留配置，不参与当前主流程。

### `realtime` 配置说明

```json
{
  "realtime": {
    "provider": "doubao_dialog",
    "enabled": true,
    "ws_url": "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
    "model": "AG-voice-chat-agent",
    "voice": "zh_female_vv_jupiter_bigtts",
    "app_id": "你的 APP ID",
    "app_key": "PlgvMymc7f3tQnJ6",
    "access_key": "你的 Access Token",
    "resource_id": "volc.speech.dialog",
    "bot_name": "豆包"
  }
}
```

说明：

- `ws_url` 固定为 `wss://openspeech.bytedance.com/api/v3/realtime/dialogue`
- `resource_id` 固定为 `volc.speech.dialog`
- `app_key` 目前填官方文档里的固定值 `PlgvMymc7f3tQnJ6`
- 控制台里的 `APP ID` 和 `Access Token` 要分别填到 `app_id`、`access_key`
- 当前默认请求 `pcm_s16le / 24000Hz` 输出音频

### `llm` 配置说明

`llm` 用来做提醒内容润色，例如把“15点吃药”整理成更自然的：

- 列表内容：`吃药`
- 播报内容：`提醒你，该吃药了。`

如果不配置 `llm`，程序仍可运行，只是提醒文案会更朴素。

## 启动

```bash
python main.py
```

## 使用方式

1. 点击 `开始对话`
2. 直接说话
3. 说完停顿一下，助手会自动继续接话
4. 如果说出类似“明天下午三点记得吃药”，提醒会自动进入左上角列表
5. 程序开着时，到点会由实时语音主动提醒

## 长期记忆

程序会保存两类记忆：

- 原始对话历史：`output/memory.json`
- 结构化人物事实：`output/profile_memory.json`

目前会优先抽取：

- 家庭关系
- 健康信息
- 近期安排
- 背景信息
- 居住信息

这些信息会在后续会话中重新注入，让助手更像“真的记得你”。

## 目录结构

```text
24-7voice-assistant/
├── main.py
├── config.py
├── requirements.txt
├── settings.example.json
├── core/
│   ├── ai.py
│   ├── memory.py
│   ├── realtime_voice.py
│   ├── reminders.py
│   ├── settings.py
│   ├── stt.py
│   └── tts.py
├── ui/
│   └── main_window.py
└── output/
    ├── settings.json
    ├── memory.json
    ├── profile_memory.json
    ├── reminders.json
    └── tts_cache/
```

其中：

- `settings.example.json` 是分发用模板
- `output/` 是运行期目录，会保存你的本地配置和数据
- `core/stt.py` 是旧版本地识别代码，当前默认流程不使用

## 依赖说明

当前默认流程实际需要的 Python 依赖只有：

- `PySide6`
- `sounddevice`
- `numpy`
- `openai`
- `websockets`

`sherpa-onnx` 已不再是当前默认流程的安装前置条件。

## 分发建议

如果你准备把项目发给别人看，建议这样处理：

1. 提交代码时不要带上你自己的 `output/settings.json`
2. 不要带上 `output/memory.json`、`output/profile_memory.json`、`output/reminders.json`
3. 让对方从 `settings.example.json` 复制出自己的 `output/settings.json`

我这次没有替你清空当前本地 `output/settings.json`，是为了避免把你现在能正常使用的配置破坏掉。

## 已知说明

- 当前项目面向 `macOS`
- 提醒只在程序保持开启时生效
- 到点提醒现在走实时语音，不走本地 TTS
- 如果实时会话当时没开，到点提醒会先自动拉起实时会话，再播报
- 首次创建提醒时会先秒记下，再后台润色，所以提醒文案可能会轻微更新一次

## 参考文档

- 豆包实时语音 Dialog API：https://www.volcengine.com/docs/6561/1594356?lang=zh
- 豆包实时语音 iOS SDK 文档：https://www.volcengine.com/docs/6561/1597646
- 火山语音相关 WebSocket 文档：https://www.volcengine.com/docs/6561/1756902
