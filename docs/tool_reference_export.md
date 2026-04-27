# AiClip 工具导出文档

- 导出时间: 2026-04-23T15:01:00+08:00
- 工具来源: src/llm/tools/tool_setup_impl/tool_setup_catalog_tools.py
- 当前可调用工具数: 43
- doc-only 合约数: 1

## 说明

本文档按当前注册表导出代理工具全集，包含用途、输入输出、效果、实现边界和典型边界情况。
效果、边界和边界情况中的共性结论，来自当前代码实现与资源文档的合并归纳。

## 共性边界

- 项目类工具依赖统一项目校验：project id/name 必填，clip/subtitle 时间范围合法，引用关系必须指向已存在对象。
- 字幕 span 模式下，cue.text 必须与 span 文本拼接一致，否则后续渲染校验可能失败。
- 工作区路径受 AICLIP_WORKSPACE 限制，项目内相对路径解析后不得越界。
- render_project 属于最终导出工具，推荐在 prepare_project_render 或等价校验通过后执行。
- 联网素材和视觉分析能力都依赖外部配置，不满足 API Key 或 SDK 前置条件时会直接返回错误结果。

## 工具索引

| 名称 | 标题 | 来源 | 类别 | 注册状态 | 文档文件 |
| --- | --- | --- | --- | --- | --- |
| project_core_contract | Project Core Contract | project | doc_only | doc-only | project_core_contract.txt |
| create_project_from_media | Project Bootstrap Tool | project | mutation | registered | create_project_from_media.txt |
| transcribe_audio | Project Subtitle Transcription Tool | project | mutation | registered | transcribe_audio.txt |
| remove_project_silence | Project Silence Removal Tool | project | mutation | registered | remove_project_silence.txt |
| load_project | Project Loader Tool | project | read_or_analyze | registered | load_project.txt |
| get_project_summary | Project Summary Tool | project | read_or_analyze | registered | get_project_summary.txt |
| search_project_subtitles | Project Subtitle Search Tool | project | read_or_analyze | registered | search_project_subtitles.txt |
| list_project_clips | Project Clip List Tool | project | read_or_analyze | registered | list_project_clips.txt |
| save_project | Project Saver Tool | project | mutation | registered | save_project.txt |
| set_project_metadata | Project Metadata Tool | project | mutation | registered | set_project_metadata.txt |
| trim_project_clip | Project Clip Trim Tool | project | mutation | registered | trim_project_clip.txt |
| set_project_clip_speed | Project Clip Speed Tool | project | mutation | registered | set_project_clip_speed.txt |
| set_project_clip_transform | Project Clip Transform Tool | project | mutation | registered | set_project_clip_transform.txt |
| add_project_asset | Project Asset Tool | project | mutation | registered | add_project_asset.txt |
| add_project_clip | Project Clip Insert Tool | project | mutation | registered | add_project_clip.txt |
| generate_animejs_overlay_asset | Anime.js Overlay Asset Tool | project | mutation | registered | generate_animejs_overlay_asset.txt |
| apply_overlay_to_screen | Overlay Screen Placement Tool | project | mutation | registered | apply_overlay_to_screen.txt |
| add_project_subtitle | Project Subtitle Add Tool | project | mutation | registered | add_project_subtitle.txt |
| update_project_subtitle | Project Subtitle Update Tool | project | mutation | registered | update_project_subtitle.txt |
| batch_update_project_subtitles | Project Subtitle Batch Styling Tool | project | mutation | registered | batch_update_project_subtitles.txt |
| add_project_subtitle_span | Project Subtitle Span Add Tool | project | mutation | registered | add_project_subtitle_span.txt |
| update_project_subtitle_span | Project Subtitle Span Update Tool | project | mutation | registered | update_project_subtitle_span.txt |
| remove_project_subtitle_span | Project Subtitle Span Remove Tool | project | mutation | registered | remove_project_subtitle_span.txt |
| remove_project_subtitle | Project Subtitle Remove Tool | project | mutation | registered | remove_project_subtitle.txt |
| prepare_project_render | Project Render Planning Tool | project | planning | registered | prepare_project_render.txt |
| add_project_audio_stem | Project Audio Stem Add Tool | project | mutation | registered | add_project_audio_stem.txt |
| update_project_audio_stem | Project Audio Stem Update Tool | project | mutation | registered | update_project_audio_stem.txt |
| remove_project_audio_stem | Project Audio Stem Remove Tool | project | mutation | registered | remove_project_audio_stem.txt |
| set_project_export_preset | Project Export Preset Tool | project | mutation | registered | set_project_export_preset.txt |
| plan_project_export | Project Export Planning Tool | project | planning | registered | plan_project_export.txt |
| render_project | Project Render Tool | project | render | registered | render_project.txt |
| add_project_effect | Project Effect Add Tool | project | mutation | registered | add_project_effect.txt |
| update_project_effect | Project Effect Update Tool | project | mutation | registered | update_project_effect.txt |
| remove_project_effect | Project Effect Remove Tool | project | mutation | registered | remove_project_effect.txt |
| set_project_subtitle_effect | Project Subtitle Effect Tool | project | mutation | registered | set_project_subtitle_effect.txt |
| remove_project_subtitle_effect | Project Subtitle Effect Remove Tool | project | mutation | registered | remove_project_subtitle_effect.txt |
| add_project_comment | Project Comment Add Tool | project | mutation | registered | add_project_comment.txt |
| update_project_comment | Project Comment Update Tool | project | mutation | registered | update_project_comment.txt |
| remove_project_comment | Project Comment Remove Tool | project | mutation | registered | remove_project_comment.txt |
| lock_project_comment | Project Comment Lock Tool | project | mutation | registered | lock_project_comment.txt |
| detect_faces | Face Detection Tool | project | read_or_analyze | registered | detect_faces.txt |
| vision_analyze_media | Vision Analyze Media Tool | vision | analysis | registered | vision_analyze_media.txt |
| search_net_asset | Network Asset Search Tool | net_asset | network | registered | search_net_asset.txt |
| download_net_asset | Network Asset Download Tool | net_asset | network | registered | download_net_asset.txt |

## 逐项说明

### Project Core Contract (project_core_contract)

- 来源: project
- 类别: doc_only
- 注册状态: 仅文档
- 说明文件: resources/docs/project_core_contract.txt

#### 使用说明

```text
Project Core Contract

Purpose
- Keep agent behavior inside the project file model.
- Use tool output, not chat text, to decide the next step.

Decision order
1. Read `decision`.
2. Check `validation` and `render_state`.
3. Use `state` and `next_actions`.
4. Inspect `payload` only when you need the full project snapshot.

Output rules
- `message` and `summary` are display text only.
- Prefer `code`, `status`, `state`, `render_state`, `validation`, and `next_actions`.
- If `next_actions` contains a concrete follow-up inside the active skill, continue instead of ending the task early.
- If `decision.render_state.ready` is false, do not render.
- If `decision.render_state.ready` is true and the request is to finish or optimize a video, continue through render preparation and final render when possible.
- If the request needs subtitles and no subtitle source exists, use `transcribe_audio` first.
- If the request is to cut silence, use `remove_project_silence` after subtitle cues exist.
- If the request is about better short-video effect, hook strength, Douyin pacing, or stronger retention, inspect `payload.short_video` from `get_project_summary`.

Project scope
- The current core edits timeline, assets, subtitles, audio stems, effects, comments, metadata, and export presets.
- Subtitle spans can be edited separately for local color and style changes.
- Media bootstrap creates a project from raw media; it does not magically create a subtitle transcript.
```

#### 效果

- 只提供约束说明，不会被注册为可调用工具。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 当前实现未发现该工具独有的额外边界情况，主要遵循所属类别的共性约束。

### Project Bootstrap Tool (create_project_from_media)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/create_project_from_media.txt

#### 使用说明

```text
create_project_from_media

Purpose
- Bootstrap a project from a raw video or audio file.

Inputs
- `media_path`: source media file.
- `project_path`: optional output project path.
- `project_name`: optional name.
- `project_id`: optional id.
- `asset_id`: optional asset id.
- `track_id`: optional initial track id.
- `clip_id`: optional initial clip id.

Returns
- `decision`
- `payload`
- `render_state`
- `state` with `project_path`, `media_path`, `subtitle_source_present`, `audio_track_present`, `asset_count`, `track_count`, `subtitle_count`

Notes
- This tool creates the project shell only.
- It does not generate subtitles or a transcript.
- If the request depends on subtitles and none exist yet, keep the result at project scope and report that gap with `decision`.
- If the source video has audio, the project should include both video and audio timeline tracks.
```

#### 效果

- 创建项目工作区与项目壳文件。
- 必要时会把源媒体导入受管工作区。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。
- 该工具只建立项目壳，不会自动转写字幕。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Subtitle Transcription Tool (transcribe_audio)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/transcribe_audio.txt

#### 使用说明

```text
transcribe_audio

Purpose
- Convert source audio into subtitle cues stored in the project.

Inputs
- `project_path`
- `language`: optional language code
- `audio_path`: optional override source path
- `model_size`: optional Whisper model size, default `tiny`
- `output_path`: optional project save path
- `replace_existing`: optional, default `true`

Returns
- `decision`
- `payload`
- `render_state`
- `state` with `subtitle_source_present` and `subtitle_count`

Notes
- Use this when the project has no subtitle source yet.
- This is the core fallback for subtitle-driven edits.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Silence Removal Tool (remove_project_silence)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/remove_project_silence.txt

#### 使用说明

```text
remove_project_silence

Purpose
- Remove gaps between subtitle cues and rebuild the main timeline track.

Inputs
- `project_path`
- `track_id`: optional
- `output_path`: optional
- `padding`: optional seconds added around each cue

Returns
- `decision`
- `payload`
- `render_state`
- `state` with `segment_count`, `timeline_duration`, `subtitle_count`

Notes
- Requires subtitle cues.
- Use after transcription when the goal is to cut silent sections.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Loader Tool (load_project)

- 来源: project
- 类别: read_or_analyze
- 注册状态: 可调用
- 说明文件: resources/docs/load_project.txt

#### 使用说明

```text
load_project

Purpose
- Load a project from JSON or XML.

Inputs
- `project_path`: path to `project.json` or `project.xml`.

Returns
- `decision`
- `payload`
- `validation`
- `render_state`
- `state` with `project_path`, `subtitle_source_present`, `audio_track_present`, `asset_count`, `track_count`, `subtitle_count`, `audio_stem_count`, `effect_count`, `comment_count`

Notes
- Use this before any edit that depends on the existing project structure.
- Inspect `subtitle_source_present` and `subtitle_count` before trying subtitle edits.
- If `subtitle_source_present` is false, call `transcribe_audio` instead of asking for a subtitle file.
- If `audio_track_present` is false on a video project, rebuild the project from media.
```

#### 效果

- 读取、搜索或分析现有项目/媒体状态。
- 正常情况下不会改写项目文件。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Summary Tool (get_project_summary)

- 来源: project
- 类别: read_or_analyze
- 注册状态: 可调用
- 说明文件: resources/docs/get_project_summary.txt

#### 使用说明

```text
get_project_summary

Purpose
- Return a compact summary of the project without dumping the full project payload.

Inputs
- `project_path`

Returns
- `decision`
- `validation`
- `render_state`
- `payload` with timeline duration, fps, tracks, source media path, entity counts, and `short_video` editing signals

Notes
- Use this when you need a quick project overview before deciding which edit tool to call.
- For short-video optimization, inspect `payload.short_video` before large pacing or subtitle changes.
```

#### 效果

- 读取、搜索或分析现有项目/媒体状态。
- 正常情况下不会改写项目文件。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Subtitle Search Tool (search_project_subtitles)

- 来源: project
- 类别: read_or_analyze
- 注册状态: 可调用
- 说明文件: resources/docs/search_project_subtitles.txt

#### 使用说明

```text
search_project_subtitles

Purpose
- Search subtitle cues by text, speaker, or language.

Inputs
- `project_path`
- `query`: optional substring match, case-insensitive
- `speaker`: optional exact speaker filter
- `language`: optional exact language filter
- `limit`: optional, default `50`

Returns
- `decision`
- `validation`
- `render_state`
- `payload.matches`

Notes
- Use this instead of `load_project` when you need to find subtitles such as all cues containing a word or phrase.
```

#### 效果

- 读取、搜索或分析现有项目/媒体状态。
- 正常情况下不会改写项目文件。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Clip List Tool (list_project_clips)

- 来源: project
- 类别: read_or_analyze
- 注册状态: 可调用
- 说明文件: resources/docs/list_project_clips.txt

#### 使用说明

```text
list_project_clips

Purpose
- List timeline clips with optional filters.

Inputs
- `project_path`
- `track_id`: optional
- `track_kind`: optional
- `asset_id`: optional
- `min_duration`: optional
- `max_duration`: optional
- `limit`: optional, default `100`

Returns
- `decision`
- `validation`
- `render_state`
- `payload.clips`

Notes
- Use this to answer questions like “which clips are longer than 5 seconds” or “what is on the overlay track”.
```

#### 效果

- 读取、搜索或分析现有项目/媒体状态。
- 正常情况下不会改写项目文件。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Saver Tool (save_project)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/save_project.txt

#### 使用说明

```text
save_project

Purpose
- Persist the current project to JSON or XML.

Inputs
- `project_path`: source project file.
- `output_path`: optional target path.
- `format`: optional `json` or `xml`.

Returns
- `decision`
- `payload`
- `validation`
- `render_state`
- `artifacts` with the saved project path
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Metadata Tool (set_project_metadata)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/set_project_metadata.txt

#### 使用说明

```text
set_project_metadata

Update project metadata in the project file.

When to use:
- Change project-level fields such as title, owner, notes, tags, or delivery metadata.

Inputs:
- `project_path`
- `metadata`: key/value map to merge
- `output_path`: optional save path

Returns:
- updated project snapshot
- `project_version`
- `render_state`

Notes:
- This does not touch timeline clips.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Clip Trim Tool (trim_project_clip)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/trim_project_clip.txt

#### 使用说明

```text
trim_project_clip

Purpose
- Trim a clip inside the project timeline.

Inputs
- `project_path`
- `clip_id`
- `start`
- `end`
- `track_id`: optional
- `output_path`: optional

Returns
- `decision`
- `changes`
- `validation`
- `render_state`

Notes
- Check `validation` before moving to render.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 时间区间、目标 clip 或 asset 不存在时，时间线更新会失败或产生不可渲染项目。

### Project Clip Speed Tool (set_project_clip_speed)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/set_project_clip_speed.txt

#### 使用说明

```text
set_project_clip_speed

Update clip speed inside a project file.

When to use:
- Change playback speed without changing the source file.

Inputs:
- `project_path`
- `clip_id`
- `speed`
- `track_id`: optional
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
- `project_version`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 时间区间、目标 clip 或 asset 不存在时，时间线更新会失败或产生不可渲染项目。

### Project Clip Transform Tool (set_project_clip_transform)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/set_project_clip_transform.txt

#### 使用说明

```text
set_project_clip_transform

Purpose
- Update the visible placement and basic transform values of a clip in the timeline.

Inputs
- `project_path`
- `clip_id`
- `x`: optional
- `y`: optional
- `scale`: optional
- `opacity`: optional
- `track_id`: optional
- `transform`: optional object for additional keys
- `output_path`: optional

Returns
- updated project snapshot
- transform change details

Notes
- The current renderer actively applies `x`, `y`, `scale`, and `opacity`.
- Extra transform keys can still be stored for future render upgrades.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Asset Tool (add_project_asset)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/add_project_asset.txt

#### 使用说明

```text
add_project_asset

Add a media asset into a project file.

When to use:
- Register a new source file in the project.

Inputs:
- `project_path`
- `asset_id`
- `asset_path`
- `media_type`
- `output_path`: optional

Returns:
- updated project snapshot
- asset count in `state`
- `render_state`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Clip Insert Tool (add_project_clip)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/add_project_clip.txt

#### 使用说明

```text
add_project_clip

Purpose
- Insert a clip that references an existing project asset onto a timeline track.

Inputs
- `project_path`
- `clip_id`
- `asset_id`
- `start`
- `end`
- `track_id`
- `source_in`: optional
- `source_out`: optional
- `speed`: optional
- `track_kind`: optional, default `video`
- `track_name`: optional
- `transform`: optional, supports keys like `x`, `y`, `scale`, `opacity`
- `insert_index`: optional
- `output_path`: optional

Returns
- `decision`
- `changes`
- `validation`
- `render_state`

Notes
- The referenced `asset_id` must already exist in the project.
- Use this after `add_project_asset` to place downloaded or local media on the timeline.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 时间区间、目标 clip 或 asset 不存在时，时间线更新会失败或产生不可渲染项目。

### Anime.js Overlay Asset Tool (generate_animejs_overlay_asset)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/generate_animejs_overlay_asset.txt

#### 使用说明

```text
generate_animejs_overlay_asset

Purpose
- Store Anime.js source as a workspace bundle and register a transparent overlay asset in the project.

Inputs
- `project_path`
- `asset_id`
- `code`
- `width`
- `height`
- `duration`
- `fps`
- `label`: optional
- `output_path`: optional

Returns
- updated project snapshot
- generated asset metadata
- bundle artifact paths for html, script, manifest, and preview image

Notes
- MVP registers a transparent PNG preview asset and stores the Anime.js bundle for later rendering.
- Use `apply_overlay_to_screen` to place the generated overlay on the timeline.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Overlay Screen Placement Tool (apply_overlay_to_screen)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/apply_overlay_to_screen.txt

#### 使用说明

```text
apply_overlay_to_screen

Purpose
- Add a transparent overlay asset back onto the screen area of a target clip.

Inputs
- `project_path`
- `asset_id`
- `target_clip_id`
- `overlay_clip_id`
- `x`
- `y`
- `width`: optional
- `height`: optional
- `start`: optional
- `end`: optional
- `opacity`: optional
- `track_id`: optional
- `track_name`: optional
- `output_path`: optional

Returns
- updated project snapshot
- overlay clip insertion result

Notes
- The clip is written to a dedicated overlay track by default.
- The clip transform stores the screen placement and opacity.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 时间区间、目标 clip 或 asset 不存在时，时间线更新会失败或产生不可渲染项目。

### Project Subtitle Add Tool (add_project_subtitle)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/add_project_subtitle.txt

#### 使用说明

```text
add_project_subtitle

Purpose
- Add a subtitle cue to the project.

Inputs
- `project_path`
- `subtitle_id`
- `start`
- `end`
- `text`
- `spans`: optional list of rich-text spans with `id`, `text`, `color`, `bold`, `italic`, `underline`
- `track_id`: optional
- `speaker`: optional
- `language`: optional
- `position`: optional `top`, `middle`, or `bottom`
- `margin_top`: optional top edge margin in pixels
- `margin_bottom`: optional bottom edge margin in pixels
- `margin_left`: optional left edge margin in pixels
- `margin_right`: optional right edge margin in pixels
- `offset_y`: optional vertical pixel adjustment
- `output_path`: optional

Returns
- `decision`
- `changes`
- `validation`
- `render_state`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 字幕文本与 spans 内容不一致时，后续 prepare_project_render 或 render_project 可能校验失败。

### Project Subtitle Update Tool (update_project_subtitle)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/update_project_subtitle.txt

#### 使用说明

```text
update_project_subtitle

Purpose
- Update an existing subtitle cue.

Inputs
- `project_path`
- `subtitle_id`
- `start`: optional
- `end`: optional
- `text`: optional
- `spans`: optional list of rich-text spans with `id`, `text`, `color`, `bold`, `italic`, `underline`
- `speaker`: optional
- `language`: optional
- `position`: optional `top`, `middle`, `bottom`, or `below_faces` (to automatically avoid covering detected faces)
- `margin_top`: optional top edge margin in pixels
- `margin_bottom`: optional bottom edge margin in pixels
- `margin_left`: optional left edge margin in pixels
- `margin_right`: optional right edge margin in pixels
- `offset_y`: optional vertical pixel adjustment
- `output_path`: optional

Returns
- `decision`
- `changes`
- `validation`
- `render_state`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 字幕文本与 spans 内容不一致时，后续 prepare_project_render 或 render_project 可能校验失败。

### Project Subtitle Batch Styling Tool (batch_update_project_subtitles)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/batch_update_project_subtitles.txt

#### 使用说明

```text
batch_update_project_subtitles

Purpose
- Update many subtitle cues in one call.
- Use this when you need to reposition, recolor, highlight, or add multiple effects across several subtitles.
- Prefer this tool over repeated subtitle/span/effect calls when styling 3 or more subtitles.

Inputs
- `project_path`
- `entries`: list of objects. Each object supports:
  - `subtitle_id`: required
  - `start`, `end`, `text`, `speaker`, `language`: optional cue updates
  - `position`: optional `top`, `middle`, `bottom`, or `below_faces`
  - `margin_top`, `margin_bottom`, `margin_left`, `margin_right`, `offset_y`: optional layout fields
  - `spans`: optional list of rich-text spans with `id`, `text`, `color`, `bold`, `italic`, `underline`
  - `effects`: optional list of effect objects
    - `kind`: required
    - `parameters`: optional dict
    - `replace`: optional bool, default true
    - `span_id`: optional target one span instead of the full cue
- `output_path`: optional

Returns
- `decision`
- `changes`
- `validation`
- `render_state`
- `state.updated_subtitle_ids`
- `state.updated_subtitle_count`
- `state.applied_effect_count`

Notes
- This tool applies all requested cue updates and effects under one project lock and one save.
- It is the preferred path for bulk subtitle styling because it keeps tool-call count low and avoids oversized agent request chains.
- You can combine `position=below_faces` with colored spans and stacked effects in the same entry.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 字幕文本与 spans 内容不一致时，后续 prepare_project_render 或 render_project 可能校验失败。

### Project Subtitle Span Add Tool (add_project_subtitle_span)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/add_project_subtitle_span.txt

#### 使用说明

```text
add_project_subtitle_span

Purpose
- Add one styled span into a subtitle cue.

Inputs
- `project_path`
- `subtitle_id`
- `span_id`: optional
- `text`
- `color`: optional
- `bold`: optional
- `italic`: optional
- `underline`: optional
- `index`: optional insert position
- `output_path`: optional

Returns
- `decision`
- `changes`
- `render_state`

Notes
- Use this for a few highlighted words inside one subtitle line.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 字幕文本与 spans 内容不一致时，后续 prepare_project_render 或 render_project 可能校验失败。

### Project Subtitle Span Update Tool (update_project_subtitle_span)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/update_project_subtitle_span.txt

#### 使用说明

```text
update_project_subtitle_span

Purpose
- Update the style or text of one subtitle span.

Inputs
- `project_path`
- `subtitle_id`
- `span_id`
- `text`: optional
- `color`: optional
- `bold`: optional
- `italic`: optional
- `underline`: optional
- `output_path`: optional

Returns
- `decision`
- `changes`
- `render_state`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 字幕文本与 spans 内容不一致时，后续 prepare_project_render 或 render_project 可能校验失败。

### Project Subtitle Span Remove Tool (remove_project_subtitle_span)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/remove_project_subtitle_span.txt

#### 使用说明

```text
remove_project_subtitle_span

Purpose
- Remove one subtitle span from a cue.

Inputs
- `project_path`
- `subtitle_id`
- `span_id`
- `output_path`: optional

Returns
- `decision`
- `changes`
- `render_state`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Subtitle Remove Tool (remove_project_subtitle)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/remove_project_subtitle.txt

#### 使用说明

```text
remove_project_subtitle

Purpose
- Remove a subtitle cue from the project.

Inputs
- `project_path`
- `subtitle_id`
- `output_path`: optional

Returns
- `decision`
- `changes`
- `render_state`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Render Planning Tool (prepare_project_render)

- 来源: project
- 类别: planning
- 注册状态: 可调用
- 说明文件: resources/docs/prepare_project_render.txt

#### 使用说明

```text
prepare_project_render

Purpose
- Validate the project before preview or final render.

Inputs
- `project_path`
- `preview_path`: optional
- `final_path`: optional

Returns
- `decision`
- `validation`
- `render_state`
- `next_actions`

Notes
- Render only when `render_state.ready` is true.
- Use `validation.errors` and `render_state.blockers` to decide what to fix.
```

#### 效果

- 返回规划或校验结果，不直接生成最终媒体文件。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Audio Stem Add Tool (add_project_audio_stem)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/add_project_audio_stem.txt

#### 使用说明

```text
add_project_audio_stem

Add an audio stem reference to a project file.

When to use:
- Register a dialogue, music, or effects stem in the project.

Inputs:
- `project_path`
- `stem_id`
- `role`
- `asset_path`
- `track_id`: optional
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Audio Stem Update Tool (update_project_audio_stem)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/update_project_audio_stem.txt

#### 使用说明

```text
update_project_audio_stem

Update an audio stem in a project file.

When to use:
- Correct the role, source path, or track binding of a stem.

Inputs:
- `project_path`
- `stem_id`
- `role`: optional
- `path`: optional
- `track_id`: optional
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Audio Stem Remove Tool (remove_project_audio_stem)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/remove_project_audio_stem.txt

#### 使用说明

```text
remove_project_audio_stem

Remove an audio stem from a project file.

When to use:
- Remove an obsolete stem from the project.

Inputs:
- `project_path`
- `stem_id`
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Export Preset Tool (set_project_export_preset)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/set_project_export_preset.txt

#### 使用说明

```text
set_project_export_preset

Create or update an export preset in a project file.

When to use:
- Define delivery settings such as format, bitrate, codec, or container.

Inputs:
- `project_path`
- `preset_id`
- `name`
- `format`
- `settings`
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Export Planning Tool (plan_project_export)

- 来源: project
- 类别: planning
- 注册状态: 可调用
- 说明文件: resources/docs/plan_project_export.txt

#### 使用说明

```text
plan_project_export

Purpose
- Plan preview, final, and sidecar export paths.

Inputs
- `project_path`
- `preset_id`
- `output_dir`
- `base_name`: optional

Returns
- `decision`
- `render_state`
- planned preview path
- planned final path
- planned sidecar path
```

#### 效果

- 返回规划或校验结果，不直接生成最终媒体文件。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Render Tool (render_project)

- 来源: project
- 类别: render
- 注册状态: 可调用
- 说明文件: resources/docs/render_project.txt

#### 使用说明

```text
render_project

Purpose
- Render the project timeline into a final video file.

Inputs
- `project_path`
- `output_path`
- `track_id`: optional
- `font_path`: optional
- `font_size`: optional
- `subtitle_color`: optional

Returns
- `decision`
- `payload`
- `render_state`
- `artifacts` with the rendered video path

Notes
- This tool burns subtitle cues into the video output.
- Run only after the project validates and the timeline is ready.
- If `font_path` is omitted, the renderer searches `resources/fonts` for a Chinese font first.
```

#### 效果

- 读取项目时间线并产出最终视频文件。
- 如果包含字幕，会在导出阶段烧录到视频中。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。
- 仅在项目校验通过后才适合执行。
- 字体未显式指定时会尝试从 resources/fonts 自动选择中文字体。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。
- 项目存在重复 ID、坏引用或非法时间范围时，渲染前校验不会通过。

### Project Effect Add Tool (add_project_effect)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/add_project_effect.txt

#### 使用说明

```text
add_project_effect

Add a visual effect to a project file.

When to use:
- Attach a visual effect to a clip or track.

Inputs:
- `project_path`
- `effect_id`
- `target_id`
- `kind`
- `parameters`
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Effect Update Tool (update_project_effect)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/update_project_effect.txt

#### 使用说明

```text
update_project_effect

Update a visual effect in a project file.

When to use:
- Adjust effect target, kind, or parameters.

Inputs:
- `project_path`
- `effect_id`
- `target_id`: optional
- `kind`: optional
- `parameters`: optional
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Effect Remove Tool (remove_project_effect)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/remove_project_effect.txt

#### 使用说明

```text
remove_project_effect

Remove a visual effect from a project file.

When to use:
- Delete an effect from the project.

Inputs:
- `project_path`
- `effect_id`
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Subtitle Effect Tool (set_project_subtitle_effect)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/set_project_subtitle_effect.txt

#### 使用说明

```text
set_project_subtitle_effect

Purpose
- Attach a visual or animation effect to a subtitle cue.
- The effect is stored in the subtitle cue's `effects` list and applied automatically at render time.
- Calling this tool again with the same `kind` and `replace=true` (default) replaces the previous value.

Inputs
- `project_path`
- `subtitle_id`  – id of the subtitle cue to modify
- `kind`         – effect type (see Supported effects below)
- `parameters`   – optional dict of effect-specific parameters (see per-effect docs below)
- `span_id`      – optional span id within the cue to apply the effect to a specific portion of text
- `replace`      – optional bool (default true); when true, any existing effect with the same kind is replaced
- `output_path`  – optional

Supported effects
-----------------
Visual effects (applied to the subtitle still image at render time):

  outline
    color   – stroke color, default "black"
    width   – stroke width in pixels, default 2

  glow
    color   – glow color, default "white"
    radius  – gaussian blur radius in pixels, default 4

  background_box
    color   – fill color, default "black"
    opacity – 0-255 alpha, default 160
    padding – extra pixels around text rect, default 8

  gradient
    color_top    – top gradient color (e.g. "#ff0000")
    color_bottom – bottom gradient color (e.g. "#0000ff")
    direction    – "vertical" (default) or "horizontal"

Animation effects (applied to the clip timeline during render):

  fade_in
    duration – ramp-in duration in seconds, default 0.3

  fade_out
    duration – ramp-out duration in seconds, default 0.3

  slide_in
    direction – "bottom" (default) | "top" | "left" | "right"
    duration  – animation duration in seconds, default 0.3
    distance  – slide distance in pixels, default 40

  slide_out
    direction – "bottom" (default) | "top" | "left" | "right"
    duration  – animation duration in seconds, default 0.3
    distance  – slide distance in pixels, default 40

  typewriter
    chars_per_second – reveal speed, default 20
    Note: this effect generates one ImageClip per character step.
          It cannot be combined with slide_in / slide_out on the same cue.

  scale_in
    duration – zoom-in duration in seconds, default 0.3

Returns
- `decision`
- `changes`
- `validation`
- `render_state`

Notes
- Multiple effects of different kinds can coexist on one cue.
- Visual effects (outline, glow, background_box) can be stacked freely.
- Animation effects (fade_in, fade_out, slide_in, slide_out, scale_in) are composited during moviepy render.
- Per-cue `font_size` and `font_path` fields override the global render defaults.
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Subtitle Effect Remove Tool (remove_project_subtitle_effect)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/remove_project_subtitle_effect.txt

#### 使用说明

```text
remove_project_subtitle_effect

Purpose
- Remove one or all effects from a subtitle cue.

Inputs
- `project_path`
- `subtitle_id` – id of the subtitle cue
- `kind`        – optional; if provided only effects with this kind are removed; omit to clear all effects
- `span_id`     – optional; if provided, effects are removed from the specific span instead of the cue
- `output_path` – optional

Returns
- `decision`
- `changes`
- `render_state`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Comment Add Tool (add_project_comment)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/add_project_comment.txt

#### 使用说明

```text
add_project_comment

Add a collaboration comment to a project file.

When to use:
- Add a review note or collaboration comment.

Inputs:
- `project_path`
- `comment_id`
- `author`
- `text`
- `anchor`: optional
- `timecode`: optional
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Comment Update Tool (update_project_comment)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/update_project_comment.txt

#### 使用说明

```text
update_project_comment

Update an existing project comment.

When to use:
- Edit the text, anchor, timecode, or lock state of a comment.

Inputs:
- `project_path`
- `comment_id`
- `text`: optional
- `anchor`: optional
- `timecode`: optional
- `locked`: optional
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Comment Remove Tool (remove_project_comment)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/remove_project_comment.txt

#### 使用说明

```text
remove_project_comment

Remove a collaboration comment from a project file.

When to use:
- Delete a review note from the project.

Inputs:
- `project_path`
- `comment_id`
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Project Comment Lock Tool (lock_project_comment)

- 来源: project
- 类别: mutation
- 注册状态: 可调用
- 说明文件: resources/docs/lock_project_comment.txt

#### 使用说明

```text
lock_project_comment

Lock or unlock a collaboration comment.

When to use:
- Freeze a comment during review or allow edits again.

Inputs:
- `project_path`
- `comment_id`
- `locked`: `true` or `false`
- `output_path`: optional

Returns:
- updated project snapshot
- `changes`
```

#### 效果

- 会读取并改写项目文件中的对应结构。
- 结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Face Detection Tool (detect_faces)

- 来源: project
- 类别: read_or_analyze
- 注册状态: 可调用
- 说明文件: resources/docs/detect_faces.txt

#### 使用说明

```text
detect_faces

Purpose
- Detect human faces in a project's source video, save their positions in the project metadata, and return their pixel and normalized bounding-box positions for each sampled frame. The saved metadata can be used by subtitle rendering to automatically dodge faces (e.g. `position="below_faces"` in update_project_subtitle).

Inputs
- `project_path`: path to the project JSON file
- `media_path`: optional override video path (defaults to project source media)
- `timestamps`: optional list of specific timestamps (seconds) to sample; if omitted, frames are sampled every `sample_interval` seconds
- `sample_interval`: seconds between auto-sampled frames, default `1.0`
- `max_frames`: maximum number of frames to sample when auto-sampling, default `30`
- `scale_factor`: Haar cascade scaleFactor, default `1.1`
- `min_neighbors`: Haar cascade minNeighbors, default `5`
- `min_face_size`: minimum face size in pixels, default `30`

Returns
- `ok`: true on success
- `state` with:
  - `video_width`, `video_height`
  - `duration`, `fps`
  - `frames_sampled`
  - `frames_with_faces`
  - `total_faces_detected`
- `payload` with:
  - `video_width`, `video_height`, `duration`, `fps`
  - `total_faces_detected`
  - `frames_with_faces`
  - `frames`: list of frame objects, each containing:
    - `timestamp`: float seconds
    - `frame_index`: int
    - `face_count`: int
    - `faces`: list of face objects:
      - `x`, `y`, `w`, `h`: pixel bounding box (top-left origin)
      - `cx`, `cy`: center pixel coordinates
      - `norm_x`, `norm_y`, `norm_w`, `norm_h`: normalized coordinates (0.0–1.0)

Notes
- Requires `opencv-python` installed (`pip install opencv-python`).
- Uses OpenCV Haar cascade (`haarcascade_frontalface_default.xml`) bundled with OpenCV — no external model download needed.
- Use `timestamps` for targeted sampling (e.g. at subtitle cue midpoints).
- Use normalized coordinates (`norm_x`, `norm_y`, `norm_w`, `norm_h`) when computing subtitle placement relative to faces.
- Returns `faces.detected` code even when zero faces are found.
```

#### 效果

- 读取、搜索或分析现有项目/媒体状态。
- 正常情况下不会改写项目文件。

#### 边界

- 项目必须具备有效的 project id 与 name。
- 引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。
- 时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。
- 字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。
- asset_id、clip_id、subtitle_id 不能重复。
- 工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。

#### 边界情况

- 目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。
- 传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。

### Vision Analyze Media Tool (vision_analyze_media)

- 来源: vision
- 类别: analysis
- 注册状态: 可调用
- 说明文件: resources/docs/vision_analyze_media.txt

#### 使用说明

```text
vision_analyze_media

Purpose
- Analyze image or video content with an OpenAI-compatible vision model.

Inputs
- `media_path`: public URL or local file path
- `prompt`: analysis instruction; default asks for key events and timestamps
- `media_type`: optional `image` or `video`; inferred from path when omitted
- `model`: optional override model name
- `api_base`: optional override API base URL
- `api_key`: optional override API key
- `fps`: optional video frame sampling rate
- `temperature`: optional decoding temperature
- `max_tokens`: optional response token limit

Returns
- `ok`: true on success
- `content`: model analysis text (primary field to read)
- `message`: same as `content` (alias)
- `summary`: same as `content` (alias)
- `decision`: structured decision dict
- `state.model`, `state.media_type`, `state.usage`

Notes
- Default endpoint and model can be configured via env:
  - `AICLIP_VISION_API_BASE`
  - `AICLIP_VISION_API_KEY`
  - `AICLIP_VISION_MODEL`
- The `OPENAI_API_KEY` value is NOT used as a fallback for vision requests to avoid
  sending it to non-OpenAI endpoints. Set `AICLIP_VISION_API_KEY` explicitly.
```

#### 效果

- 对输入媒体执行视觉分析并返回文本结果与调用状态。
- 不会修改项目文件。

#### 边界

- 必须提供 AICLIP_VISION_API_KEY 或 DASHSCOPE_API_KEY。
- 本机未安装 dashscope SDK 时会直接返回安装提示。
- 视频分析会按 fps 抽帧，超时与重试次数受环境变量控制。

#### 边界情况

- 如果媒体类型推断错误，可显式传入 media_type 覆盖自动判断。

### Network Asset Search Tool (search_net_asset)

- 来源: net_asset
- 类别: network
- 注册状态: 可调用
- 说明文件: resources/docs/search_net_asset.txt

#### 使用说明

```text
search_net_asset

Search online stock libraries for free-to-use media assets.

When to use:
- User needs background video, B-roll, stock photos, or audio clips.
- AI decides to source supplementary media from the web.

Providers:
- pexels   — video + image (Pexels License, free commercial use)
- pixabay  — video + image (Pixabay License, free commercial use)
- freesound — audio SFX + music loops (Creative Commons)
- auto     — picks the best available provider for the requested media type

Inputs:
- `query`      — natural-language search (e.g. "sunset beach", "city crowd noise")
- `media_type` — "video" | "image" | "audio"  (default: "video")
- `provider`   — "pexels" | "pixabay" | "freesound" | "auto"  (default: "auto")
- `per_page`   — number of results 1–80  (default: 8)
- `orientation` — optional filter: "landscape" | "portrait" | "square"

Returns (on success):
- `ok`: true
- `provider_used`: which provider actually served results
- `total_returned`: count of results in this page
- `results[]`: list of asset objects, each with:
    - `id`           — provider-specific ID
    - `title`        — human-readable name / alt-text
    - `media_type`   — "video" | "image" | "audio"
    - `provider`     — source provider name
    - `preview_url`  — thumbnail / low-res URL (for display only)
    - `download_url` — direct file URL; pass to download_net_asset
    - `page_url`     — original page link (required for attribution)
    - `author`       — creator's name
    - `attribution`  — full attribution string (must be stored)
    - `license`      — license name
    - `duration`     — seconds (video/audio) or null
    - `width`/`height` — pixels (video/image) or null
    - `tags`         — list of keywords

Returns (on error):
- `ok`: false
- `error`: human-readable reason (e.g. missing API key)
- `results`: []

Workflow:
1. Call search_net_asset to get a list of candidates.
2. Present options to the user or pick the best match automatically.
3. Call download_net_asset with the chosen result's `download_url`.
4. Call add_project_asset with the returned `local_path` to register it.
5. Store `attribution` in the asset metadata for compliance.

Attribution requirement:
Pexels and Pixabay require that the author and source are credited whenever
their content is displayed.  Always copy the `attribution` field into the
asset's metadata when calling add_project_asset.
```

#### 效果

- 向外部素材站点发起检索请求并返回候选素材。
- 不会修改项目文件。

#### 边界

- 依赖对应 provider 的 API Key；未配置时会返回 no_provider 错误。
- auto provider 会按 media_type 选择可用服务，audio 优先 freesound，其它优先 pexels。
- per_page 会被限制在 1 到 80 之间。

#### 边界情况

- 即使请求成功，也可能返回 0 个结果；这种情况不是系统错误。

### Network Asset Download Tool (download_net_asset)

- 来源: net_asset
- 类别: network
- 注册状态: 可调用
- 说明文件: resources/docs/download_net_asset.txt

#### 使用说明

```text
download_net_asset

Download a stock media file to the local filesystem.

When to use:
- After search_net_asset has returned results and the desired asset is chosen.
- Before calling add_project_asset to register the file in a project.

Inputs:
- `download_url` — direct file URL from a search result's `download_url` field (required)
- `save_to`      — destination directory path; defaults to "tmp/" (optional)
- `filename`     — override the saved filename; inferred from URL if omitted (optional)
- `attribution`  — attribution text from the search result (optional, stored in return value)
- `project_path` — path to an existing project.json (optional). When provided, the tool
                   resolves the download destination relative to the project workspace and
                   returns a workspace-relative path in `state.project_asset_path`.
                   Pass this value as `asset_path` to add_project_asset so the asset path
                   is stored as a project-relative path (e.g. "media/clip.mp4") rather
                   than an absolute filesystem path.

Returns (on success):
- `ok`: true
- `local_path`: absolute path of the saved file
- `filename`: final filename on disk
- `attribution`: attribution text (pass this to add_project_asset metadata)
- `state.project_asset_path`: workspace-relative path (only present when `project_path` was given)

Returns (on error):
- `ok`: false
- `error`: human-readable reason (e.g. network timeout, disk full)

Workflow after download:
1. If `project_path` was given, use `state.project_asset_path` as the `asset_path` when
   calling add_project_asset (workspace-relative, e.g. "media/clip.mp4").
2. Otherwise use `local_path` as the `asset_path` (absolute path).
3. Include `attribution` in the asset metadata, e.g.:
     { "attribution": "<attribution text>", "source": "pexels" }

Notes:
- Files are saved once; repeated calls with the same URL skip re-downloading.
- Default destination is "tmp/" relative to the project working directory.
- Large video files may take several seconds to download.
```

#### 效果

- 下载远程素材到本地目录或项目工作区 media 目录。
- 下载完成后仍需单独调用 add_project_asset 才会进入项目。

#### 边界

- 下载失败会返回错误，不会自动补注册到项目。
- 如果提供 project_path，素材会优先落到对应项目工作区的 media 目录。

#### 边界情况

- 仅有 local_path 还不代表项目可用，必须进一步注册为项目资产。

## CLI 附录

### 内建命令

- /help: Show this help message
- /exit: Exit the CLI
- /quit: Exit the CLI
- /clear: Clear conversation history
- /verbose: Toggle verbose output
- /status: Show current session state
- /plan <request>: Preview an execution plan without running it
- /run: Execute the most recent previewed plan
- /execute: Execute the most recent previewed plan

### 技能命令

- /skills: List available skills
- /skill <name>: Switch and lock the active skill
- /auto_skill: Return to automatic skill routing

### CLI 中展示的核心工具别名

- create_project_from_media: Create a project from raw media
- transcribe_audio: Generate subtitle cues from audio
- remove_project_silence: Remove gaps between subtitle cues
- load_project: Load a JSON or XML project
- save_project: Save the current project
- set_project_metadata: Update project metadata
- trim_project_clip: Trim a timeline clip
- set_project_clip_speed: Change clip speed
- add_project_asset: Register a media asset
- add/update/remove_project_subtitle: Manage subtitle cues
- batch_update_project_subtitles: Bulk subtitle positioning, highlighting, and effects
- add/update/remove_project_subtitle_span: Manage highlighted words inside subtitles
- add/update/remove_project_audio_stem: Manage dialogue/music/effects stems
- add/update/remove_project_effect: Manage visual effects
- add/update/remove_project_comment: Manage collaboration comments
- lock_project_comment: Lock or unlock a comment
- set_project_export_preset: Define export settings
- prepare_project_render: Validate render readiness
- plan_project_export: Plan preview/final/sidecar outputs
- render_project: Render final video with subtitle burn-in
