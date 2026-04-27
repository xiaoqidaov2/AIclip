Repository Guidelines
Project Structure & Module Organization
This repository is a Python CLI app for AI-assisted video editing. Main entry points live in main.py and src/cli/. Core editing logic is in src/editor_core/, LLM orchestration and tool wiring live in src/llm/, and network asset providers live in src/net_asset/. Tests are under tests/, grouped by area such as tests/editor_core/ and tests/cli/. Shared prompts, skill notes, and command docs are stored in resources/. Keep generated or temporary files in tmp/ only.

Build, Test, and Development Commands
python -m venv .venv and .venv\Scripts\activate: create and enter a local virtual environment.

pip install -r requirements.txt: install runtime and test dependencies.

python main.py --help: inspect CLI options.

python main.py --command "/help": run a single CLI command without interactive mode.

pytest: run the full test suite.

flake8 src tests: check style and import issues.

Coding Style & Naming Conventions
Use 4-space indentation, UTF-8 text, and CRLF line endings for Python files. Follow the existing module layout and prefer descriptive snake_case for functions, modules, and test files. Class names use CapWords. Keep lines within the flake8 limit of 160 characters. Respect the repo's .editorconfig and .flake8 settings.

Testing Guidelines
pytest is the primary test framework. Add tests alongside the area they cover, using names like test_workspace.py or test_cli_commands.py. Prefer focused unit tests for src/editor_core/ and src/cli/, and add regression tests for command parsing, validation, and codec behavior when changing those paths. Run pytest before submitting changes.

Commit & Pull Request Guidelines
Recent commits use short conventional prefixes such as feat:, test:, chore:, and refactor:. Match that style when practical. Pull requests should summarize the user-facing change, mention commands run for verification, and note any config or environment updates. Include screenshots or sample CLI output when behavior changes are visible.

Agent Behavior Guidelines (for the AI Video Editing Assistant)
The AI agent built by this project — the assistant that interacts with users via CLI — must operate solely on the basis of the model’s own reasoning and emergent behavior. No hard‑coded human prior guidance, forced confirmations, blocking user input prompts, unsolicited help popups, or any other form of manual override logic is permitted. All decisions, action sequences, and responses shall be generated autonomously by the AI from its internal understanding and the immediate conversational context.

In Chinese: 本项目设计的 AI 视频编辑 Agent 必须完全基于模型自身的自我思考进行运作，不得加入任何人类的先验引导、强制操作或人工干预逻辑。 禁止预设任何必须由用户确认才能继续的步骤，禁止主动打断用户流程的提示，也不得要求用户进行人工覆写。

Developers must not hard‑code any conditional branches that force the agent to ask for confirmation, pause execution, or request manual intervention unless the user explicitly asks for such guidance. The agent’s behavior should feel fluid, non‑intrusive, and entirely driven by the AI’s own inference.

Configuration & Secrets
Copy .env.example to .env and set required keys such as OPENAI_API_KEY. Do not commit secrets, workspace data, or exported media. The app defaults to a workspace under AICLIP_WORKSPACE; keep project assets and exports inside that root.

