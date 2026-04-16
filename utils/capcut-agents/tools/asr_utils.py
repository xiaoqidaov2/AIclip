"""ASR 输出解析工具"""


def parse_asr_output(asr_data: dict | list) -> tuple[str, list[dict]]:
    """
    解析 ASR 输出，提取 script 和 timestamps

    支持两种格式:
    1. ASR 原始输出: 含 full_text / segments[].words 的完整结构
    2. 简单格式: [{text, start, end}, ...] 列表（兼容旧格式）

    返回:
        (script, timestamps) 元组
    """
    # 兼容简单列表格式
    if isinstance(asr_data, list):
        script = "".join(seg.get("text", "") for seg in asr_data)
        return script, asr_data

    # ASR 原始输出格式
    script = asr_data.get("full_text", "")
    segments = asr_data.get("segments", [])

    if not segments:
        return script, [{"text": script, "start": 0, "end": 30.0}]

    # 从 words 切分句子级时间戳
    timestamps = []

    for seg in segments:
        words = seg.get("words", [])
        if not words:
            timestamps.append({
                "text": seg.get("text", ""),
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
            })
            continue

        current_text = ""
        current_start = None
        current_end = None

        for w in words:
            word = w.get("word", "")
            start = w.get("start", 0)
            end = w.get("end", 0)

            if current_start is None:
                current_start = start

            current_text += word
            current_end = end

            # 遇到标点就切分
            if word and word[-1] in "，。！？、；,.!?;":
                timestamps.append({
                    "text": current_text,
                    "start": current_start,
                    "end": current_end,
                })
                current_text = ""
                current_start = None
                current_end = None

        # 处理剩余内容
        if current_text:
            timestamps.append({
                "text": current_text,
                "start": current_start or 0,
                "end": current_end or 0,
            })

    # 合并过短的片段（< 2秒），避免碎片化
    merged = []
    for ts in timestamps:
        duration = ts["end"] - ts["start"]
        if merged and duration < 2.0:
            prev = merged[-1]
            prev["text"] += ts["text"]
            prev["end"] = ts["end"]
        else:
            merged.append(ts.copy())

    # 补充 script（如果 full_text 为空则从时间戳拼接）
    if not script:
        script = "".join(ts["text"] for ts in merged)

    return script, merged
