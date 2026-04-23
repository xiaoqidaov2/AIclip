from __future__ import annotations

from .impl.project_tool_impl_media import ProjectToolMediaMixin
from .impl.project_tool_impl_project import ProjectToolProjectMixin
from .impl.project_tool_impl_subtitle_image import ProjectToolSubtitleImageMixin
from .impl.project_tool_impl_time import ProjectToolTimeMixin
from .project_tool_postparse import ProjectToolPostParseMixin


class ProjectTool(
    ProjectToolPostParseMixin,
    ProjectToolSubtitleImageMixin,
    ProjectToolMediaMixin,
    ProjectToolTimeMixin,
    ProjectToolProjectMixin,
):
    """Project-level editing entry points backed by editor_core."""
