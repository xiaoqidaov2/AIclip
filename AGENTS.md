# Repository Guidelines

## Project Structure & Module Organization
This is a Python CLI app for AI-assisted video editing. Core code lives in `src/`:
`src/cli/` handles terminal interaction, `src/coordinator/` manages multi-step tasks and workers, and `src/llm/` holds model config plus tool registration. Tool prompt text lives in `resources/docs/`, and shared assets such as fonts live in `resources/fonts/`. `main.py` is the main entry point; `debug_stream.py` is a standalone troubleshooting script. Treat `tmp/` as scratch space.

## Build, Test, and Development Commands
Install dependencies with:

```bash
pip install -r requirements.txt
```

Run the app locally with:

```bash
python main.py
```

Use `python debug_stream.py` when you need to inspect agent stream output or tool-call structure during development.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, UTF-8, and CRLF line endings (see `.editorconfig`). Use `snake_case` for modules, functions, and variables; use `PascalCase` for classes. Keep tool and prompt file names aligned with the capability they implement, such as `generate_subtitle_srt.txt` or `trim_video.txt`.

## Testing Guidelines
There is no automated test suite checked in yet. When adding tests, place them under `tests/` and prefer `pytest` naming such as `test_*.py`. For now, validate changes by running `python main.py` and exercising the relevant CLI command or tool path manually.

## Commit & Pull Request Guidelines
Recent commits use short, imperative messages with prefixes like `feat:` and `fix:`. Keep commit subjects focused and specific. Pull requests should include a brief summary, the commands you ran, and any relevant sample output or screenshots when CLI behavior changes. Call out environment changes such as updates to `.env.example` or new external dependencies.

## Security & Configuration Tips
Do not commit `.env` or generated media files. Copy `.env.example` to `.env` for local configuration, and keep `OPENAI_API_KEY` and other secrets out of source control.
