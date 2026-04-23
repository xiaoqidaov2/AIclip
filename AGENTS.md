# Project Guidelines

## Architecture
AiClip is a Python CLI for AI-assisted video editing. Keep changes inside the existing boundaries instead of adding ad hoc orchestration in entrypoints or shell scripts.

- `main.py` wires config, tool setup, agent construction, and the CLI app.
- `src/cli/` owns interactive commands, streaming output, and session state.
- `src/editor_core/` is the source of truth for project data, persistence, validation, and workspace/path handling.
- `src/llm/` owns model config, tool registration, skills, and agent-facing tool surfaces.

Treat `utils/capcut-agents/` as a separate subsystem. Prefer linking to or reusing its own conventions instead of folding its behavior into the main app.

## Build And Validation
Use the narrowest validation that matches the area you touched.

- `pip install -r requirements.txt` installs dependencies.
- `python main.py` starts the interactive CLI.
- `python main.py --help` checks startup argument wiring.
- `python main.py --command "/help"` is the cheapest CLI smoke test.
- `python debug_stream.py` is the focused check for stream output and tool-call behavior.
- `pytest tests/editor_core/` is the preferred regression check when changing `src/editor_core/`.

There is no full committed test suite yet. For tool or CLI changes, run a targeted command path manually after code changes.

## Core Conventions
- Follow the existing Python style: 4-space indentation, UTF-8, and CRLF line endings from `.editorconfig`.
- Use `snake_case` for modules/functions/variables and `PascalCase` for classes.
- Keep tool prompt filenames aligned with the tool name, for example `resources/docs/trim_project_clip.txt`.
- When adding or changing an agent-facing tool, update both the implementation and its prompt/skill registration instead of changing only one side.

## Project Model Rules
- Keep project mutations inside `src/editor_core/` abstractions. `ProjectStore` already provides per-path re-entrant locking and atomic temp-file replacement; use it instead of open-coded read/write cycles.
- Asset paths stored in projects should be project-relative when the asset lives under the workspace, for example `media/input.mp4`. Avoid storing workspace-relative paths directly.
- Project workspaces live under `AICLIP_WORKSPACE` or `~/.aiclip` by default and contain `project.json`, `media/`, `exports/`, and `cache/`.
- The same source media path should deterministically resolve to the same project through the workspace registry flow, not through ad hoc prompting logic.
- Exported or generated artifacts should stay in the managed workspace by default, not beside the source media.

## Tooling Expectations
- Tool output is authoritative. Use structured fields such as `decision`, `validation`, `render_state`, `state`, and `next_actions` to guide behavior; treat `message` and `summary` as display text.
- If a request needs subtitles and no subtitle source exists, transcribe first before subtitle-dependent edits.
- If `render_state.ready` is false, fix the project state before attempting render.

## Reference Points
Link to existing docs instead of duplicating them when possible.

- `README.md` covers installation, environment variables, CLI commands, and common usage.
- `CLAUDE.md` gives the broader architecture and runtime/configuration overview.
- `resources/docs/project_core_contract.txt` defines the agent-facing tool contract and decision order.
- `resources/skills/` contains the shipped workflow skill docs.
- `tests/editor_core/` shows stable patterns for workspace resolution, store mutation, validation, and codec behavior.

## Change Hygiene
- Do not commit `.env` files, generated media, or scratch artifacts from `tmp/`.
- Keep commits focused and use short imperative subjects, commonly with prefixes such as `feat:` and `fix:`.
- If you touch behavior that changes user-visible CLI flow or tool semantics, update the nearest prompt or documentation entry in the same change.
