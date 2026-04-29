"""Remove the test multiline subtitle and render."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.tools.project_tool_impl import ProjectTool

PROJECT_PATH = "C:/Users/admin/.aiclip/projects/a5328f0cd57dbcd7008a8a5c30128e65_20260429_142150/project.json"

tool = ProjectTool()

# Remove the multiline subtitle we added
print("Removing test subtitle sub_0fed54...")
result = tool.remove_project_subtitle(PROJECT_PATH, subtitle_id="sub_0fed54")
print("ok:", result.get("ok"), "code:", result.get("code"))

# Render
print("Rendering...")
render = tool.render_project(PROJECT_PATH, output_path="tmp/test_e2e_final_render.mp4")
print("render ok:", render.get("ok"), "code:", render.get("code"))
if render.get("ok"):
    print("Rendered to:", render.get("state", {}).get("final_path") or "tmp/test_e2e_final_render.mp4")
else:
    print("Render error:", render.get("error"))
