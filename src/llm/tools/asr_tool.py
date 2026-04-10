from .subtitle_tool import SubtitleTool


class ASRTool(SubtitleTool):
    """Backward-compatible alias for SubtitleTool.

    The Whisper implementation now lives in SubtitleTool, which provides both
    transcribe() and subtitle generation methods.
    """

    pass
