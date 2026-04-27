# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt    # install dependencies
python main.py                      # start interactive CLI
python main.py --help               # CLI options
python main.py --command "/help"    # run single command and exit
pytest                              # run full test suite
pytest tests/editor_core/test_commands_basic.py  # single test file
flake8 src tests                    # lint check (max-line-length=160)
```

## Architecture

AiClip is a Python CLI app for AI-assisted video editing. An LLM agent (LangChain) orchestrates a tool set for transcription, subtitle generation, trimming, compositing, rendering, and asset search.

### Layered structure

- **`main.py`** — Entry point. Builds agent, LLM config, tools, and CLIApp.
- **`src/cli/`** — CLI interaction via mixin-based `CLIApp` (commands, state, agent, runtime mixins). Uses `CLIRenderer` for streaming agent output with a spinner and rate-limit retry.
- **`src/llm/`** — LLM config, skill routing (`SkillRouter` — keyword + LLM-based), tool setup and registration (`ToolSetup`), and query orchestration (`QueryOrchestrator` — multi-step pipeline: route → plan → execute → compress).
- **`src/editor_core/`** — Core editing model and operations:
  - **Project model** (`project.py`, `project_model/`): Dataclass-based (`Project`, `Asset`, `Clip`, `Track`, `Timeline`, `SubtitleCue`, `SubtitleSpan`, etc.)
  - **Commands** (`commands.py`, `commands_impl/`): Command pattern (`Command` ABC → `execute(project) → CommandResult`)
  - **Store** (`store.py`): Thread-safe `ProjectStore` with atomic read/write via tempfile+os.replace, per-path reentrant locks, and `mutate()` for load-edit-save
  - **Workspace** (`workspace.py`): `ProjectWorkspace` (path-traversal-guarded media/exports/cache dirs) and `WorkspaceRegistry` (persistent media→project mapping)
  - **Codec** (`codec.py`): JSON and XML serialization for project files
  - **Validation** (`validation.py`): `validate_project()` → `ValidationReport`
- **`src/net_asset/`** (implied): Network asset providers for stock media search/download.

### Skills system

Three skills defined in `resources/skills/skills.json`:
- `project_core` — Core editing: transcribe, subtitle, trim, speed, render, export, effects, comments
- `asset_discovery` — Search/download stock assets (Pexels, Pixabay, Freesound)
- `vision_inspection` — Visual media analysis via DashScope/Qwen-VL

Each skill maps to a tool set and can be locked (`/skill`), auto-routed by `SkillRouter`, or composed via `QueryOrchestrator` steps. Agent roles/per-agent system prompts in `resources/agent_roles.json`.

### Tool definition flow

1. Tools are plain functions in `src/llm/tools/impl/`
2. Post-parse logic in `src/llm/tools/postparse/` refines tool outputs
3. `ToolSetup` registers tools per skill, builds system prompts from `resources/docs/*.txt`
4. `AgentBuilder` wraps them as LangChain tools for the agent

### Config

`.env` file (copy from `.env.example`):
- `OPENAI_API_KEY` (required), `OPENAI_MODEL`, `OPENAI_TEMPERATURE`
- `AICLIP_VISION_*` / `DASHSCOPE_API_KEY` for vision analysis
- `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `FREESOUND_API_KEY` for stock asset search
- `AICLIP_WORKSPACE` — project workspace root (default: `~/.aiclip`)

### Key patterns

- **Commands are data-driven**: Each command constructor takes a value object, `execute(project)` returns `CommandResult(ok, code, message, changes, validation, state)`. Validate domain rules inside execute, return `ok=False` with a code rather than raising.
- **Project store is thread-safe**: Uses per-path `RLock` and ordered lock acquisition to prevent deadlocks. Use `store.mutate(path, mutator_fn)` for load-edit-save.
- **Workspace path guard**: `ProjectWorkspace.resolve_path()` validates that resolved paths stay within the workspace root.
- **Atomic writes**: Store writes to a temp file then `os.replace()` for crash safety.
- **FFmpeg via moviepy**: Video operations (trim, speed, render) rely on moviepy/ffmpeg.
