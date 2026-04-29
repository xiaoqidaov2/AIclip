"""Quick validation of overlay placement restriction."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.tools.project_tool_impl import ProjectTool

PROJECT_PATH = "C:/Users/admin/.aiclip/projects/a5328f0cd57dbcd7008a8a5c30128e65_20260429_142150/project.json"

tool = ProjectTool()
clips = tool.list_project_clips(PROJECT_PATH)
for c in clips.get("payload", {}).get("clips", []):
    if c["id"] == "ovclip_50d0b7":
        print(json.dumps(c, indent=2))
        break
else:
    print("ovclip_50d0b7 not found")
