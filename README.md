# AiClip

AiClip 是一个基于大模型的命令行视频剪辑助手。它把字幕转写、字幕生成、视频裁剪、拼接、缩放、裁切和烧录字幕等能力封装成工具，由 LLM 统一调度完成多步骤任务。

## 主要功能

- 音频/视频转写
- 生成 SRT / VTT 字幕
- 将字幕烧录到视频中
- 视频截取、删除片段、拼接、缩放、裁切
- 文件读取、编辑、写入、搜索、目录浏览
- 通过 `bash_command` 执行临时命令
- 使用 `/coordinate` 进入协同器模式，处理更复杂的多阶段任务

## 项目结构

- `main.py`：程序入口
- `src/cli/`：命令行交互、状态和渲染
- `src/coordinator/`：任务协同、Worker 管理、通知和校验
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

## 启动

```bash
python main.py
```

启动后会进入交互式 CLI。

## CLI 命令

- `/help`：查看帮助
- `/exit`：退出
- `/quit`：退出
- `/clear`：清空对话历史
- `/verbose`：切换详细输出
- `/status`：查看当前状态
- `/coordinate <任务描述>`：使用协同器执行复杂任务
- `/workers`：查看当前 Worker 状态

## 默认工具

工具会自动注册给代理使用，常见能力包括：

- `transcribe_audio`
- `generate_subtitle_srt`
- `generate_subtitle_vtt`
- `generate_subtitle`
- `get_video_info`
- `trim_video`
- `cutout_video`
- `concatenate_videos`
- `resize_video`
- `crop_video`
- `add_subtitles`
- `read_file`
- `edit_file`
- `write_file`
- `grep_file`
- `list_directory`
- `bash_command`

## 使用示例

```text
请帮我把这个视频 00:00:10 到 00:01:20 截出来
```

```text
先生成字幕，再把字幕烧录到视频中
```

```text
/coordinate 帮我分析当前目录下的视频，生成字幕并输出一个可发布版本
```

## 说明

- 默认输出文件通常会在源文件旁边生成，并带有操作后缀，比如 `_trimmed`、`_cutout`、`_concat`、`_resized`、`_cropped`、`_subbed`
- `bash_command` 适合作为补充能力，不建议优先依赖
- 工具的详细说明在 `resources/docs/` 下

