# AiClip

AiClip 是一个基于大模型的命令行视频剪辑助手。它把字幕转写、字幕生成、视频裁剪、拼接、缩放、裁切和烧录字幕等能力封装成工具，由 LLM 统一调度完成多步骤任务。

## 主要功能

- 音频/视频转写
- 生成 SRT / VTT 字幕
- 将字幕烧录到视频中
- 视频截取、删除片段、拼接、缩放、裁切
- 文件读取、编辑、写入、搜索、目录浏览
- 通过 `bash_command` 执行临时命令

## 项目结构

- `main.py`：程序入口
- `src/cli/`：命令行交互、状态和渲染
- `src/llm/`：模型配置和工具注册
- `resources/docs/`：每个工具的说明文档

## 环境要求

- Python 3.10+
- 已安装并可用的 FFmpeg 相关依赖
- OpenAI API Key

## 安装

```bash
pip install -r requirements.txt
```

建议在虚拟环境中安装依赖：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，并填写真实配置：

```env
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0
```

其中：

- `OPENAI_API_KEY` 必填
- `OPENAI_MODEL` 控制使用的模型
- `OPENAI_TEMPERATURE` 默认建议保持 `0`
- `AICLIP_WORKSPACE` 控制项目工作区根目录，默认是 `~/.aiclip`
- `AICLIP_VISION_API_KEY` 或 `DASHSCOPE_API_KEY` 用于视觉分析能力
- `AICLIP_VISION_MODEL` 控制视觉模型，默认值为 `qwen3-vl-plus`
- `AICLIP_VISION_API_BASE` / `AICLIP_DASHSCOPE_BASE` 可覆盖视觉接口地址
- `AICLIP_VISION_TIMEOUT`、`AICLIP_VISION_MAX_RETRIES`、`AICLIP_VISION_RETRY_BASE` 控制视觉请求超时与重试
- `PEXELS_API_KEY`、`PIXABAY_API_KEY`、`FREESOUND_API_KEY` 用于联网素材搜索
- `NET_ASSET_CACHE_DIR` 控制联网素材缓存目录

## 启动

```bash
python main.py
python main.py --help
python main.py --command "/help"
python main.py --skill project_core
```

启动后会进入交互式 CLI。`--help` 会先显示启动参数帮助，然后退出。`--command` 会直接执行一条指令后退出，不进入交互式提示符。
`--skill` 可在启动时锁定技能集。

## CLI 命令

- `/help`：查看帮助
- `/exit`：退出
- `/quit`：退出
- `/clear`：清空对话历史
- `/verbose`：切换详细输出
- `/status`：查看当前状态
- `/plan`：开启 LLM 规划模式
- `/skills`：查看可用技能
- `/skill <name>`：切换并锁定技能
- `/auto_skill`：恢复自动技能路由

## 默认工具

工具会自动注册给代理使用，常见能力包括：

- `transcribe_audio`
- `create_project_from_media`
- `load_project`
- `save_project`
- `set_project_metadata`
- `trim_project_clip`
- `set_project_clip_speed`
- `add_project_asset`
- `add_project_subtitle`
- `update_project_subtitle`
- `remove_project_subtitle`
- `batch_update_project_subtitles`
- `prepare_project_render`
- `plan_project_export`
- `render_project`

## 常见问题

- 启动时提示缺少 `OPENAI_API_KEY`：复制 `.env.example` 为 `.env`，并填写 `OPENAI_API_KEY`。
- 视觉分析报缺少 API Key：请单独设置 `AICLIP_VISION_API_KEY` 或 `DASHSCOPE_API_KEY`。
- 素材路径报越界错误：项目资产路径必须位于 AiClip 工作区内，推荐使用 `download_net_asset` 返回的 `state.project_asset_path`。

## 使用示例

```text
请帮我把这个视频 00:00:10 到 00:01:20 截出来
```

```text
先生成字幕，再把字幕烧录到视频中
```

## 说明

- 项目数据默认保存在 `AICLIP_WORKSPACE` 指向的工作区中，典型结构包括 `project.json`、`media/`、`exports/` 和 `cache/`
- 导出产物应优先视为工作区内的受管输出，而不是默认写回源媒体同目录
- `bash_command` 适合作为补充能力，不建议优先依赖
- 工具的详细说明在 `resources/docs/` 下
