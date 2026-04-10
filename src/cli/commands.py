def show_help() -> None:
    print("""
Available commands:
  /help             Show this help message
  /exit             Exit the CLI
  /quit             Exit the CLI
  /clear            Clear conversation history
  /verbose          Toggle verbose output (show full message stream)
  /status           Show current status
  /coordinate <任务> 使用协调器模式执行复杂任务（四阶段工作流）
  /workers          显示当前所有 Worker 状态

Built-in tools available to agent:
  read_file     Read file content
  edit_file     Replace strings in a file
  grep_file     Search for patterns in files
  bash_command  Execute shell commands
  transcribe    Transcribe audio/video to text
  generate_srt  Generate SRT subtitles from video
""")


def clear_history() -> None:
    print("Conversation history cleared.")
    # Note: Actual history clearing handled in app.py


def toggle_verbose(current: bool) -> bool:
    new_value = not current
    status = "ON" if new_value else "OFF"
    print(f"Verbose mode: {status}")
    return new_value


def show_status(verbose: bool) -> None:
    print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
