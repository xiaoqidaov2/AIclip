"""Verify multiline subtitle rendering works after fix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.tools.project_tool_impl import ProjectTool

PROJECT_PATH = "C:/Users/admin/.aiclip/projects/a5328f0cd57dbcd7008a8a5c30128e65_20260429_142150/project.json"

tool = ProjectTool()

# Add a multiline subtitle
print("Adding multiline subtitle...")
result = tool.add_project_subtitle(
    PROJECT_PATH,
    subtitle_id="multiline_test_01",
    start=0.0,
    end=2.0,
    text="Line one\nLine two",
)
print("add ok:", result.get("ok"), "code:", result.get("code"))

# Render with the multiline subtitle
print("Rendering with multiline subtitle...")
render = tool.render_project(PROJECT_PATH, output_path="tmp/test_multiline_render.mp4")
print("render ok:", render.get("ok"), "code:", render.get("code"))
if render.get("ok"):
    print("Rendered to:", render.get("state", {}).get("final_path") or "tmp/test_multiline_render.mp4")
else:
    print("Render error:", render.get("error"))

# Cleanup
print("Removing test subtitle...")
tool.remove_project_subtitle(PROJECT_PATH, subtitle_id="multiline_test_01")
