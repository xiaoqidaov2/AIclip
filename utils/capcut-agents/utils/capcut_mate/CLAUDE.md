# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CapCut Mate API is a FastAPI-based service for automating Jianying (CapCut) draft manipulation. It provides RESTful APIs for creating drafts, adding materials (videos, images, audio, captions, effects), and generating final videos via cloud rendering. The project also includes an Electron-based desktop client for downloading Jianying drafts.

## Development Commands

### Backend (Python API)

```bash
# Install dependencies (using uv package manager)
uv sync

# Additional Windows dependencies (for Jianying RPA automation)
uv pip install -e .[windows]

# Start the development server
uv run main.py

# Server runs at http://localhost:30000
# API docs at http://localhost:30000/docs
```

### Desktop Client (Electron)

```bash
cd desktop-client

# Install dependencies
npm install

# Start web frontend dev server
npm run web:dev

# Start Electron app
npm start

# Build for different platforms
npm run build-win          # Windows
npm run build-mac          # macOS ARM64
npm run build-mac-x64      # macOS x64
```

### Docker Deployment

```bash
docker-compose pull && docker-compose up -d
```

## Architecture

### Backend Structure

- **`src/router/v1.py`**: FastAPI router defining all API endpoints. All endpoints follow the pattern `/openapi/capcut-mate/v1/<endpoint>`.
- **`src/service/`**: Business logic layer. Each API endpoint has a corresponding service module. Most services have both sync and async variants (e.g., `add_videos` and `add_videos_async`).
- **`src/schemas/`**: Pydantic models for request/response validation.
- **`src/pyJianYingDraft/`**: Core library for manipulating Jianying draft files. Contains classes for segments (VideoSegment, AudioSegment, TextSegment), tracks, keyframes, effects, and metadata enums.
- **`src/middlewares/`**: Request/response middleware:
  - `PrepareMiddleware`: Creates output/temp directories before each request
  - `ResponseMiddleware`: Unified response format with `code` and `message` fields
- **`src/utils/`**: Utilities including:
  - `draft_lock_manager.py`: Async lock manager to prevent concurrent writes to the same draft
  - `video_task_manager.py`: Task queue for video generation with concurrent download/upload and serialized RPA export
  - `draft_downloader.py`: Downloads draft files from API URLs

### Key Patterns

1. **Async Locking**: Draft modifications use `DraftLockManager` to prevent concurrent writes. Always use `*_async` service functions for draft modifications.

2. **Draft Manipulation**: The `src/pyJianYingDraft/` module provides classes for building Jianying drafts programmatically. Key classes:
   - `DraftFolder`: Represents a draft folder
   - `ScriptFile`: The draft content (draft_content.json)
   - `VideoSegment`, `AudioSegment`, `TextSegment`: Media segments on tracks
   - `KeyframeProperty`: For keyframe animations

3. **Video Generation Flow**: 
   - `gen_video` submits task to `VideoGenTaskManager`
   - Tasks go through: download → RPA export (serialized) → COS upload
   - Status queryable via `gen_video_status`

4. **Windows-Only Features**: The `JianyingController` class in `src/pyJianYingDraft/jianying_controller.py` provides RPA automation for controlling the Jianying desktop app. This is only available on Windows.

### Configuration

- `config.py`: Contains all configuration including paths, URLs, and COS credentials (via environment variables)
- Key configs:
  - `DRAFT_DIR`: Output directory for generated drafts
  - `DRAFT_SAVE_PATH`: Where downloaded drafts are saved (for cloud rendering)
  - `COS_*`: Tencent Cloud Object Storage credentials

### Response Format

All API responses follow this format:
```json
{
  "code": 0,
  "message": "success",
  "<field>": <data>
}
```

Errors have non-zero codes with localized messages (zh/en based on Accept-Language header).
