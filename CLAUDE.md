# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is
AiClip is a Python CLI for AI-assisted video editing. The top-level flow is:
1. `main.py` builds the LLM agent and CLI.
2. `src/cli/` handles interactive commands, streaming output, and session state.
3. `src/editor_core/` owns the project data model, persistence, validation, and render/edit commands.
4. `src/llm/tools/` exposes the agent-facing tools for project editing, media search/download, vision analysis, and CapCut integration.

`utils/capcut-agents/` is a bundled external integration that should be treated as a separate subsystem with its own path hacks and helper modules. `tmp/` is scratch space for generated artifacts.

## Common commands
Install dependencies:

```bash
pip install -r requirements.txt
```

Run the CLI:

```bash
python main.py
```

Inspect stream/tool-call behavior while developing:

```bash
python debug_stream.py
```

There is no committed automated test suite yet. When tests are added, use `pytest`; for a single test, the expected pattern is:

```bash
pytest tests/test_file.py::test_name
```

## Configuration and runtime
- Copy `.env.example` to `.env` and set `OPENAI_API_KEY` before running.
- `OPENAI_MODEL`, `OPENAI_API_BASE`, and `OPENAI_TEMPERATURE` are read by `src/llm/llmConfig.py`.
- Vision tools also consult `AICLIP_VISION_API_KEY`, `AICLIP_VISION_MODEL`, `AICLIP_VISION_API_BASE`, and related retry/timeout env vars.
- Workspace state defaults to `~/.aiclip/` unless `AICLIP_WORKSPACE` is set; each project workspace contains `project.json`, `media/`, `exports/`, and `cache/`.
- Python files are UTF-8 with CRLF line endings and 4-space indentation (`.editorconfig`).

## Architecture notes
- `main.py` wires together `ToolSetup`, `LLMConfig`, and `AgentBuilder`, then hands control to `CLIApp`.
- `src/cli/app.py` is the interactive loop. It handles slash commands, streams agent output when available, and keeps session state in sync with tool results.
- `src/editor_core/project.py` defines the canonical project schema: assets, timeline/tracks/clips, subtitles/spans/effects, audio stems, comments, and export presets.
- `src/editor_core/store.py` and `src/editor_core/workspace.py` handle locked load/save semantics and workspace discovery/creation.
- `src/llm/tools/project_tool.py` is the main editing surface and is intentionally large because it bridges agent calls to project mutations, validation, and rendering.
- `src/llm/tools/net_asset_tool.py` and `src/llm/tools/vision_tool.py` integrate external services; they return structured `ToolResult` objects rather than plain strings.

## Working conventions
- Prefer changing the relevant tool or editor-core command rather than adding new ad hoc shell logic.
- Treat tool return payloads as the source of truth for CLI state.
- Keep generated media, scratch files, and environment secrets out of version control.