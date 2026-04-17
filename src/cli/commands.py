def show_help() -> None:
    print(
        """
Available commands:
  /help             Show this help message
  /exit             Exit the CLI
  /quit             Exit the CLI
  /clear            Clear conversation history
  /verbose          Toggle verbose output
  /status           Show current session state
  /coordinate <task> Run the coordinator workflow
  /workers          Show current workers

Core tools available to the agent:
  create_project_from_media  Create a project from raw media
  transcribe_audio           Generate subtitle cues from audio
  remove_project_silence     Remove gaps between subtitle cues
  load_project               Load a JSON or XML project
  save_project               Save the current project
  set_project_metadata       Update project metadata
  trim_project_clip          Trim a timeline clip
  set_project_clip_speed     Change clip speed
  add_project_asset          Register a media asset
  add/update/remove_project_subtitle  Manage subtitle cues
    batch_update_project_subtitles      Bulk subtitle positioning, highlighting, and effects
  add/update/remove_project_subtitle_span Manage highlighted words inside subtitles
  add/update/remove_project_audio_stem Manage dialogue/music/effects stems
  add/update/remove_project_effect    Manage visual effects
  add/update/remove_project_comment    Manage collaboration comments
  lock_project_comment       Lock or unlock a comment
  set_project_export_preset   Define export settings
  prepare_project_render      Validate render readiness
  plan_project_export        Plan preview/final/sidecar outputs
  render_project             Render final video with subtitle burn-in
"""
    )


def clear_history() -> None:
    print("Conversation history cleared.")


def toggle_verbose(current: bool) -> bool:
    new_value = not current
    status = "ON" if new_value else "OFF"
    print(f"Verbose mode: {status}")
    return new_value


def show_status(verbose: bool) -> None:
    print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
