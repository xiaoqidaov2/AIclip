"""
CapCut Mate - 快速视频生成入口

独立运行的脚本入口，使用 LangGraph 编排的完整工作流。

使用方法:
    python quick_video.py --input timestamps.json --videos video1.mp4 video2.mp4

或者:
    from quick_video import create_video
    create_video(
        video_files=["video1.mp4"],
        script="文案内容",
        timestamps=[{"text": "第一句", "start": 0, "end": 3.0}]
    )
"""

import argparse
import json
import sys
from pathlib import Path

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

from core.video_processor import create_video
from tools.asr_utils import parse_asr_output



def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="CapCut Mate - 快速视频生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用 ASR 输出文件生成视频
  python quick_video.py --input asr_output.json --videos video1.mp4

  # 指定草稿名称
  python quick_video.py -i timestamps.json -v v1.mp4 v2.mp4 -n my_draft
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="ASR 输出 JSON 文件路径（支持 ASR 原始格式或简单 [{text,start,end}] 格式）"
    )

    parser.add_argument(
        "--videos", "-v",
        nargs="+",
        required=True,
        help="视频文件路径列表"
    )

    parser.add_argument(
        "--draft-name", "-n",
        default="quick_video",
        help="草稿名称"
    )

    parser.add_argument(
        "--max-effects", "-e",
        type=int,
        default=5,
        help="最大特效数量（默认5）"
    )


    parser.add_argument(
        "--max-stickers", "-s",
        type=int,
        default=3,
        help="最大贴纸数量（默认3）"
    )

    args = parser.parse_args()

    # 加载并解析 ASR 输出
    with open(args.input, 'r', encoding='utf-8') as f:
        asr_data = json.load(f)

    script, timestamps = parse_asr_output(asr_data)

    print(f"📋 解析 ASR 输出: {len(timestamps)} 个片段, 文案 {len(script)} 字")
    for ts in timestamps:
        print(f"   [{ts['start']:.1f}s - {ts['end']:.1f}s] {ts['text']}")

    create_video(
        video_files=args.videos,
        script=script,
        timestamps=timestamps,
        draft_name=args.draft_name,
        max_effects=args.max_effects,
        max_stickers=args.max_stickers,
    )


if __name__ == "__main__":
    main()
