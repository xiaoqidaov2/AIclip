BUILTIN_COMMANDS: list[tuple[str, str]] = [
    ("/help", "Show this help message"),
    ("/exit", "Exit the CLI"),
    ("/quit", "Exit the CLI"),
    ("/clear", "Clear conversation history"),
    ("/verbose", "Toggle verbose output"),
    ("/status", "Show current session state"),
    ("/plan", "Switch to the planning skill"),
]

SKILL_COMMANDS: list[tuple[str, str]] = [
    ("/skills", "List available skills"),
    ("/skill <name>", "Switch and lock the active skill"),
    ("/auto_skill", "Return to automatic skill routing"),
]

CORE_TOOLS: list[tuple[str, str]] = [
    ("create_project_from_media", "Create a project from raw media"),
    ("transcribe_audio", "Generate subtitle cues from audio"),
    ("remove_project_silence", "Remove gaps between subtitle cues"),
    ("load_project", "Load a JSON or XML project"),
    ("save_project", "Save the current project"),
    ("set_project_metadata", "Update project metadata"),
    ("trim_project_clip", "Trim a timeline clip"),
    ("set_project_clip_speed", "Change clip speed"),
    ("add_project_asset", "Register a media asset"),
    ("add/update/remove_project_subtitle", "Manage subtitle cues"),
    ("batch_update_project_subtitles", "Bulk subtitle positioning, highlighting, and effects"),
    ("add/update/remove_project_subtitle_span", "Manage highlighted words inside subtitles"),
    ("add/update/remove_project_audio_stem", "Manage dialogue/music/effects stems"),
    ("add/update/remove_project_effect", "Manage visual effects"),
    ("add/update/remove_project_comment", "Manage collaboration comments"),
    ("lock_project_comment", "Lock or unlock a comment"),
    ("set_project_export_preset", "Define export settings"),
    ("prepare_project_render", "Validate render readiness"),
    ("plan_project_export", "Plan preview/final/sidecar outputs"),
    ("render_project", "Render final video with subtitle burn-in"),
]


def _format_section(title: str, entries: list[tuple[str, str]]) -> str:
    lines = [title]
    lines.extend(f"  {name:<32} {description}" for name, description in entries)
    return "\n".join(lines)


def show_help(skill_names: list[str] | None = None) -> None:
    sections = [_format_section("Available commands:", BUILTIN_COMMANDS)]
    if skill_names:
        sections.append(_format_section("Skills:", SKILL_COMMANDS))
    sections.append(_format_section("Core tools available to the agent:", CORE_TOOLS))
    print("\n\n".join(sections))


def clear_history() -> None:
    print("Conversation history cleared.")


def toggle_verbose(current: bool) -> bool:
    new_value = not current
    status = "ON" if new_value else "OFF"
    print(f"Verbose mode: {status}")
    return new_value


def show_status(verbose: bool) -> None:
    print(f"Verbose mode: {'ON' if verbose else 'OFF'}")


def show_detailed_status(
    *,
    verbose: bool,
    active_skill: str | None,
    locked_skill: str | None,
    planner_enabled: bool,
    history_count: int,
    last_file_path: str | None,
    last_tool_name: str | None,
) -> None:
    routing_mode = f"locked ({locked_skill})" if locked_skill else "auto"
    planner_mode = "llm" if planner_enabled else "heuristic"
    print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
    print(f"Active skill: {active_skill or 'auto'}")
    print(f"Routing mode: {routing_mode}")
    print(f"Planner mode: {planner_mode}")
    print(f"History messages: {history_count}")
    print(f"Last file: {last_file_path or 'N/A'}")
    print(f"Last tool: {last_tool_name or 'N/A'}")
