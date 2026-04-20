"""
特效推荐模块
根据文案和时间戳，用 LLM 推荐合适的视频特效
核心思路：语义场景匹配 + 保守推荐策略（适合口播类视频）
【2025-04-10 更新】新增开场特效逻辑：每个视频必须有一个开场特效
"""

# pyright: reportMissingTypeArgument=false

import json
import re
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import SecretStr


# ==================== 配置加载 ====================

_effects_config: dict | None = None
_curated_effects_config: dict | None = None


def load_effects_config() -> dict:
    """加载完整特效配置文件（向后兼容）"""
    global _effects_config
    if _effects_config is None:
        config_path = Path(__file__).parent / "config" / "effects.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            _effects_config = json.load(f)
    assert _effects_config is not None
    return _effects_config


def load_curated_effects() -> dict:
    """加载精选特效配置文件（推荐用于口播视频）"""
    global _curated_effects_config
    if _curated_effects_config is None:
        config_path = Path(__file__).parent / "config" / "effects_curated.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            _curated_effects_config = json.load(f)
    assert _curated_effects_config is not None
    return _curated_effects_config


def get_all_effect_names() -> list[str]:
    """获取所有特效名称（从完整配置，用于验证）"""
    config = load_effects_config()
    names: list[str] = []
    for effects in config.get('scene_effects', {}).values():  # type: ignore[union-attr]
        names.extend(effects)  # type: ignore[arg-type]
    for effects in config.get('character_effects', {}).values():  # type: ignore[union-attr]
        names.extend(effects)  # type: ignore[arg-type]
    return names


def get_opening_effect_names() -> list[str]:
    """获取所有开场特效名称"""
    config = load_curated_effects()
    opening_effects = config.get('opening_effects', {}).get('effects', {})
    return list(opening_effects.keys())


def format_effects_for_prompt() -> str:
    """
    将精选特效格式化为 prompt 友好的语义映射表
    帮助 LLM 根据文案语义精确匹配特效
    """
    config = load_curated_effects()
    scenes = config.get('semantic_scenes', {})
    character = config.get('character_effects', {})
    opening = config.get('opening_effects', {})
    rules = config.get('recommendation_rules', {})

    lines: list[str] = []
    lines.append("\n## 口播视频精选特效（语义场景映射表）")
    lines.append(f"\n**推荐策略**: {rules.get('default_strategy', '保守策略')}")
    lines.append(f"**内容特效最多**: {rules.get('max_effects_per_video', 5)} 个")
    lines.append(f"**开场特效**: 必须1个，独立于内容特效")
    lines.append("\n**三不原则**: 不遮挡人脸、不干扰观看、不过度花哨")

    lines.append("\n### 开场特效（每个视频必须选一个）")
    lines.append(f"说明: {opening.get('description', '')}")
    duration_rules = opening.get('duration_rules', {})
    lines.append(f"时长限制: {duration_rules.get('min_seconds', 1)}-{duration_rules.get('max_seconds', 3)}秒，必须短而有力！")
    opening_effects = opening.get('effects', {})
    for effect_name, effect_data in opening_effects.items():
        desc = effect_data.get('description', '')
        best_for = effect_data.get('best_for', [])
        duration_hint = effect_data.get('duration_hint', '2秒')
        lines.append(f"  - {effect_name}: {desc}")
        lines.append(f"    适合: {', '.join(best_for)} | 建议时长: {duration_hint}")

    lines.append("\n### 场景特效（根据文案语义选择）")
    for scene_name, scene_data in scenes.items():
        desc = scene_data.get('description', '')
        triggers = scene_data.get('trigger_words', [])
        effects = scene_data.get('effects', [])

        lines.append(f"\n【{scene_name}】")
        lines.append(f"  适用场景: {desc}")
        lines.append(f"  触发词: {', '.join(triggers[:6])}...")
        lines.append(f"  可选特效: {', '.join(effects)}")

    lines.append("\n### 人物特效（点缀使用）")
    char_desc = character.get('description', '')
    char_effects = character.get('effects', {})
    lines.append(f"{char_desc}")
    for effect_name, effect_desc in char_effects.items():
        lines.append(f"  - {effect_name}: {effect_desc}")

    return "\n".join(lines)


# ==================== ASR 格式转换 ====================


def convert_asr_to_segments(asr_result: dict) -> list[dict]:
    """
    将 ASR 输出转换为简化格式，支持按标点拆分长段

    当 ASR 结果包含 words 级别的时间戳时，会按标点符号将
    一个大 segment 拆分为多个子段落，使 LLM 能更精确地
    推荐每个子段的特效及特效时长。

    输入: ASR 原始 JSON
    输出: [{"text": "...", "start": 0, "end": 3200000}, ...]
    (start/end 单位为微秒)
    """
    # 中文断句标点
    split_pattern = re.compile(r'[，。！？；、,.!?;]')

    segments: list[dict] = []
    for seg in asr_result.get("segments", []):
        words = seg.get("words", [])

        if not words:
            # 没有 words 信息，直接用 segment 级别
            segments.append({
                "text": seg["text"],
                "start": int(seg["start"] * 1_000_000),
                "end": int(seg["end"] * 1_000_000),
            })
            continue

        # 按 words 拆分为子段落
        sub_text = ""
        sub_start: float | None = None
        sub_words: list[dict] = []

        for w in words:
            word_text = w["word"]
            word_start = w["start"]
            word_end = w["end"]

            if sub_start is None:
                sub_start = word_start

            sub_text += word_text
            sub_words.append(w)

            # 遇到断句标点，切分
            if split_pattern.search(word_text) and sub_start is not None:
                segments.append({
                    "text": sub_text,
                    "start": int(sub_start * 1_000_000),
                    "end": int(word_end * 1_000_000),
                })
                sub_text = ""
                sub_start = None
                sub_words = []

        # 剩余部分
        if sub_text and sub_start is not None:
            segments.append({
                "text": sub_text,
                "start": int(sub_start * 1_000_000),
                "end": int(sub_words[-1]["end"] * 1_000_000),
            })

    return segments


def print_segments(segments: list[dict]) -> None:
    """打印拆分后的段落和时间戳，便于调试"""
    print("\n===== ASR 段落拆分结果 =====")
    for i, seg in enumerate(segments):
        start_sec = seg["start"] / 1_000_000
        end_sec = seg["end"] / 1_000_000
        duration = end_sec - start_sec
        print(f"  [{i}] {start_sec:.2f}s - {end_sec:.2f}s (时长{duration:.2f}s): {seg['text']}")
    print(f"共 {len(segments)} 个子段落\n")


# ==================== LLM 推荐逻辑 ====================


def extract_opening_text(segments: list[dict], max_chars: int = 100) -> str:
    """
    从 segments 中提取开头的文案用于分析开场特效

    Args:
        segments: 时间段落列表
        max_chars: 最大字符数，默认100个字符

    Returns:
        开头文案
    """
    if not segments:
        return ""

    # 取前几个段落，凑够 max_chars 个字符
    opening_parts = []
    total_chars = 0

    for seg in segments:
        text = seg.get("text", "")
        if total_chars + len(text) <= max_chars:
            opening_parts.append(text)
            total_chars += len(text)
        else:
            # 只取剩余需要的部分
            remaining = max_chars - total_chars
            if remaining > 0:
                opening_parts.append(text[:remaining])
            break

    return "".join(opening_parts)


def recommend_opening_effect(
    script: str,
    segments: list[dict],
    llm: ChatOpenAI | None = None,
) -> dict | None:
    """
    【第一步】根据文案开头，推荐开场特效

    Args:
        script: 完整文案
        segments: 时间段落列表
        llm: ChatOpenAI 实例

    Returns:
        开场特效字典 {"effect_title": "...", "start": 0, "end": 2000000, "is_opening": true}
        如果无法确定，返回默认"开幕"特效
    """
    # 加载配置
    curated_config = load_curated_effects()
    opening_config = curated_config.get('opening_effects', {})
    duration_rules = opening_config.get('duration_rules', {})
    max_duration_sec = duration_rules.get('max_seconds', 3)
    opening_effects = opening_config.get('effects', {})

    # 提取开头文案
    opening_text = extract_opening_text(segments, max_chars=100)

    # 格式化开场特效列表
    opening_lines = ["\n### 可选开场特效"]
    for name, data in opening_effects.items():
        desc = data.get('description', '')
        best_for = data.get('best_for', [])
        duration_hint = data.get('duration_hint', '2秒')
        opening_lines.append(f"- {name}: {desc} (适合: {', '.join(best_for)}, 建议时长: {duration_hint})")

    opening_formatted = "\n".join(opening_lines)

    # 构造 prompt
    prompt = f"""你是一个专业的视频开场特效推荐助手。

## 任务
根据视频文案的开头内容，推荐**1个**最合适的开场特效。

## 开场特效时长规则（非常重要）
- **绝对不要超过 {max_duration_sec} 秒**
- 开场特效要短而有力，目的是引入，不是抢戏
- 时长必须控制在 1-{max_duration_sec} 秒之间
- 推荐：1-2秒最佳

{opening_formatted}

## 输入数据

**文案开头**（前100字）：
{opening_text}

**完整文案**（参考）：
{script[:200]}...

**视频第一段时间戳**：
- 开始: 0μs
- 第一段结束: {segments[0]['end'] if segments else 3000000}μs

## 分析要求

1. 分析文案开头的主题和氛围
2. 判断哪个开场特效最匹配
3. **自行决定时长**（必须在1-{max_duration_sec}秒内）

## 输出格式

只返回一个 JSON 对象：
```json
{{
  "effect_title": "特效名称",
  "duration_seconds": 2
}}
```

**注意**：
- effect_title 必须是上面列表中的精确名称
- duration_seconds 必须是 1-{max_duration_sec} 之间的整数
- 不要返回任何解释，只返回 JSON
"""

    # 使用 LLM
    if llm is None:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=SecretStr("sk-stNCnaSdsAm0cJ9nDFwfCXQqpawyKcEKxbdIstKTEzAmBex8"),
            base_url="https://happyapi.org/v1"
        )

    try:
        response = llm.invoke(prompt)
        raw = response.content
        content = raw.strip() if isinstance(raw, str) else str(raw)

        print(f"\n===== 开场特效 LLM 返回 =====\n{content}\n===== 结束 =====\n")

        # 解析 JSON
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从代码块中提取
            match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
            if match:
                result = json.loads(match.group(1))
            else:
                raise ValueError("无法解析 JSON")

        # 验证并构建返回
        effect_title = result.get("effect_title", "开幕")
        duration_sec = min(max(result.get("duration_seconds", 2), 1), max_duration_sec)

        # 转换为微秒
        duration_us = duration_sec * 1_000_000

        return {
            "effect_title": effect_title,
            "start": 0,
            "end": duration_us,
            "is_opening": True,
        }

    except Exception as e:
        print(f"Warning: 开场特效推荐失败 ({e})，使用默认开幕特效")
        # 默认返回"开幕"特效，2秒
        return {
            "effect_title": "开幕",
            "start": 0,
            "end": 2_000_000,
            "is_opening": True,
        }


def recommend_content_effects(
    script: str,
    segments: list[dict],
    opening_end_us: int,
    llm: ChatOpenAI | None = None,
) -> list[dict]:
    """
    【第二步】根据完整文案，推荐内容特效（不包括开场特效）

    Args:
        script: 完整文案
        segments: 时间段落列表
        opening_end_us: 开场特效结束时间（微秒）
        llm: ChatOpenAI 实例

    Returns:
        内容特效列表
    """
    # 加载精选特效配置
    curated_config = load_curated_effects()
    max_effects = curated_config.get('recommendation_rules', {}).get('max_effects_per_video', 5)

    # 格式化特效列表
    effects_formatted = format_effects_for_prompt()

    # 格式化 segments（过滤掉开场特效已经覆盖的时间段）
    segments_text_lines = []
    for seg in segments:
        seg_end = seg['end']
        seg_start = seg['start']

        # 如果整个段落都在开场特效期间，跳过
        if seg_end <= opening_end_us:
            continue

        # 如果部分重叠，显示但不强制推荐特效
        segments_text_lines.append(
            f"- [{seg_start:,}μs - {seg_end:,}μs]: {seg['text']}"
        )

    segments_text = "\n".join(segments_text_lines)

    # 构造 prompt
    prompt = f"""你是一个专业的抖音短视频特效推荐助手。

## 核心原则

抖音短视频节奏快、用户注意力短，**必须有视觉节奏点来留住用户**。

**节奏策略：积极推荐 > 保守观望**

**三不原则**：
1. 不遮挡人脸（不用边框录制、分屏）
2. 不干扰观看（不用爆炸、过度故障）
3. 不过度花哨（不用漫画涂鸦、电子屏幕）

## 重要说明

- 开场特效（0-{opening_end_us/1_000_000:.1f}秒）已经单独处理
- 你现在只需要推荐**内容特效**，从 {opening_end_us/1_000_000:.1f} 秒之后开始
- 内容特效可以和开场特效重叠，这是允许的
- **抖音短视频必须至少1-2个内容特效**，制造视觉节奏感

## 推荐逻辑

第一步：识别文案中的**节奏转折点**
- 话题切换、重点强调、数据/事实陈述、结论总结等位置
- 这些位置需要视觉节奏变化

第二步：识别文案中的**语义场景**
- 查看每段文案是否包含"触发词"
- 判断属于哪个语义场景（怀旧日常、温暖治愈、梦幻浪漫、自然季节、科技知识、欢快庆祝、故事叙事、强调转折、医学科普）
- **医学科普类内容**（前列腺、健康、身体、症状、治疗等关键词）→ 使用"丁达尔光线""光晕""细闪""电影感"

第三步：积极推荐策略
- **必须至少推荐1个内容特效**（最多 {max_effects} 个）
- 宁可稍微多加，也不要完全不加
- 在以下位置优先加特效：
  - 话题/观点转折处
  - 重点数据或结论处
  - 新知识点引入处
  - 段落/章节分界处
- 特效之间要有节奏感，不要太密集（间隔5-10秒以上）

{effects_formatted}

## 输入数据

**完整文案**：
{script}

**段落时间戳**（微秒，开场特效之后的段落）：
{segments_text}

## 输出要求

返回 JSON 数组，每个元素包含：
- effect_title: 特效名称（必须来自上面"可选特效"列表中的精确名称）
- start: 开始时间（微秒，使用输入段落的时间戳）
- end: 结束时间（微秒，使用输入段落的时间戳）

**输出规则**：
1. **必须至少推荐1个内容特效，推荐2-3个最佳**
2. 如果文案确实非常平淡，最少也要返回1个轻微特效（如"光晕""细闪"）
3. 内容特效最多 {max_effects} 个（开场特效已单独处理，不计入）
4. 优先使用场景特效，人物特效仅在表达特定情绪时点缀使用
5. 特效时长不要太短（至少覆盖2秒以上）

**示例输出**：
```json
[
  {{"effect_title": "丁达尔光线", "start": 10000000, "end": 15000000}},
  {{"effect_title": "光晕", "start": 30000000, "end": 35000000}}
]
```

**抖音短视频必须有节奏感，不要返回空数组！**
"""

    # 使用 LLM
    if llm is None:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=SecretStr("sk-stNCnaSdsAm0cJ9nDFwfCXQqpawyKcEKxbdIstKTEzAmBex8"),
            base_url="https://happyapi.org/v1"
        )

    response = llm.invoke(prompt)
    raw = response.content
    content = raw.strip() if isinstance(raw, str) else str(raw)

    print(f"\n===== 内容特效 LLM 返回 =====\n{content}\n===== 结束 =====\n")

    # 提取 JSON
    try:
        effects = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", content)
        if match:
            effects = json.loads(match.group(1))
        else:
            print(f"Warning: 无法解析 LLM 返回的 JSON，原始内容: {content}")
            return []

    # 验证返回格式
    if not isinstance(effects, list):
        print(f"Warning: LLM 返回的不是列表类型: {type(effects)}")
        return []

    # 应用最大特效数量限制
    if len(effects) > max_effects:
        print(f"Warning: LLM 返回 {len(effects)} 个特效，超过限制 {max_effects}，只保留前 {max_effects} 个")
        effects = effects[:max_effects]

    return effects


def recommend_effects(
    script: str,
    segments: list[dict],
    llm: ChatOpenAI | None = None,
) -> list[dict]:
    """
    根据文案和时间戳，用 LLM 推荐特效列表（口播视频优化版）
    【2025-04-10 更新】新增两步推理：
    1. 先推荐开场特效（必须有，独立计数）
    2. 再推荐内容特效（最多5个）

    Args:
        script: 完整文案（full_text）
        segments: 时间段落列表 [{"text": "...", "start": 0, "end": 3200000}, ...]
        llm: ChatOpenAI 实例，默认会创建新实例

    Returns:
        特效列表 [{"effect_title": "...", "start": 0, "end": 3200000, "is_opening": true/false}, ...]
        开场特效会有 is_opening: true 标识
    """
    print("\n===== 开始两步特效推荐 =====")

    # ==================== 第一步：推荐开场特效 ====================
    print("\n【第一步】推荐开场特效...")
    opening_effect = recommend_opening_effect(script, segments, llm)

    # 确保有开场特效（默认回退）
    if opening_effect is None:
        opening_effect = {
            "effect_title": "开幕",
            "start": 0,
            "end": 2_000_000,
            "is_opening": True,
        }

    opening_title = str(opening_effect['effect_title'])
    opening_end_us = int(opening_effect['end'])
    print(f"开场特效推荐结果: {opening_title} ({opening_end_us/1_000_000:.1f}秒)")

    # ==================== 第二步：推荐内容特效 ====================
    print("\n【第二步】推荐内容特效...")
    content_effects = recommend_content_effects(script, segments, opening_end_us, llm)
    print(f"内容特效推荐结果: {len(content_effects)} 个")

    # ==================== 合并结果并验证 ====================
    all_effects = [opening_effect] + content_effects

    # 获取有效特效名称集合
    valid_names = set(get_all_effect_names())
    valid_opening_names = set(get_opening_effect_names())
    all_valid_names = valid_names | valid_opening_names

    # 验证所有特效
    validated = []
    for item in all_effects:
        if isinstance(item, dict) and "effect_title" in item:
            title = item["effect_title"]
            if title in all_valid_names:
                validated.append({
                    "effect_title": title,
                    "start": int(item.get("start", 0)),
                    "end": int(item.get("end", 0)),
                    "is_opening": item.get("is_opening", False),
                })
            else:
                print(f"Warning: 特效名称无效，被过滤: '{title}'")
        else:
            print(f"Warning: 格式不正确的元素被过滤: {item}")

    # 统计
    opening_count = sum(1 for e in validated if e.get("is_opening"))
    content_count = len(validated) - opening_count

    print(f"\n===== 特效推荐完成 =====")
    print(f"开场特效: {opening_count} 个")
    print(f"内容特效: {content_count} 个")
    print(f"总计: {len(validated)} 个")

    return validated


# ==================== 便捷函数 ====================


def recommend_effects_from_asr(
    asr_result: dict,
    llm: ChatOpenAI | None = None,
) -> list[dict]:
    """
    直接从 ASR 结果推荐特效（一步到位）

    Args:
        asr_result: ASR 模型输出的原始 JSON
        llm: ChatOpenAI 实例（可选）

    Returns:
        特效列表 [{"effect_title": "...", "start": 0, "end": 3200000}, ...]
    """
    segments = convert_asr_to_segments(asr_result)
    print_segments(segments)
    script = asr_result.get("full_text", "")

    return recommend_effects(
        script=script,
        segments=segments,
        llm=llm,
    )
