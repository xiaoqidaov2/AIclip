from functools import cached_property

from .whisper_cache import get_whisper_model


class ASRTool:
    """Fast Whisper 语音识别工具 - 将音频或视频文件转换为文字

    这个工具使用 faster-whisper 模型进行语音转文字，支持多种语言。
    适用于：视频字幕生成、音频笔记转文字、会议记录等场景。

    参数:
        audio_path (str): 音频或视频文件的完整路径
        language (str, 可选): 语言代码，如 'zh' 表示中文，'en' 表示英文。
                            默认为 'zh'

    返回:
        dict: 包含以下键:
            - text (str): 转录后的完整文本
            - language (str): 检测到的语言代码
            - language_probability (float): 语言检测置信度 (0-1)

    使用示例:
        result = asr_tool.transcribe("video.mp4", language="zh")
        print(result["text"])  # 获取转录文本
    """

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    @cached_property
    def model(self):
        return get_whisper_model(self.model_size, self.device, self.compute_type)

    def transcribe(self, audio_path: str, language: str = "zh"):
        """转写音频文件并返回文本"""
        segments, info = self.model.transcribe(audio_path, language=language)
        text = "".join(segment.text for segment in segments).strip()
        return {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
        }
