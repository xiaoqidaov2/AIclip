from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(r"c:\Users\admin\Documents\item\AiClip")
SRC = ROOT / "src/llm/tools/project_tool_postparse.py"
text = SRC.read_text(encoding="utf-8")
lines = text.splitlines()

pattern = re.compile(r"^    def (\w+)\(")
methods = []
for idx, line in enumerate(lines):
    match = pattern.match(line)
    if match:
        methods.append((match.group(1), idx))
methods_with_end = []
for index, (name, start) in enumerate(methods):
    end = methods[index + 1][1] if index + 1 < len(methods) else len(lines)
    methods_with_end.append((name, start, end))
method_map = {name: (start, end) for name, start, end in methods_with_end}

common_header = '''from __future__ import annotations

from .project_tool_postparse_common import *


'''

out_dir = ROOT / "src/llm/tools"
for path in out_dir.glob("project_tool_postparse_*.py"):
    if path.name not in {
        "project_tool_postparse.py",
        "project_tool_postparse_common.py",
        "project_tool_postparse_create_helpers.py",
        "project_tool_postparse_silence_helpers.py",
    }:
        path.unlink()

for name, start, end in methods_with_end:
    filename = f"project_tool_postparse_{name}.py"
    class_name = "ProjectToolPostParse" + "".join(part.capitalize() for part in name.split("_")) + "Mixin"
    body = [common_header, f"class {class_name}:\n", "    def __getattr__(self, name: str) -> Any:\n", "        raise AttributeError(name)\n\n"]
    body.append("\n".join(lines[start:end]).rstrip() + "\n")
    (out_dir / filename).write_text("".join(body), encoding="utf-8")

imports = [
    "from __future__ import annotations\n\n",
    "from .project_tool_render import ProjectToolRenderMixin\n",
    "from .project_tool_postparse_create_helpers import ProjectToolPostParseCreateHelpersMixin\n",
    "from .project_tool_postparse_silence_helpers import ProjectToolPostParseSilenceHelpersMixin\n",
]
bases = ["ProjectToolRenderMixin", "ProjectToolPostParseCreateHelpersMixin", "ProjectToolPostParseSilenceHelpersMixin"]
for name, _, _ in methods_with_end:
    module = f"project_tool_postparse_{name}"
    class_name = "ProjectToolPostParse" + "".join(part.capitalize() for part in name.split("_")) + "Mixin"
    imports.append(f"from .{module} import {class_name}\n")
    bases.append(class_name)
facade = imports + ["\n\nclass ProjectToolPostParseMixin(\n"]
for base in bases:
    facade.append(f"    {base},\n")
facade.append("):\n    pass\n")
(out_dir / "project_tool_postparse.py").write_text("".join(facade), encoding="utf-8")
