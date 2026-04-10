import os
import subprocess
import stat
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


class FileTools:
    """Basic file and shell tools for the CLI agent."""

    def read(self, file_path: str) -> Dict[str, Any]:
        """Read a file and return its content.

        Args:
            file_path: Path to the file to read

        Returns:
            Dict with keys: ok, summary, content
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return {
                    "ok": False,
                    "summary": f"File not found: {file_path}",
                    "content": ""
                }

            content = path.read_text(encoding="utf-8")
            lines = len(content.splitlines())
            return {
                "ok": True,
                "summary": f"Read {lines} lines from {file_path}",
                "content": content
            }
        except Exception as e:
            return {
                "ok": False,
                "summary": f"Error reading file: {str(e)}",
                "content": ""
            }

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> Dict[str, Any]:
        """Edit a file by replacing old_string with new_string.

        Args:
            file_path: Path to the file to edit
            old_string: String to replace
            new_string: String to replace with
            replace_all: If True, replace all occurrences; else only first

        Returns:
            Dict with keys: ok, summary, content (diff)
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return {
                    "ok": False,
                    "summary": f"File not found: {file_path}",
                    "content": ""
                }

            content = path.read_text(encoding="utf-8")
            if old_string not in content:
                return {
                    "ok": False,
                    "summary": f"String not found in {file_path}",
                    "content": ""
                }

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                # Replace only first occurrence
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            path.write_text(new_content, encoding="utf-8")

            # Generate a simple diff-like summary
            summary = f"Replaced {count} occurrence(s) of '{old_string[:50]}...' with '{new_string[:50]}...' in {file_path}"

            return {
                "ok": True,
                "summary": summary,
                "content": f"Successfully edited {file_path}"
            }
        except Exception as e:
            return {
                "ok": False,
                "summary": f"Error editing file: {str(e)}",
                "content": ""
            }

    def write(self, file_path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
        """Write text content to a file, creating parent directories if needed."""
        try:
            path = Path(file_path)
            existed_before = path.exists()
            path.parent.mkdir(parents=True, exist_ok=True)

            if existed_before and not overwrite:
                return {
                    "ok": False,
                    "summary": f"File already exists: {file_path}",
                    "content": "",
                }

            path.write_text(content, encoding="utf-8")
            lines = len(content.splitlines())
            action = "Overwrote" if existed_before else "Created"
            return {
                "ok": True,
                "summary": f"{action} {file_path} with {lines} line(s)",
                "content": f"Successfully wrote {file_path}",
            }
        except Exception as e:
            return {
                "ok": False,
                "summary": f"Error writing file: {str(e)}",
                "content": "",
            }

    def grep(self, pattern: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Search for pattern in file or files.

        Args:
            pattern: Regex pattern to search for
            file_path: Optional path to file or directory. If None, searches current directory

        Returns:
            Dict with keys: ok, summary, content (matches)
        """
        try:
            import re

            if file_path is None:
                file_path = "."

            path = Path(file_path)
            matches = []

            if path.is_file():
                files_to_search = [path]
            elif path.is_dir():
                # Search all files in directory (non-recursive for simplicity)
                files_to_search = [f for f in path.iterdir() if f.is_file()]
            else:
                return {
                    "ok": False,
                    "summary": f"Path not found: {file_path}",
                    "content": ""
                }

            regex = re.compile(pattern)

            for file in files_to_search:
                try:
                    content = file.read_text(encoding="utf-8")
                    lines = content.splitlines()
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            matches.append(f"{file}:{i}: {line}")
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary or unreadable files
                    continue

            if matches:
                summary = f"Found {len(matches)} match(es) for pattern '{pattern}'"
                content = "\n".join(matches[:20])  # Limit output
                if len(matches) > 20:
                    content += f"\n... and {len(matches) - 20} more matches"
            else:
                summary = f"No matches found for pattern '{pattern}'"
                content = ""

            return {
                "ok": True,
                "summary": summary,
                "content": content
            }
        except Exception as e:
            return {
                "ok": False,
                "summary": f"Error during grep: {str(e)}",
                "content": ""
            }

    def _is_hidden(self, path: Path) -> bool:
        if path.name.startswith("."):
            return True

        if os.name != "nt":
            return False

        try:
            file_attributes = getattr(path.stat(), "st_file_attributes", 0)
            hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
            return bool(file_attributes & hidden_flag)
        except (OSError, ValueError):
            return False

    def list_directory(self, directory_path: str = ".", include_hidden: bool = False) -> Dict[str, Any]:
        """List files and folders in a directory."""
        try:
            path = Path(directory_path)
            if not path.exists():
                return {
                    "ok": False,
                    "summary": f"Path not found: {directory_path}",
                    "content": "",
                    "entries": [],
                }

            if not path.is_dir():
                return {
                    "ok": False,
                    "summary": f"Not a directory: {directory_path}",
                    "content": "",
                    "entries": [],
                }

            entries = []
            for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if not include_hidden and self._is_hidden(entry):
                    continue

                try:
                    info = entry.stat()
                except OSError:
                    continue

                is_dir = entry.is_dir()
                entry_data = {
                    "name": entry.name,
                    "path": str(entry),
                    "type": "directory" if is_dir else "file",
                    "hidden": self._is_hidden(entry),
                    "modified_time": datetime.fromtimestamp(info.st_mtime).isoformat(timespec="seconds"),
                }
                if not is_dir:
                    entry_data["size"] = info.st_size
                entries.append(entry_data)

            lines = []
            for entry in entries:
                marker = "[D]" if entry["type"] == "directory" else "[F]"
                hidden_tag = " (hidden)" if entry["hidden"] else ""
                size_text = f" - {entry['size']} bytes" if entry["type"] == "file" and "size" in entry else ""
                lines.append(f"{marker} {entry['name']}{hidden_tag}{size_text}")

            summary = f"Listed {len(entries)} item(s) in {directory_path}"
            if include_hidden:
                summary += " (including hidden)"

            return {
                "ok": True,
                "summary": summary,
                "content": "\n".join(lines),
                "directory_path": str(path),
                "include_hidden": include_hidden,
                "entries": entries,
            }
        except Exception as e:
            return {
                "ok": False,
                "summary": f"Error listing directory: {str(e)}",
                "content": "",
                "entries": [],
            }

    def bash(self, command: str) -> Dict[str, Any]:
        """Execute a shell command.

        Args:
            command: Shell command to execute

        Returns:
            Dict with keys: ok, summary, content (stdout/stderr)
        """
        try:
            # Security note: In a real application, you'd want to restrict commands
            # For this demo, we'll allow basic commands but warn
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30  # 30 second timeout
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\nSTDERR:\n"
                output += result.stderr

            if result.returncode == 0:
                summary = f"Command executed successfully (exit code {result.returncode})"
            else:
                summary = f"Command failed with exit code {result.returncode}"

            # Truncate output if too long
            if len(output) > 1000:
                output = output[:1000] + "\n... (output truncated)"

            return {
                "ok": result.returncode == 0,
                "summary": summary,
                "content": output
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "summary": "Command timed out after 30 seconds",
                "content": ""
            }
        except Exception as e:
            return {
                "ok": False,
                "summary": f"Error executing command: {str(e)}",
                "content": ""
            }


# Create a singleton instance for easy registration
file_tools = FileTools()

# Export individual functions for tool registration
def read_file(file_path: str) -> Dict[str, Any]:
    """Read the full contents of a file and return a structured result."""
    return file_tools.read(file_path)

def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> Dict[str, Any]:
    """Edit a file by replacing text and return a structured summary of the change."""
    return file_tools.edit(file_path, old_string, new_string, replace_all)

def write_file(file_path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
    """Write text content to a file and return a structured result."""
    return file_tools.write(file_path, content, overwrite)

def grep_file(pattern: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Search for a regex pattern in a file or directory and return matching lines."""
    return file_tools.grep(pattern, file_path)

def bash_command(command: str) -> Dict[str, Any]:
    """Run a shell command and return its exit status plus captured output."""
    return file_tools.bash(command)

def list_directory(directory_path: str = ".", include_hidden: bool = False) -> Dict[str, Any]:
    """List directory contents and return files/folders in a structured result."""
    return file_tools.list_directory(directory_path, include_hidden)
