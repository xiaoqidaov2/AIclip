from pathlib import Path
from typing import Optional
import logging
import os
import tempfile

from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip, TextClip
from moviepy.video.tools.subtitles import SubtitlesClip

# 压制 MoviePy 的冗长日志输出
logging.getLogger("moviepy").setLevel(logging.ERROR)


class MoviePyTool:
    """MoviePy 视频剪辑工具集 - 提供基础剪辑和画面调整能力

    支持能力：
    - 获取视频信息
    - 截取片段
    - 删除片段
    - 拼接视频
    - 调整分辨率
    - 裁剪画面
    - 字幕烧录

    所有方法返回结构化 dict，便于 agent 串联后续操作。
    """

    def _default_output_path(self, video_path: str, suffix: str) -> str:
        path = Path(video_path)
        return str(path.with_name(f"{path.stem}_{suffix}{path.suffix}"))

    def _normalize_path(self, path_text: str, collapse_filename_separators: bool = False) -> str:
        cleaned = path_text.strip().strip('"').strip("'")
        path = Path(cleaned)
        parts = [part.strip() for part in path.parts]
        if parts:
            path = Path(*parts)
        if not collapse_filename_separators:
            return str(path)

        filename = path.name.replace("_ ", "_").replace(" _", "_").replace("- ", "-").replace(" -", "-")
        return str(path.with_name(filename))

    def _ensure_trailing_blank_line(self, content: str) -> str:
        return content.rstrip() + "\n\n"

    def _resolve_subtitle_position(
        self,
        position: str,
        video_width: int,
        video_height: int,
        subtitle_width: int,
        subtitle_height: int,
        margin_x: int = 0,
        margin_y: int = 48,
        x_offset: int = 0,
        y_offset: int = 0,
    ) -> tuple[float, float]:
        position_key = position.strip().lower().replace("-", "_")
        center_x = (video_width - subtitle_width) / 2
        center_y = (video_height - subtitle_height) / 2

        if position_key in {"top", "top_center", "top_middle"}:
            return center_x + x_offset, max(margin_y, 0) + y_offset
        if position_key in {"bottom", "bottom_center", "bottom_middle"}:
            return center_x + x_offset, max(video_height - subtitle_height - margin_y, 0) + y_offset
        if position_key in {"center", "middle"}:
            return center_x + x_offset, center_y + y_offset
        if position_key in {"top_left", "left_top"}:
            return max(margin_x, 0) + x_offset, max(margin_y, 0) + y_offset
        if position_key in {"top_right", "right_top"}:
            return max(video_width - subtitle_width - margin_x, 0) + x_offset, max(margin_y, 0) + y_offset
        if position_key in {"bottom_left", "left_bottom"}:
            return max(margin_x, 0) + x_offset, max(video_height - subtitle_height - margin_y, 0) + y_offset
        if position_key in {"bottom_right", "right_bottom"}:
            return (
                max(video_width - subtitle_width - margin_x, 0) + x_offset,
                max(video_height - subtitle_height - margin_y, 0) + y_offset,
            )
        if position_key in {"left", "center_left"}:
            return max(margin_x, 0) + x_offset, center_y + y_offset
        if position_key in {"right", "center_right"}:
            return max(video_width - subtitle_width - margin_x, 0) + x_offset, center_y + y_offset

        raise ValueError(
            "position must be one of: top, bottom, center, top_left, top_right, "
            "bottom_left, bottom_right, left, right"
        )

    def _ensure_srt(self, subtitle_path: str) -> tuple[str, Optional[str]]:
        subtitle_path = self._normalize_path(subtitle_path)
        path = Path(subtitle_path)
        if path.suffix.lower() == ".srt":
            # SRT file - need to ensure it's UTF-8 encoded for MoviePy
            # MoviePy's SubtitlesClip has encoding issues on Windows
            # So we always create a UTF-8 temp file
            with open(subtitle_path, "r", encoding="utf-8") as f:
                content = self._ensure_trailing_blank_line(f.read())
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
            try:
                temp_file.write(content)
                temp_file.close()
                return temp_file.name, temp_file.name
            except Exception:
                temp_file.close()
                os.unlink(temp_file.name)
                raise

        if path.suffix.lower() != ".vtt":
            raise ValueError("subtitle_path must be .srt or .vtt")

        with open(subtitle_path, "r", encoding="utf-8") as f:
            content = self._ensure_trailing_blank_line(f.read())

        lines = []
        index = 1
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line == "WEBVTT":
                continue
            if "-->" in line:
                lines.append(str(index))
                lines.append(line.replace(".", ","))
                index += 1
            else:
                lines.append(line)
                lines.append("")

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".srt", mode="w", encoding="utf-8")
        try:
            temp_file.write(self._ensure_trailing_blank_line("\n".join(lines)))
            temp_file.close()
            return temp_file.name, temp_file.name
        except Exception:
            temp_file.close()
            os.unlink(temp_file.name)
            raise

    def add_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        font_path: str,
        output_path: Optional[str] = None,
        font_size: int = 36,
        color: str = "white",
        position: str = "bottom",
        margin_x: int = 0,
        margin_y: int = 48,
        x_offset: int = 0,
        y_offset: int = 0,
        subtitle_box_width_ratio: float = 0.9,
    ) -> dict:
        """将字幕文件烧录到视频中。

        Args:
            video_path: 视频文件路径
            subtitle_path: 字幕文件路径（.srt 或 .vtt）
            font_path: 字体文件路径（.ttf），必须指定
            output_path: 输出视频路径，可选
            font_size: 字体大小，默认 36
            color: 字体颜色，默认 white
            position: 字幕位置，支持 top/bottom/center/left/right 及四角预设
            margin_x: 侧边安全边距，默认 0
            margin_y: 上下安全边距，默认 48
            x_offset: 位置水平微调，单位像素
            y_offset: 位置垂直微调，单位像素
            subtitle_box_width_ratio: 字幕文本区域宽度占比，默认 0.9
        """
        if not 0.1 <= subtitle_box_width_ratio <= 1.0:
            raise ValueError("subtitle_box_width_ratio must be between 0.1 and 1.0")

        video_path = self._normalize_path(video_path)
        subtitle_path = self._normalize_path(subtitle_path)
        font_path = self._normalize_path(font_path)
        if output_path:
            output_path = self._normalize_path(output_path, collapse_filename_separators=True)

        if not os.path.exists(font_path):
            raise ValueError(f"font_path does not exist: {font_path}")

        source = None
        final_clip = None
        subtitle_clip = None
        temp_subtitle_path = None
        try:
            source = VideoFileClip(video_path)
            srt_path, temp_subtitle_path = self._ensure_srt(subtitle_path)

            subtitle_clip = SubtitlesClip(
                srt_path,
                make_textclip=lambda text: TextClip(
                    text=text,
                    font=font_path,
                    font_size=font_size,
                    color=color,
                    method="caption",
                    text_align="center",
                    horizontal_align="center",
                    vertical_align="bottom",
                    size=(int(source.w * subtitle_box_width_ratio), None),
                ),
                encoding="utf-8",
            )
            subtitle_clip.size = (
                int(source.w * subtitle_box_width_ratio),
                max(int(font_size * 3), 1),
            )
            subtitle_clip = subtitle_clip.with_position(
                self._resolve_subtitle_position(
                    position,
                    int(source.w),
                    int(source.h),
                    int(subtitle_clip.w),
                    int(subtitle_clip.h),
                    margin_x=margin_x,
                    margin_y=margin_y,
                    x_offset=x_offset,
                    y_offset=y_offset,
                )
            )

            final_clip = CompositeVideoClip([source, subtitle_clip], size=source.size)
            output_path = output_path or self._default_output_path(video_path, "subbed")
            final_clip.write_videofile(output_path, logger="bar")
            return {
                "output_path": output_path,
                "source_path": video_path,
                "subtitle_path": subtitle_path,
                "font_path": font_path,
                "position": position,
                "margin_x": margin_x,
                "margin_y": margin_y,
                "x_offset": x_offset,
                "y_offset": y_offset,
                "subtitle_box_width_ratio": subtitle_box_width_ratio,
                "operation": "add_subtitles",
                "duration": float(source.duration),
            }
        finally:
            if subtitle_clip is not None:
                subtitle_clip.close()
            if final_clip is not None:
                final_clip.close()
            if source is not None:
                source.close()
            if temp_subtitle_path is not None and os.path.exists(temp_subtitle_path):
                os.unlink(temp_subtitle_path)

    def get_video_info(self, video_path: str) -> dict:
        """获取视频文件的基础信息。"""
        video_path = self._normalize_path(video_path)
        clip = None
        try:
            clip = VideoFileClip(video_path)
            return {
                "video_path": video_path,
                "duration": float(clip.duration),
                "fps": float(clip.fps),
                "size": [int(clip.w), int(clip.h)],
                "has_audio": clip.audio is not None,
            }
        finally:
            if clip is not None:
                clip.close()

    def trim_video(self, video_path: str, start: float, end: float, output_path: Optional[str] = None) -> dict:
        """截取视频指定时间范围。"""
        if start >= end:
            raise ValueError("start must be less than end")

        video_path = self._normalize_path(video_path)
        if output_path:
            output_path = self._normalize_path(output_path, collapse_filename_separators=True)

        source = VideoFileClip(video_path)
        trimmed = None
        try:
            if end > source.duration:
                raise ValueError("end exceeds video duration")

            output_path = output_path or self._default_output_path(video_path, "trimmed")
            trimmed = source.subclipped(start, end)
            trimmed.write_videofile(output_path, logger="bar")
            return {
                "output_path": output_path,
                "source_path": video_path,
                "operation": "trim",
                "start": float(start),
                "end": float(end),
                "duration": float(trimmed.duration),
            }
        finally:
            if trimmed is not None:
                trimmed.close()
            source.close()

    def cutout_video(self, video_path: str, start: float, end: float, output_path: Optional[str] = None) -> dict:
        """删除视频指定时间范围。"""
        if start >= end:
            raise ValueError("start must be less than end")

        video_path = self._normalize_path(video_path)
        if output_path:
            output_path = self._normalize_path(output_path, collapse_filename_separators=True)

        source = VideoFileClip(video_path)
        cut = None
        try:
            if end > source.duration:
                raise ValueError("end exceeds video duration")

            output_path = output_path or self._default_output_path(video_path, "cutout")
            cut = source.with_section_cut_out(start, end)
            cut.write_videofile(output_path, logger="bar")
            return {
                "output_path": output_path,
                "source_path": video_path,
                "operation": "cutout",
                "removed_range": [float(start), float(end)],
                "duration": float(cut.duration),
            }
        finally:
            if cut is not None:
                cut.close()
            source.close()

    def concatenate_videos(self, video_paths: list[str], output_path: Optional[str] = None, method: str = "compose") -> dict:
        """拼接多个视频文件。"""
        if not video_paths:
            raise ValueError("video_paths cannot be empty")

        video_paths = [self._normalize_path(path) for path in video_paths]
        if output_path:
            output_path = self._normalize_path(output_path, collapse_filename_separators=True)

        clips = [VideoFileClip(path) for path in video_paths]
        final_clip = None
        try:
            output_path = output_path or self._default_output_path(video_paths[0], "concat")
            final_clip = concatenate_videoclips(clips, method=method)
            final_clip.write_videofile(output_path, logger="bar")
            return {
                "output_path": output_path,
                "source_paths": video_paths,
                "operation": "concatenate",
                "clip_count": len(video_paths),
                "duration": float(final_clip.duration),
            }
        finally:
            if final_clip is not None:
                final_clip.close()
            for clip in clips:
                clip.close()

    def resize_video(
        self,
        video_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        scale: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> dict:
        """调整视频分辨率。"""
        if width is None and height is None and scale is None:
            raise ValueError("width, height, or scale must be provided")

        video_path = self._normalize_path(video_path)
        if output_path:
            output_path = self._normalize_path(output_path, collapse_filename_separators=True)

        source = VideoFileClip(video_path)
        resized = None
        try:
            output_path = output_path or self._default_output_path(video_path, "resized")

            if scale is not None:
                resized = source.resized(scale)
            else:
                new_size = (
                    width if width is not None else source.w,
                    height if height is not None else source.h,
                )
                resized = source.resized(new_size)

            resized.write_videofile(output_path, logger="bar")
            return {
                "output_path": output_path,
                "source_path": video_path,
                "operation": "resize",
                "original_size": [int(source.w), int(source.h)],
                "new_size": [int(resized.w), int(resized.h)],
            }
        finally:
            if resized is not None:
                resized.close()
            source.close()

    def crop_video(
        self,
        video_path: str,
        x1: int,
        y1: int,
        x2: Optional[int] = None,
        y2: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> dict:
        """裁剪视频画面。"""
        if x2 is None and width is None:
            raise ValueError("either x2 or width must be provided")
        if y2 is None and height is None:
            raise ValueError("either y2 or height must be provided")

        video_path = self._normalize_path(video_path)
        if output_path:
            output_path = self._normalize_path(output_path, collapse_filename_separators=True)

        source = VideoFileClip(video_path)
        cropped = None
        try:
            output_path = output_path or self._default_output_path(video_path, "cropped")
            cropped = source.cropped(x1=x1, y1=y1, x2=x2, y2=y2, width=width, height=height)
            cropped.write_videofile(output_path, logger="bar")
            return {
                "output_path": output_path,
                "source_path": video_path,
                "operation": "crop",
                "original_size": [int(source.w), int(source.h)],
                "cropped_size": [int(cropped.w), int(cropped.h)],
                "crop_region": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "width": width,
                    "height": height,
                },
            }
        finally:
            if cropped is not None:
                cropped.close()
            source.close()
