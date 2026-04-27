from __future__ import annotations

# flake8: noqa: F401

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from faster_whisper import WhisperModel  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont
from moviepy import AudioFileClip, VideoFileClip  # type: ignore[import-untyped]

from src.editor_core.commands import (
    AddAudioStemCommand,
    AddAssetCommand,
    AddClipCommand,
    AddCommentCommand,
    AddEffectCommand,
    AddSubtitleCueCommand,
    AddSubtitleSpanCommand,
    LockCommentCommand,
    RemoveAudioStemCommand,
    RemoveCommentCommand,
    RemoveEffectCommand,
    RemoveSubtitleCueCommand,
    RemoveSubtitleEffectCommand,
    RemoveSubtitleSpanCommand,
    SetClipSpeedCommand,
    SetClipTransformCommand,
    SetExportPresetCommand,
    SetProjectMetadataCommand,
    SetSubtitleEffectCommand,
    TrimClipCommand,
    UpdateAudioStemCommand,
    UpdateCommentCommand,
    UpdateEffectCommand,
    UpdateSubtitleCueCommand,
    UpdateSubtitleSpanCommand,
)
from src.editor_core.contracts import ArtifactRef, RenderState, ToolResult, ValidationSnapshot
from src.editor_core.project import (
    Asset,
    AudioStem,
    Clip,
    Comment,
    Effect,
    ExportPreset,
    Project,
    SubtitleCue,
    SubtitleEffect,
    SubtitleSpan,
    Timeline,
    Track,
)
