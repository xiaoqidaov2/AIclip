from functools import cached_property

from .whisper_cache import get_whisper_model


class SubtitleTool:
    """字幕生成工具 - 从音频或视频文件生成带时间轴的字幕文件

    这个工具使用 faster-whisper 模型进行语音识别，并生成标准字幕格式。
    支持 SRT 和 VTT 两种常见字幕格式。

    适用于：
    - 为视频添加字幕
    - 生成带时间轴的会议记录
    - 创建多语言字幕文件

    主要方法:
        generate_srt(audio_path, language) - 生成 SRT 格式字幕
        generate_vtt(audio_path, language) - 生成 VTT 格式字幕
        generate(audio_path, language, format) - 统一接口，通过 format 参数选择格式

    参数说明:
        audio_path (str): 音频或视频文件的完整路径
        language (str, 可选): 语言代码，默认 'zh'（中文）
        format (str, 可选): 字幕格式，'srt' 或 'vtt'，默认 'srt'

    返回值结构:
        {
            "subtitle": "完整字幕文本（按格式生成）",
            "format": "srt 或 vtt",
            "segment_count": 字幕段落数量,
            "language": "检测到的语言代码"
        }

    使用示例:
        tool = SubtitleTool()
        result = tool.generate_srt("video.mp4", language="zh")
        print(result["subtitle"])  # 打印完整 SRT 内容

    格式说明:
        SRT 格式示例:
            1
            00:00:00,000 --> 00:00:05,000
            第一句字幕内容

        VTT 格式示例:
            WEBVTT

            00:00.000 --> 00:05.000
            第一句字幕内容
    """

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    @cached_property
    def model(self):
        return get_whisper_model(self.model_size, self.device, self.compute_type)

    def _format_timestamp_srt(self, seconds: float) -> str:
        """将秒转换为 SRT 时间格式: HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        """将秒转换为 VTT 时间格式: HH:MM:SS.mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def generate_srt(self, audio_path: str, language: str = "zh") -> dict:
        """生成 SRT 格式字幕

        Args:
            audio_path: 音频/视频文件路径
            language: 语言代码，默认中文

        Returns:
            dict: {
                "subtitle": "SRT格式字幕内容",
                "format": "srt",
                "segment_count": 段落数量,
                "language": 检测到的语言
            }
        """
        segments, info = self.model.transcribe(audio_path, language=language)
        lines = []
        for i, segment in enumerate(segments, start=1):
            start_time = self._format_timestamp_srt(segment.start)
            end_time = self._format_timestamp_srt(segment.end)
            text = segment.text.strip()
            lines.append(f"{i}")
            lines.append(f"{start_time} --> {end_time}")
            lines.append(text)
            lines.append("")

        return {
            "subtitle": "\n".join(lines),
            "format": "srt",
            "segment_count": len(lines) // 4,
            "language": info.language,
        }

    def generate_vtt(self, audio_path: str, language: str = "zh") -> dict:
        """生成 VTT 格式字幕

        Args:
            audio_path: 音频/视频文件路径
            language: 语言代码，默认中文

        Returns:
            dict: {
                "subtitle": "VTT格式字幕内容",
                "format": "vtt",
                "segment_count": 段落数量,
                "language": 检测到的语言
            }
        """
        segments, info = self.model.transcribe(audio_path, language=language)
        lines = ["WEBVTT", ""]
        for segment in segments:
            start_time = self._format_timestamp_vtt(segment.start)
            end_time = self._format_timestamp_vtt(segment.end)
            text = segment.text.strip()
            lines.append(f"{start_time} --> {end_time}")
            lines.append(text)
            lines.append("")

        return {
            "subtitle": "\n".join(lines),
            "format": "vtt",
            "segment_count": (len(lines) - 2) // 3,
            "language": info.language,
        }

    def generate(self, audio_path: str, language: str = "zh", format: str = "srt") -> dict:
        """统一接口生成字幕

        Args:
            audio_path: 音频/视频文件路径
            language: 语言代码，默认中文
            format: 字幕格式，支持 "srt" 或 "vtt"

        Returns:
            dict: 包含字幕内容和元数据
        """
        if format.lower() == "vtt":
            return self.generate_vtt(audio_path, language)
        else:
            return self.generate_srt(audio_path, language)
