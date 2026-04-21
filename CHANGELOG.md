# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed
- Windows path separator bug in `workspace.py` (`to_storage_path` now returns POSIX paths)
- UTC deprecation warning: replaced `datetime.utcnow()` with timezone-aware `datetime.now(timezone.utc)`
- Environment variable mismatch: `FREESOUND_CLIENT_ID` → `FREESOUND_API_KEY` in `.env.example` and README

### Added
- `langchain-openai` added to `requirements.txt` (was imported but undeclared)
- `pytest` and `flake8` added to `requirements.txt` (dev tooling)
- `.flake8` configuration file (`max-line-length = 160`, E203/W503 ignored)
- `src/llm/tools/project_tool_impl.py` — main project tool implementation refactored into separate file
- `src/llm/tools/project_tool_postparse.py` — subtitle, transcription and face-detection operations
- `src/llm/tools/project_tool_render.py` — render mixin with subtitle animation effects

### Changed
- README: added missing environment variables (`AICLIP_WORKSPACE`, `AICLIP_VISION_*`), corrected workspace output path description

---

## [0.4.0] - 2026-04-20

### Added
- Expanded `editor_core` test coverage: project model, codec, workspace, store, command and contract tests (42 tests total)

### Changed
- Refactored project structure and enhanced skill orchestration

### Fixed
- Removed local coverage artifact from repository

---

## [0.3.0] - 2026-04-17

### Added
- Effect tool: `add_project_effect`, `update_project_effect`, `remove_project_effect` core implementation
- Batch subtitle update tool and subtitle normalization data

### Fixed
- Effect tool error on initialization

---

## [0.2.0] - 2026-04-16

### Added
- Initial visual effect tool skeleton

### Changed
- Code structure refactored for improved readability and maintainability

---

## [0.1.0] - 2026-04-13

### Added
- Initial README documentation (features, installation, usage)
- File writing and directory listing tools
- Enhanced subtitle generation tooling
- Refactored tool prompts and documentation

### Fixed
- Wrapped tools as `BaseTool` and fixed subprocess encoding issues
