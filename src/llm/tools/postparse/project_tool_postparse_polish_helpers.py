from __future__ import annotations
import re
from typing import Any, Iterable, Optional

from src.editor_core.project import Project, SubtitleCue, SubtitleEffect, SubtitleSpan


class ProjectToolPostParsePolishHelpersMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    _HOOK_PATTERNS = (
        "为什么",
        "凭什么",
        "千万别",
        "一定要",
        "立刻",
        "马上",
        "最后",
        "结果",
        "真相",
        "关键",
        "注意",
        "别再",
        "居然",
        "原来",
        "how",
        "why",
        "secret",
        "mistake",
        "don't",
        "must",
        "stop",
        "wait",
    )

    def _subtitle_canvas_profile(self, project: Project) -> dict[str, int]:
        size = project.metadata.get("source_media_size") or project.metadata.get("size")
        if not size and project.assets:
            size = project.assets[0].metadata.get("size")
        width = int(size[0]) if isinstance(size, list) and len(size) >= 2 else 1080
        height = int(size[1]) if isinstance(size, list) and len(size) >= 2 else 1920
        short_edge = max(320, min(width, height))
        font_size = max(34, min(68, int(round(short_edge * 0.05))))
        margin_x = max(24, min(96, int(round(width * 0.06))))
        margin_bottom = max(72, min(220, int(round(height * 0.1))))
        box_padding = max(8, min(18, int(round(font_size * 0.28))))
        outline_width = max(2, min(4, int(round(font_size / 18.0))))
        return {
            "width": width,
            "height": height,
            "font_size": font_size,
            "margin_x": margin_x,
            "margin_bottom": margin_bottom,
            "box_padding": box_padding,
            "outline_width": outline_width,
        }

    def _subtitle_char_weight(self, text: str) -> int:
        cleaned = re.sub(r"\s+", "", text or "")
        return max(1, len(cleaned))

    def _subtitle_reading_rate(self, cue: SubtitleCue) -> float:
        duration = max(0.1, float(cue.end) - float(cue.start))
        return self._subtitle_char_weight(cue.text) / duration

    def _is_hook_text(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        if any(pattern in normalized for pattern in self._HOOK_PATTERNS):
            return True
        punctuated = normalized.endswith(("?", "？", "!", "！"))
        return punctuated and len(normalized) <= 18

    def _subtitle_style_profile_name(self, project: Project, cue: Optional[SubtitleCue] = None) -> str:
        strategy = str(project.metadata.get("editing_strategy") or "").strip().lower()
        if strategy in {"douyin", "tiktok", "short_video"}:
            return "short_video_attention_v1"
        if cue is not None and self._is_hook_text(cue.text):
            return "short_video_attention_v1"
        return "dynamic_subtitles_v1"

    def _clamp_subtitle_timing(self, project: Project, cue: SubtitleCue) -> None:
        duration = max(0.18, float(cue.end) - float(cue.start))
        char_weight = self._subtitle_char_weight(cue.text)
        reading_rate = char_weight / duration
        min_duration = 0.45 if char_weight <= 6 else 0.75 if char_weight <= 14 else 1.05
        max_duration = 2.4 if char_weight <= 14 else 3.2
        if self._is_hook_text(cue.text):
            min_duration = max(min_duration, 1.0)
            max_duration = max(max_duration, 1.8)
        target_duration = min(max(duration, min_duration), max_duration)
        if reading_rate > 8.5:
            target_duration = min(max_duration, max(target_duration, char_weight / 7.2))
        timeline_cap = float(project.timeline.duration or 0.0)
        cue.end = round(max(cue.start + 0.18, cue.start + target_duration), 3)
        if timeline_cap > 0:
            cue.end = round(min(cue.end, timeline_cap), 3)
        if cue.end <= cue.start:
            cue.end = round(cue.start + 0.18, 3)

    def _key_phrase_from_text(self, text: str) -> Optional[str]:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if not normalized:
            return None
        candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", normalized)
        if not candidates:
            return None
        full_compact = re.sub(r"\s+", "", normalized)
        filtered = [
            item
            for item in candidates
            if re.sub(r"\s+", "", item) != full_compact
        ]
        if not filtered:
            return None
        ranked = sorted(filtered, key=lambda item: (self._is_hook_text(item), len(item)), reverse=True)
        phrase = ranked[0]
        if len(phrase) < 2:
            return None
        return phrase

    def _ensure_emphasis_span(self, cue: SubtitleCue) -> None:
        phrase = self._key_phrase_from_text(cue.text)
        if not phrase:
            return
        if any(span.text == phrase for span in cue.spans):
            return
        leading, _, trailing = cue.text.partition(phrase)
        spans = [
            {
                "id": span.id or f"{cue.id}_span_{index}",
                "text": span.text,
                "color": span.color,
                "bold": span.bold,
                "italic": span.italic,
                "underline": span.underline,
                "effects": [effect for effect in span.effects],
                "metadata": dict(span.metadata or {}),
            }
            for index, span in enumerate(cue.spans, start=1)
            if span.text and cue.text.find(span.text) >= 0
        ]
        if leading:
            spans.append({"id": f"{cue.id}_lead", "text": leading})
        spans.append(
            {
                "id": f"{cue.id}_key",
                "text": phrase,
                "color": "#FFD54F",
                "bold": True,
                "metadata": {"role": "key_phrase"},
            }
        )
        if trailing:
            spans.append({"id": f"{cue.id}_tail", "text": trailing})
        cue.spans = [SubtitleSpan.from_dict(span) for span in spans]

    def _apply_short_video_style(self, project: Project, cue: SubtitleCue, profile: dict[str, int]) -> None:
        requested_position = str(cue.metadata.get("requested_position") or "").strip().lower()
        if requested_position in {"top", "middle", "bottom", "below_faces"}:
            cue.position = requested_position
        else:
            cue.position = cue.position or "middle"
        cue.margin_bottom = float(max(96, int(profile["height"] * 0.135)))
        cue.margin_left = float(max(28, int(profile["width"] * 0.07)))
        cue.margin_right = float(max(28, int(profile["width"] * 0.07)))
        cue.font_size = max(profile["font_size"], 42)
        self._ensure_emphasis_span(cue)
        if self._is_hook_text(cue.text):
            cue.margin_bottom = float(max(80, int(profile["height"] * 0.1)))
            cue.font_size = max(cue.font_size or 0, int(round(profile["font_size"] * 1.1)))
            self._upsert_subtitle_effect(
                cue,
                "slide_in",
                {"direction": "bottom", "duration": 0.16, "distance": 48},
            )
        elif self._subtitle_char_weight(cue.text) <= 10:
            self._upsert_subtitle_effect(
                cue,
                "scale_in",
                {"duration": 0.12},
            )
        else:
            self._upsert_subtitle_effect(
                cue,
                "typewriter",
                {"chars_per_second": 18 if self._is_cjk_heavy(cue.text) else 24},
            )

    def _project_short_video_metrics(self, project: Project) -> dict[str, Any]:
        subtitles = sorted(project.subtitles, key=lambda item: (item.start, item.end, item.id))
        timeline_duration = float(project.timeline.duration or 0.0)
        subtitle_count = len(subtitles)
        first_cue = subtitles[0] if subtitles else None
        first_hook_time = round(float(first_cue.start), 3) if first_cue else None
        avg_subtitle_duration = (
            round(sum(max(0.0, cue.end - cue.start) for cue in subtitles) / subtitle_count, 3)
            if subtitle_count
            else 0.0
        )
        avg_chars_per_second = (
            round(sum(self._subtitle_reading_rate(cue) for cue in subtitles) / subtitle_count, 2)
            if subtitle_count
            else 0.0
        )
        hook_strength = 0.0
        if first_cue is not None:
            hook_bonus = 1.0 if self._is_hook_text(first_cue.text) else 0.45
            timing_bonus = max(0.0, 1.0 - min(float(first_cue.start), 3.0) / 3.0)
            hook_strength = round(min(1.0, hook_bonus * 0.65 + timing_bonus * 0.35), 3)
        subtitle_coverage = 0.0
        if timeline_duration > 0 and subtitles:
            covered = sum(max(0.0, cue.end - cue.start) for cue in subtitles)
            subtitle_coverage = round(min(1.0, covered / timeline_duration), 3)
        pacing_score = 0.0
        if subtitles:
            target_rate = min(1.0, avg_chars_per_second / 6.6) if avg_chars_per_second > 0 else 0.0
            target_duration_score = 1.0 - min(abs(avg_subtitle_duration - 1.25) / 1.25, 1.0)
            pacing_score = round(max(0.0, min(1.0, target_rate * 0.55 + target_duration_score * 0.45)), 3)
        total_score = round(
            min(
                100.0,
                (
                    hook_strength * 35.0
                    + pacing_score * 30.0
                    + min(1.0, subtitle_coverage / 0.72) * 20.0
                    + min(1.0, subtitle_count / max(1.0, timeline_duration / 1.6 if timeline_duration > 0 else 1.0)) * 15.0
                ),
            ),
            1,
        )
        diagnosis: list[str] = []
        if first_hook_time is None:
            diagnosis.append("缺少字幕驱动内容，无法建立前3秒钩子")
        elif first_hook_time > 1.2:
            diagnosis.append("前1秒信息进入偏慢，开场抓人能力不足")
        if subtitle_coverage < 0.55:
            diagnosis.append("有效信息覆盖偏低，空白停顿过多")
        if avg_chars_per_second > 8.8:
            diagnosis.append("字幕阅读压力偏高，观众扫读成本大")
        if avg_subtitle_duration > 2.5:
            diagnosis.append("字幕停留偏长，短视频节奏不够紧")
        if not diagnosis:
            diagnosis.append("节奏、钩子和字幕可读性达到较稳的短视频基线")
        return {
            "target_platform": "douyin",
            "editing_goal": "更好的剪辑效果",
            "hook_strength": hook_strength,
            "pacing_score": pacing_score,
            "subtitle_coverage": subtitle_coverage,
            "avg_subtitle_duration": avg_subtitle_duration,
            "avg_chars_per_second": avg_chars_per_second,
            "first_hook_time": first_hook_time,
            "score": total_score,
            "diagnosis": diagnosis,
        }

    def _normalize_subtitle_timeline(self, project: Project) -> None:
        ordered = sorted(project.subtitles, key=lambda item: (item.start, item.end, item.id))
        for index, cue in enumerate(ordered[:-1]):
            next_cue = ordered[index + 1]
            max_end = round(max(cue.start + 0.18, float(next_cue.start) - 0.04), 3)
            if cue.end > max_end:
                cue.end = max_end
            if cue.end <= cue.start:
                cue.end = round(cue.start + 0.18, 3)
        project.subtitles = ordered

    def _is_cjk_heavy(self, text: str) -> bool:
        if not text:
            return False
        cjk_chars = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        return cjk_chars >= max(2, int(len(text) * 0.3))

    def _split_subtitle_text(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if not normalized:
            return []
        parts = [
            item.strip()
            for item in re.findall(r"[^。！？!?；;，,、…]+[。！？!?；;，,、…]*", normalized)
        ]
        if not parts:
            parts = [normalized]
        limit = 18 if self._is_cjk_heavy(normalized) else 42
        chunks: list[str] = []
        for part in parts:
            if self._subtitle_char_weight(part) <= limit:
                chunks.append(part)
                continue
            if " " in part:
                words = part.split(" ")
                current: list[str] = []
                for word in words:
                    candidate = " ".join([*current, word]).strip()
                    if current and self._subtitle_char_weight(candidate) > limit:
                        chunks.append(" ".join(current).strip())
                        current = [word]
                    else:
                        current.append(word)
                if current:
                    chunks.append(" ".join(current).strip())
                continue
            cursor = 0
            while cursor < len(part):
                chunks.append(part[cursor : cursor + limit].strip())
                cursor += limit
        merged: list[str] = []
        for chunk in chunks:
            if not chunk:
                continue
            if merged and self._subtitle_char_weight(chunk) <= 4:
                merged[-1] = f"{merged[-1]}{chunk}"
            else:
                merged.append(chunk)
        return merged

    def _expand_transcribed_segment(
        self, start: float, end: float, text: str
    ) -> list[tuple[float, float, str]]:
        normalized = self._normalize_transcribed_text(text)
        chunks = self._split_subtitle_text(normalized)
        if not normalized:
            return []
        if len(chunks) <= 1:
            return [(float(start), float(end), normalized)]
        total_duration = max(0.0, float(end) - float(start))
        min_duration = 0.22
        if total_duration <= min_duration * len(chunks):
            return [(float(start), float(end), normalized)]
        weights = [float(self._subtitle_char_weight(chunk)) for chunk in chunks]
        weight_sum = sum(weights) or float(len(chunks))
        durations = [max(min_duration, total_duration * (weight / weight_sum)) for weight in weights]
        overflow = sum(durations) - total_duration
        if overflow > 0:
            reducible = [max(0.0, duration - min_duration) for duration in durations]
            reducible_sum = sum(reducible)
            if reducible_sum <= 0:
                return [(float(start), float(end), normalized)]
            durations = [
                duration - (overflow * (capacity / reducible_sum) if capacity > 0 else 0.0)
                for duration, capacity in zip(durations, reducible)
            ]
        cursor = float(start)
        segments: list[tuple[float, float, str]] = []
        for index, chunk in enumerate(chunks):
            segment_end = float(end) if index == len(chunks) - 1 else cursor + durations[index]
            if segment_end <= cursor:
                continue
            segments.append((round(cursor, 3), round(segment_end, 3), chunk))
            cursor = segment_end
        return segments or [(float(start), float(end), normalized)]

    def _upsert_subtitle_effect(
        self,
        cue: SubtitleCue,
        kind: str,
        parameters: dict[str, Any],
        *,
        replace_existing: bool = False,
    ) -> None:
        existing = next((fx for fx in cue.effects if fx.kind == kind), None)
        if existing is None:
            cue.effects.append(SubtitleEffect(kind=kind, parameters=dict(parameters)))
            return
        if replace_existing:
            existing.parameters = dict(parameters)

    def _recommended_subtitle_effects(
        self, cue: SubtitleCue, profile: dict[str, int]
    ) -> list[tuple[str, dict[str, Any]]]:
        duration = max(0.0, float(cue.end) - float(cue.start))
        char_weight = self._subtitle_char_weight(cue.text)
        effects: list[tuple[str, dict[str, Any]]] = [
            (
                "outline",
                {"color": "#101010", "width": profile["outline_width"]},
            ),
            (
                "background_box",
                {
                    "color": "#101010",
                    "opacity": 150 if char_weight <= 16 else 132,
                    "padding": profile["box_padding"],
                },
            ),
            ("fade_in", {"duration": 0.12 if duration <= 1.1 else 0.18}),
            ("fade_out", {"duration": 0.12 if duration <= 1.1 else 0.18}),
        ]
        if char_weight <= 12 and duration <= 1.4:
            effects.append(("scale_in", {"duration": 0.14}))
        return effects

    def _apply_auto_style_to_cue(self, project: Project, cue: SubtitleCue) -> None:
        profile = self._subtitle_canvas_profile(project)
        self._clamp_subtitle_timing(project, cue)
        if cue.position:
            cue.metadata["requested_position"] = cue.position
        if not cue.position:
            cue.position = "middle"
        if cue.margin_left is None:
            cue.margin_left = float(profile["margin_x"])
        if cue.margin_right is None:
            cue.margin_right = float(profile["margin_x"])
        if cue.margin_bottom is None or (
            cue.margin_bottom <= 0 and cue.metadata.get("source") == "transcribe_audio"
        ):
            cue.margin_bottom = float(profile["margin_bottom"])
        if cue.font_size is None:
            cue.font_size = profile["font_size"]
        style_profile = self._subtitle_style_profile_name(project, cue)
        if style_profile == "short_video_attention_v1":
            self._apply_short_video_style(project, cue, profile)
        for kind, parameters in self._recommended_subtitle_effects(cue, profile):
            existing = next((fx for fx in cue.effects if fx.kind == kind), None)
            if existing is None:
                cue.effects.append(SubtitleEffect(kind=kind, parameters=dict(parameters)))
        cue.metadata["auto_style_profile"] = style_profile

    def _apply_auto_style_to_subtitles(
        self, project: Project, subtitle_ids: Optional[Iterable[str]] = None
    ) -> None:
        selected_ids = set(subtitle_ids or [])
        for cue in project.subtitles:
            if selected_ids and cue.id not in selected_ids:
                continue
            self._apply_auto_style_to_cue(project, cue)
        self._normalize_subtitle_timeline(project)
        metrics = self._project_short_video_metrics(project)
        project.metadata["editing_goal"] = "better_editing_effect"
        project.metadata["target_platform"] = "douyin"
        project.metadata["editing_strategy"] = "short_video"
        project.metadata["short_video_metrics"] = metrics
        project.metadata["auto_style_profile"] = self._subtitle_style_profile_name(project)
