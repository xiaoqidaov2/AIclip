from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseProbeMediaMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _probe_media(self, media_path: Path) -> Dict[str, Any]:

        clip = None

        is_audio_only = media_path.suffix.lower() in {
            ".mp3",
            ".wav",
            ".m4a",
            ".aac",
            ".flac",
            ".ogg",
            ".wma",
        }

        try:

            if is_audio_only:

                clip = AudioFileClip(str(media_path))

                return {
                    "duration": float(clip.duration or 0.0),
                    "fps": 0.0,
                    "size": [0, 0],
                    "has_audio": True,
                    "media_kind": "audio",
                }

            clip = VideoFileClip(str(media_path))

            return {
                "duration": float(clip.duration or 0.0),
                "fps": float(getattr(clip, "fps", 0.0) or 0.0),
                "size": [int(clip.w), int(clip.h)],
                "has_audio": clip.audio is not None,
                "media_kind": "video",
            }

        finally:

            if clip is not None:

                clip.close()
