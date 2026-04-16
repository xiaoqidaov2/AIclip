"""
ASR 工具 - 使用 faster-whisper 提取视频中的文案与时间戳
输出格式与 capcut_video_tool.py 中的 asr_result 一致，方便复制粘贴
"""

import re
import pprint
from datetime import datetime

from faster_whisper import WhisperModel


def smart_segment_by_words(words_list, max_chars=18, min_chars=4):
    """
    基于词级别时间戳进行智能分段
    
    Args:
        words_list: 词列表，每个元素包含 word, start, end, prob
        max_chars: 单个片段最大字数（默认 18）
        min_chars: 单个片段最小字数（默认 4）
    
    Returns:
        分段后的片段列表
    """
    if not words_list:
        return []
    
    segments = []
    current_words = []
    current_text = ""
    
    # 定义标点符号（分段依据）
    split_punctuation = set(['，', '。', '！', '？', '、', '；', '：', ',', '.', '!', '?', ';', ':'])
    
    for word_info in words_list:
        word = word_info['word']
        current_words.append(word_info)
        current_text += word
        
        # 判断是否应该分段
        should_split = False
        
        # 1. 遇到标点符号
        if word in split_punctuation:
            should_split = True
        # 2. 超过最大字数限制
        elif len(current_text) >= max_chars:
            should_split = True
        
        if should_split:
            # 创建新片段
            text = current_text.strip()
            if text:  # 确保不为空
                segments.append({
                    'text': text,
                    'start': round(current_words[0]['start'], 2),
                    'end': round(current_words[-1]['end'], 2),
                })
            
            current_words = []
            current_text = ""
    
    # 处理剩余的词
    if current_words:
        text = current_text.strip()
        if text:
            segments.append({
                'text': text,
                'start': round(current_words[0]['start'], 2),
                'end': round(current_words[-1]['end'], 2),
            })
    
    # 后处理：合并过短的片段
    merged_segments = []
    for seg in segments:
        if merged_segments and len(seg['text']) < min_chars:
            # 合并到上一个片段
            merged_segments[-1]['text'] += seg['text']
            merged_segments[-1]['end'] = seg['end']
        else:
            merged_segments.append(seg)
    
    return merged_segments


def run_asr(
    file_path: str = r"",
    model_size: str = "large-v3",
    language: str | None = None,
    device: str = "cuda",
    compute_type: str = "float16",
):
    """对视频/音频文件进行 ASR，打印 asr_result 格式的字典，方便复制粘贴"""

    print(f"正在加载模型 {model_size} (device={device}, compute_type={compute_type})...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print(f"正在转录: {file_path}...")
    segments_iter, info = model.transcribe(
        file_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    segments = list(segments_iter)
    detected_language = info.language
    print(f"检测到语言: {detected_language}, 共 {len(segments)} 个片段")

    # 收集所有词的时间戳（用于智能分段）
    all_words = []
    full_text_parts = []
    
    for seg in segments:
        if seg.words:
            for w in seg.words:
                all_words.append({
                    "word": w.word,
                    "start": round(float(w.start), 2),
                    "end": round(float(w.end), 2),
                    "prob": round(float(w.probability), 2),
                })
        full_text_parts.append(seg.text.strip())
    
    # 使用智能分段
    result_segments = smart_segment_by_words(all_words, max_chars=18, min_chars=4)
    
    # 如果没有分段结果，使用原始分段
    if not result_segments:
        for seg in segments:
            result_segments.append({
                "text": seg.text.strip(),
                "start": round(float(seg.start), 2),
                "end": round(float(seg.end), 2),
            })
    
    duration = round(float(segments[-1].end), 2) if segments else 0.0

    asr_result = {
        "task_id": f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "language": detected_language,
        "duration": duration,
        "segments": result_segments,
        "full_text": "".join(full_text_parts),
        "speakers": None,
        "hotwords_used": None,
    }

    print("\n" + "=" * 60)
    print("复制以下内容到 asr_result:")
    print("=" * 60)
    pprint.pprint(asr_result, width=120, sort_dicts=False)

    return asr_result


if __name__ == "__main__":
    # ====== 在这里修改路径和参数 ======
    run_asr(
        file_path=r"C:\Users\64061\Downloads\fusion (13).mp4",
        model_size="large-v3",
        language="zh",
        device="cpu",
        compute_type="int8",
    )
