from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cli.commands import BUILTIN_COMMANDS, CORE_TOOLS, SKILL_COMMANDS
from src.llm.tools.tool_setup_impl.tool_setup_catalog_tools import build_tool_specs


DOCS_DIR = REPO_ROOT / "resources" / "docs"
OUTPUT_MD = REPO_ROOT / "docs" / "tool_reference_export.md"
OUTPUT_JSON = REPO_ROOT / "docs" / "tool_reference_export.json"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def parse_doc_sections(text: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.splitlines()]
    title = ""
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        title = lines[index].strip()
        index += 1

    sections: dict[str, list[str]] = {}
    current = "body"
    sections[current] = []
    known_headers = {
        "Purpose",
        "Inputs",
        "Returns",
        "Notes",
        "When to use",
        "Providers",
        "Workflow",
        "Attribution requirement",
    }

    for line in lines[index:]:
        stripped = line.strip()
        if stripped in known_headers:
            current = stripped
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    normalized = {name: "\n".join(content).strip() for name, content in sections.items() if "\n".join(content).strip()}
    normalized["title"] = title
    return normalized


def classify_tool(name: str, source: str, register: bool) -> str:
    if not register:
        return "doc_only"
    if name in {"prepare_project_render", "plan_project_export"}:
        return "planning"
    if name == "render_project":
        return "render"
    if source == "net_asset":
        return "network"
    if source == "vision":
        return "analysis"
    if name in {"transcribe_audio", "save_project", "batch_update_project_subtitles", "lock_project_comment"}:
        return "mutation"
    if name.startswith(("get_", "list_", "search_", "load_", "detect_")):
        return "read_or_analyze"
    if name.startswith(("create_", "add_", "update_", "remove_", "set_", "trim_", "apply_", "generate_")):
        return "mutation"
    return "other"


def summarize_effects(spec_name: str, category: str) -> list[str]:
    if category == "doc_only":
        return ["只提供约束说明，不会被注册为可调用工具。"]
    if category == "render":
        return ["读取项目时间线并产出最终视频文件。", "如果包含字幕，会在导出阶段烧录到视频中。"]
    if category == "planning":
        return ["返回规划或校验结果，不直接生成最终媒体文件。"]
    if category == "network":
        if spec_name == "search_net_asset":
            return ["向外部素材站点发起检索请求并返回候选素材。", "不会修改项目文件。"]
        return ["下载远程素材到本地目录或项目工作区 media 目录。", "下载完成后仍需单独调用 add_project_asset 才会进入项目。"]
    if category == "analysis":
        return ["对输入媒体执行视觉分析并返回文本结果与调用状态。", "不会修改项目文件。"]
    if category == "read_or_analyze":
        return ["读取、搜索或分析现有项目/媒体状态。", "正常情况下不会改写项目文件。"]
    if spec_name == "create_project_from_media":
        return ["创建项目工作区与项目壳文件。", "必要时会把源媒体导入受管工作区。"]
    return ["会读取并改写项目文件中的对应结构。", "结果通常反映在 assets、timeline、subtitles、effects、comments、audio_stems 或 metadata 上。"]


def summarize_boundaries(spec_name: str, category: str, source: str) -> list[str]:
    boundaries: list[str] = []
    if source == "project":
        boundaries.extend(
            [
                "项目必须具备有效的 project id 与 name。",
                "引用关系必须闭合：clip.asset_id、effect.target_id、audio_stem.track_id 都必须指向现有对象。",
                "时间范围必须合法：clip/subtitle 的 end 必须大于 start，且 start 不能小于 0。",
                "字幕 spans 模式下，cue.text 必须与所有 span.text 拼接结果一致。",
                "asset_id、clip_id、subtitle_id 不能重复。",
                "工作区路径不能逃逸出 AICLIP_WORKSPACE 对应的项目根目录。",
            ]
        )
    if category == "render":
        boundaries.extend(
            [
                "仅在项目校验通过后才适合执行。",
                "字体未显式指定时会尝试从 resources/fonts 自动选择中文字体。",
            ]
        )
    if spec_name == "search_net_asset":
        boundaries.extend(
            [
                "依赖对应 provider 的 API Key；未配置时会返回 no_provider 错误。",
                "auto provider 会按 media_type 选择可用服务，audio 优先 freesound，其它优先 pexels。",
                "per_page 会被限制在 1 到 80 之间。",
            ]
        )
    if spec_name == "download_net_asset":
        boundaries.extend(
            [
                "下载失败会返回错误，不会自动补注册到项目。",
                "如果提供 project_path，素材会优先落到对应项目工作区的 media 目录。",
            ]
        )
    if spec_name == "vision_analyze_media":
        boundaries.extend(
            [
                "必须提供 AICLIP_VISION_API_KEY 或 DASHSCOPE_API_KEY。",
                "本机未安装 dashscope SDK 时会直接返回安装提示。",
                "视频分析会按 fps 抽帧，超时与重试次数受环境变量控制。",
            ]
        )
    if spec_name == "create_project_from_media":
        boundaries.append("该工具只建立项目壳，不会自动转写字幕。")
    return boundaries


def summarize_edge_cases(spec_name: str, category: str) -> list[str]:
    cases: list[str] = []
    if category in {"mutation", "planning", "render", "read_or_analyze"}:
        cases.extend(
            [
                "目标对象不存在时，通常会以校验错误、引用缺失或空结果形式返回。",
                "传入相对路径时，会相对项目工作区解析；越界路径会被拒绝。",
            ]
        )
    if spec_name in {"add_project_subtitle", "update_project_subtitle", "batch_update_project_subtitles", "add_project_subtitle_span", "update_project_subtitle_span"}:
        cases.append("字幕文本与 spans 内容不一致时，后续 prepare_project_render 或 render_project 可能校验失败。")
    if spec_name in {"add_project_clip", "trim_project_clip", "set_project_clip_speed", "apply_overlay_to_screen"}:
        cases.append("时间区间、目标 clip 或 asset 不存在时，时间线更新会失败或产生不可渲染项目。")
    if spec_name == "render_project":
        cases.append("项目存在重复 ID、坏引用或非法时间范围时，渲染前校验不会通过。")
    if spec_name == "search_net_asset":
        cases.append("即使请求成功，也可能返回 0 个结果；这种情况不是系统错误。")
    if spec_name == "download_net_asset":
        cases.append("仅有 local_path 还不代表项目可用，必须进一步注册为项目资产。")
    if spec_name == "vision_analyze_media":
        cases.append("如果媒体类型推断错误，可显式传入 media_type 覆盖自动判断。")
    return cases


def section_to_bullets(text: str) -> list[str]:
    items: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
            continue
        items.append(stripped)
    return items


def build_tool_record(spec: Any) -> dict[str, Any]:
    doc_text = read_text(DOCS_DIR / spec.doc_file)
    sections = parse_doc_sections(doc_text)
    category = classify_tool(spec.name, spec.source, spec.register)
    return {
        "name": spec.name,
        "title": spec.title,
        "description": spec.description,
        "source": spec.source,
        "doc_file": spec.doc_file,
        "registered": spec.register,
        "category": category,
        "doc": doc_text,
        "doc_sections": sections,
        "usage_summary": {
            "purpose": section_to_bullets(sections.get("Purpose", "")) or ([sections.get("body")] if sections.get("body") else []),
            "inputs": section_to_bullets(sections.get("Inputs", "")),
            "returns": section_to_bullets(sections.get("Returns", "")),
            "notes": section_to_bullets(sections.get("Notes", "")),
            "workflow": section_to_bullets(sections.get("Workflow", "")),
        },
        "effects": summarize_effects(spec.name, category),
        "boundaries": summarize_boundaries(spec.name, category, spec.source),
        "edge_cases": summarize_edge_cases(spec.name, category),
    }


def render_markdown(records: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    registered_count = sum(1 for item in records if item["registered"])
    doc_only_count = len(records) - registered_count

    lines.append("# AiClip 工具导出文档")
    lines.append("")
    lines.append(f"- 导出时间: {timestamp}")
    lines.append(f"- 工具来源: src/llm/tools/tool_setup_impl/tool_setup_catalog_tools.py")
    lines.append(f"- 当前可调用工具数: {registered_count}")
    lines.append(f"- doc-only 合约数: {doc_only_count}")
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("本文档按当前注册表导出代理工具全集，包含用途、输入输出、效果、实现边界和典型边界情况。")
    lines.append("效果、边界和边界情况中的共性结论，来自当前代码实现与资源文档的合并归纳。")
    lines.append("")
    lines.append("## 共性边界")
    lines.append("")
    shared = [
        "项目类工具依赖统一项目校验：project id/name 必填，clip/subtitle 时间范围合法，引用关系必须指向已存在对象。",
        "字幕 span 模式下，cue.text 必须与 span 文本拼接一致，否则后续渲染校验可能失败。",
        "工作区路径受 AICLIP_WORKSPACE 限制，项目内相对路径解析后不得越界。",
        "render_project 属于最终导出工具，推荐在 prepare_project_render 或等价校验通过后执行。",
        "联网素材和视觉分析能力都依赖外部配置，不满足 API Key 或 SDK 前置条件时会直接返回错误结果。",
    ]
    for item in shared:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 工具索引")
    lines.append("")
    lines.append("| 名称 | 标题 | 来源 | 类别 | 注册状态 | 文档文件 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in records:
        register_text = "registered" if item["registered"] else "doc-only"
        lines.append(f"| {item['name']} | {item['title']} | {item['source']} | {item['category']} | {register_text} | {item['doc_file']} |")
    lines.append("")

    lines.append("## 逐项说明")
    lines.append("")
    for item in records:
        lines.append(f"### {item['title']} ({item['name']})")
        lines.append("")
        lines.append(f"- 来源: {item['source']}")
        lines.append(f"- 类别: {item['category']}")
        lines.append(f"- 注册状态: {'可调用' if item['registered'] else '仅文档'}")
        lines.append(f"- 说明文件: resources/docs/{item['doc_file']}")
        lines.append("")
        lines.append("#### 使用说明")
        lines.append("")
        lines.append("```text")
        lines.append(item["doc"])
        lines.append("```")
        lines.append("")
        lines.append("#### 效果")
        lines.append("")
        for effect in item["effects"]:
            lines.append(f"- {effect}")
        lines.append("")
        lines.append("#### 边界")
        lines.append("")
        for boundary in item["boundaries"]:
            lines.append(f"- {boundary}")
        lines.append("")
        lines.append("#### 边界情况")
        lines.append("")
        if item["edge_cases"]:
            for case in item["edge_cases"]:
                lines.append(f"- {case}")
        else:
            lines.append("- 当前实现未发现该工具独有的额外边界情况，主要遵循所属类别的共性约束。")
        lines.append("")

    lines.append("## CLI 附录")
    lines.append("")
    lines.append("### 内建命令")
    lines.append("")
    for name, desc in BUILTIN_COMMANDS:
        lines.append(f"- {name}: {desc}")
    lines.append("")
    lines.append("### 技能命令")
    lines.append("")
    for name, desc in SKILL_COMMANDS:
        lines.append(f"- {name}: {desc}")
    lines.append("")
    lines.append("### CLI 中展示的核心工具别名")
    lines.append("")
    for name, desc in CORE_TOOLS:
        lines.append(f"- {name}: {desc}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_json_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "generated_at": timestamp,
        "source": "src/llm/tools/tool_setup_impl/tool_setup_catalog_tools.py",
        "tool_count": len(records),
        "registered_tool_count": sum(1 for item in records if item["registered"]),
        "doc_only_count": sum(1 for item in records if not item["registered"]),
        "tools": records,
        "cli": {
            "builtin_commands": [{"name": name, "description": desc} for name, desc in BUILTIN_COMMANDS],
            "skill_commands": [{"name": name, "description": desc} for name, desc in SKILL_COMMANDS],
            "core_tools": [{"name": name, "description": desc} for name, desc in CORE_TOOLS],
        },
    }


def main() -> int:
    specs = build_tool_specs()
    records = [build_tool_record(spec) for spec in specs]
    OUTPUT_MD.write_text(render_markdown(records), encoding="utf-8")
    OUTPUT_JSON.write_text(json.dumps(build_json_payload(records), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(records)} tools to {OUTPUT_MD.relative_to(REPO_ROOT)} and {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())