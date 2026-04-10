from functools import cached_property
from pathlib import Path
from typing import Optional

from .whisper_cache import get_whisper_model


class SubtitleTool:
    """Whisper 工具 - 提供转写和字幕生成能力

    这个工具使用 faster-whisper 模型进行语音识别，既可以直接转写文本，
    也可以生成标准字幕格式。支持 SRT 和 VTT 两种常见字幕格式。

    适用于：
    - 音频/视频转写
    - 为视频添加字幕
    - 生成带时间轴的会议记录
    - 创建多语言字幕文件

    主要方法:
        transcribe(audio_path, language) - 生成纯文本转写结果
        generate_srt(audio_path, language) - 生成 SRT 格式字幕
        generate_vtt(audio_path, language) - 生成 VTT 格式字幕
        generate(audio_path, language, subtitle_format) - 统一接口，通过 subtitle_format 选择格式

    参数说明:
        audio_path (str): 音频或视频文件的完整路径
        language (str, 可选): 语言代码，默认 'zh'（中文）
        subtitle_format (str, 可选): 字幕格式，'srt' 或 'vtt'，默认 'srt'

    返回值结构:
        {
            "subtitle": "完整字幕文本（按格式生成）",
            "format": "srt 或 vtt",
            "segment_count": 字幕段落数量,
            "language": "检测到的语言代码",
            "output_path": "保存后的字幕文件路径"
        }

    使用示例:
        tool = SubtitleTool()
        result = tool.generate_srt("video.mp4", language="zh")
        print(result["output_path"])  # 保存后的字幕文件路径

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

    def _transcribe_audio(self, audio_path: str, language: str):
        return self.model.transcribe(audio_path, language=language)

    def transcribe(self, audio_path: str, language: str = "zh") -> dict:
        """转写音频/视频文件并返回文本。"""
        segments, info = self._transcribe_audio(audio_path, language=language)
        text = "".join(segment.text for segment in segments).strip()
        return {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
        }

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

    def _default_output_path(self, audio_path: str, subtitle_format: str) -> str:
        path = Path(audio_path)
        suffix = f".{subtitle_format.lower().lstrip('.')}"
        if path.suffix:
            return str(path.with_suffix(suffix))
        return str(path.with_name(f"{path.name}{suffix}"))

    def _write_subtitle_file(self, subtitle_text: str, output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(subtitle_text, encoding="utf-8")
        return str(path)

    def _finalize_subtitle_text(self, subtitle_text: str) -> str:
        """Ensure the subtitle file ends with a blank line for MoviePy parsing."""
        return subtitle_text.rstrip() + "\n\n"

    def generate_srt(self, audio_path: str, language: str = "zh", output_path: Optional[str] = None) -> dict:
        """生成 SRT 格式字幕

        Args:
            audio_path: 音频/视频文件路径
            language: 语言代码，默认中文

        Returns:
            dict: {
                "subtitle": "SRT格式字幕内容",
                "format": "srt",
                "segment_count": 段落数量,
                "language": 检测到的语言,
                "output_path": 保存的字幕文件路径
            }
        """
        segments, info = self._transcribe_audio(audio_path, language=language)
        lines = []
        segment_count = 0
        for i, segment in enumerate(segments, start=1):
            start_time = self._format_timestamp_srt(segment.start)
            end_time = self._format_timestamp_srt(segment.end)
            text = segment.text.strip()
            lines.append(f"{i}")
            lines.append(f"{start_time} --> {end_time}")
            lines.append(text)
            lines.append("")
            segment_count += 1

        subtitle_text = self._finalize_subtitle_text("\n".join(lines))
        output_path = output_path or self._default_output_path(audio_path, "srt")
        saved_path = self._write_subtitle_file(subtitle_text, output_path)

        return {
            "subtitle": subtitle_text,
            "format": "srt",
            "segment_count": segment_count,
            "language": info.language,
            "output_path": saved_path,
        }

    def generate_vtt(self, audio_path: str, language: str = "zh", output_path: Optional[str] = None) -> dict:
        """生成 VTT 格式字幕

        Args:
            audio_path: 音频/视频文件路径
            language: 语言代码，默认中文

        Returns:
            dict: {
                "subtitle": "VTT格式字幕内容",
                "format": "vtt",
                "segment_count": 段落数量,
                "language": 检测到的语言,
                "output_path": 保存的字幕文件路径
            }
        """
        segments, info = self._transcribe_audio(audio_path, language=language)
        lines = ["WEBVTT", ""]
        segment_count = 0
        for segment in segments:
            start_time = self._format_timestamp_vtt(segment.start)
            end_time = self._format_timestamp_vtt(segment.end)
            text = segment.text.strip()
            lines.append(f"{start_time} --> {end_time}")
            lines.append(text)
            lines.append("")
            segment_count += 1

        subtitle_text = self._finalize_subtitle_text("\n".join(lines))
        output_path = output_path or self._default_output_path(audio_path, "vtt")
        saved_path = self._write_subtitle_file(subtitle_text, output_path)

        return {
            "subtitle": subtitle_text,
            "format": "vtt",
            "segment_count": segment_count,
            "language": info.language,
            "output_path": saved_path,
        }

    def generate(
        self,
        audio_path: str,
        language: str = "zh",
        subtitle_format: str = "srt",
        output_path: Optional[str] = None,
    ) -> dict:
        """统一接口生成字幕

        Args:
            audio_path: 音频/视频文件路径
            language: 语言代码，默认中文
            subtitle_format: 字幕格式，支持 "srt" 或 "vtt"
            output_path: 可选输出路径，默认保存到与输入同名的字幕文件

        Returns:
            dict: 包含字幕内容和元数据
        """
        if subtitle_format.lower() == "vtt":
            return self.generate_vtt(audio_path, language, output_path=output_path)
        else:
            return self.generate_srt(audio_path, language, output_path=output_path)
