"""
CapCut Mate - 核心视频处理逻辑
"""

import sys
import io
from pathlib import Path
from typing import Any

# 设置 UTF-8 编码以支持 Emoji 打印
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 确保可以导入项目模块
# 这里的路径处理需要考虑 core 目录是在项目根目录下
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(project_root / "utils" / "capcut_mate") not in sys.path:
    sys.path.insert(0, str(project_root / "utils" / "capcut_mate"))

# 初始化日志配置
try:
    from utils.capcut_mate.src.utils.logger import LOGGING_CONFIG  # noqa: F401
except ImportError:
    pass

from agents.main_graph import VideoWorkflow

def create_video(
    video_files: list[str],
    script: str,
    timestamps: list[dict] | None = None,
    draft_name: str = "quick_video",
    max_effects: int = 5,
    max_stickers: int = 3,
) -> dict:
    """
    快速创建视频的核心逻辑
    
    参数:
        video_files: 视频文件路径列表
        script: 视频文案
        timestamps: 文案时间戳（可选，默认 30s 单片段）
        draft_name: 草稿名称
        max_effects: 最大特效数量
        max_stickers: 最大贴纸数量
    
    返回:
        执行结果字典
    """
    print("🎬 CapCut Mate 快速视频生成")
    print("=" * 60)

    # 转换视频文件格式
    formatted_files = [{"path": f, "optional": False} for f in video_files]

    # 如果没有时间戳，创建一个简单的
    if not timestamps:
        timestamps = [{"text": script, "start": 0, "end": 30.0}]

    # 执行完整工作流
    print(f"\n📁 草稿名称: {draft_name}")
    print(f"🎥 视频文件: {len(video_files)}个")
    print(f"📝 文案长度: {len(script)}字")
    print(f"✨ 最大特效: {max_effects}个")
    print(f"🎨 最大贴纸: {max_stickers}个")

    workflow = VideoWorkflow()

    print("\n" + "-" * 60)
    print("开始执行工作流...")
    print("-" * 60)

    result = workflow.invoke(
        draft_name=draft_name,
        video_files=formatted_files,
        video_script=script,
        timestamps=timestamps,
        max_effects=max_effects,
        max_stickers=max_stickers
    )

    print("\n" + "=" * 60)
    if result.get("success"):
        print("✅ 视频生成成功！")
        print(f"📁 草稿ID: {result.get('draft_id')}")
        print(f"📂 草稿路径: {result.get('draft_path')}")
        print(f"🎬 输出视频: {result.get('final_video_path')}")

        transitions = result.get("transitions", [])
        effects = result.get("effects", [])
        stickers = result.get("stickers", [])

        print(f"\n🎭 转场效果 ({len(transitions)}个):")
        for t in transitions:
            start = t.get('start_time', 0)
            duration = t.get('duration', 0)
            if t.get("type") == "opening":
                print(f"  • 开场: {t['effect_name']} {start:.1f}s-{start+duration:.1f}s ({t.get('reason', '')})")
            else:
                print(f"  • 转场: {t['effect_name']} {start:.1f}s-{start+duration:.1f}s ({t.get('reason', '')})")

        print(f"\n✨ 视觉特效 ({len(effects)}个):")
        for e in effects:
            start = e.get('start_time', 0)
            duration = e.get('duration', 0)
            print(f"  • {e['effect_name']}: {start:.1f}s-{start+duration:.1f}s ({e.get('reason', '')})")

        print(f"\n🎨 贴纸 ({len(stickers)}个):")
        for s in stickers:
            start = s.get('start_time', 0)
            duration = s.get('duration', 0)
            print(f"  • {s.get('sticker_type', '未知贴纸')}: {start:.1f}s-{start+duration:.1f}s ({s.get('reason', '')})")
    else:
        print(f"❌ 视频生成失败: {result.get('error')}")

    return result
