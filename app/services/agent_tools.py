import pathlib

from langchain_core.tools import tool


def safe_path_for_project(project_root: pathlib.Path, relative_path: str) -> pathlib.Path:
    """Resolve relative_path against project_root, refusing anything that escapes it."""
    candidate = (project_root / relative_path).resolve()
    project_root_resolved = project_root.resolve()
    if not candidate.is_relative_to(project_root_resolved):
        raise ValueError(
            f"Path '{relative_path}' resolves outside the project directory -- refused."
        )
    return candidate

def make_tools_for_job(project_root: pathlib.Path) -> dict:
    """Build a fresh set of file tools scoped to ONE job's project_root."""

    @tool
    def read_file(relative_path: str) -> str:
        """Read and return the full text contents of a file, given a path relative to the project root.
        Returns an error message string if the file doesn't exist."""

        try:
            path = safe_path_for_project(project_root, relative_path)
            if not path.exists():
                return f"Error: {relative_path} does not exist."
            return path.read_text(encoding="utf-8")
        except ValueError as exc:
            return f"Error: {exc}"

    @tool
    def write_file(relative_path: str, content: str) -> str:
        """Write text content to a file at the given path relative to the project root.
        Creates parent directories if needed. Overwrites the file if it already exists."""
        try:
            path = safe_path_for_project(project_root, relative_path)
            if path.is_dir():
                return f"Error: '{relative_path}' is a directory, not a file. Specify a filename, e.g. '{relative_path}/index.js'."
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} characters to {relative_path}"
        except ValueError as exc:
            return f"Error: {exc}"
        except OSError as exc:
            return f"Error: could not write '{relative_path}': {exc}"

    @tool
    def list_files(relative_path: str = ".") -> str:
        """List files and directories at the given path relative to the project root.
                Defaults to the project root itself."""

        try:
            path = safe_path_for_project(project_root, relative_path)
            if not path.exists():
                return f"Error: {relative_path} does not exist."
            entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
            return "\n".join(entries) if entries else "(empty directory)"
        except ValueError as exc:
            return f"Error: {exc}"

    @tool
    def get_current_directory() -> str:
        """Return the project root's absolute path -- useful for the agent to orient itself."""

        return str(project_root)

    return {
        "read_file": read_file,
        "write_file": write_file,
        "list_files": list_files,
        "get_current_directory": get_current_directory,
    }
