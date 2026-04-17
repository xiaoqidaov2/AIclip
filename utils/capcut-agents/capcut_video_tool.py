"""
CapCut Mate - 视频生成工具 (LangChain 封装)
"""

import json
from langchain_core.tools import tool
from core.video_processor import create_video
from tools.asr_utils import parse_asr_output

@tool
def capcut_video_creation_tool(
    asr_file_path: str,
    video_files: list[str],
    draft_name: str = "quick_video",
    max_effects: int = 5,
    max_stickers: int = 3,
) -> dict:
    """
    使用 CapCut Mate 快速创建视频工具。该工具会自动解析 ASR 文件获取文案和时间戳。
    
    参数:
        asr_file_path: ASR 输出 JSON 文件路径（支持 ASR 原始格式或简单 [{text,start,end}] 格式）
        video_files: 视频文件路径列表 (例如: ["C:/videos/v1.mp4"])
        draft_name: 剪映草稿名称，默认为 "quick_video"，不需要修改
        max_effects: 视频中允许添加的最大视觉特效数量，默认 5
        max_stickers: 视频中允许添加的最大贴纸数量，默认 3
    
    返回:
        包含 success (bool), draft_id, draft_path, final_video_path 等字段的结果字典。
    """
    # 加载并解析 ASR 输出
    try:
        with open(asr_file_path, 'r', encoding='utf-8') as f:
            asr_data = json.load(f)
        
        script, timestamps = parse_asr_output(asr_data)
        
        print(f"📋 解析 ASR 输出: {len(timestamps)} 个片段, 文案 {len(script)} 字")
        for ts in timestamps:
            print(f"   [{ts['start']:.1f}s - {ts['end']:.1f}s] {ts['text']}")
            
        return create_video(
            video_files=video_files,
            script=script,
            timestamps=timestamps,
            draft_name=draft_name,
            max_effects=max_effects,
            max_stickers=max_stickers
        )
    except Exception as e:
        return {"success": False, "error": f"解析 ASR 文件或创建视频失败: {str(e)}"}

if __name__ == "__main__":
    # 测试代码
    print("🚀 启动工具测试...")
    
    # 使用项目中的测试文件
    test_asr_file = r"timestamps.json"
    test_video = r"C:\Users\64061\Desktop\fusion (13).mp4"
    
    test_result = capcut_video_creation_tool.invoke({
        "asr_file_path": test_asr_file,
        "video_files": [test_video],
        "draft_name": "tool_test_draft"
    })
    
    print("\n✅ 测试调用完成")
    print(f"执行结果: {test_result}")


