# Repository Guidelines

## Project Structure & Module Organization
This is a Python CLI for AI-assisted video editing. Core code lives in `src/`:
- `src/cli/` handles terminal interaction, command parsing, and streaming output.
- `src/coordinator/` manages multi-step worker orchestration, notifications, and verification.
- `src/editor_core/` owns the project model, persistence, validation, and edit/render commands.
- `src/llm/` contains model configuration and tool registration.

Prompt text for tools lives in `resources/docs/`. Shared assets such as fonts are in `resources/fonts/`. The bundled CapCut integration lives under `utils/capcut-agents/` and should be treated as a separate subsystem. Use `tmp/` only for scratch artifacts.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` installs project dependencies.
- `python main.py` starts the interactive CLI.
- `python main.py --help` shows startup options.
- `python main.py --command "/help"` runs a single command and exits.
- `python debug_stream.py` is useful for inspecting stream output and tool-call structure during development.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, UTF-8 encoding, and CRLF line endings per `.editorconfig`. Use `snake_case` for modules, functions, and variables, and `PascalCase` for classes. Keep tool and prompt filenames aligned with their behavior, such as `trim_project_clip.txt` or `add_project_subtitle.txt`.

## Testing Guidelines
There is no committed automated test suite yet. When adding tests, place them under `tests/` and use `pytest` naming like `test_*.py`. Validate changes locally with `python main.py` and exercise the relevant CLI command or tool path manually.

## Commit & Pull Request Guidelines
Recent commits use short, imperative subjects, often with prefixes such as `feat:` and `fix:`. Keep commits focused and specific. PRs should include a brief summary, the commands you ran, and any relevant sample output or screenshots when CLI behavior changes.

## Security & Configuration Tips
Do not commit `.env` files or generated media. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` plus any other required runtime values locally.
