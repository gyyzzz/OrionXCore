import os
from pathlib import Path
from typing import Any

from orionxcore.config import Settings
from orionxcore.tools.base import Tool


class FileSystemTool(Tool):
    name = "filesystem"
    description = (
        "Perform safe file system operations within the configured workspace. "
        "Supports: read_file, write_file, append_file, list_dir, make_dir, "
        "delete_file, move, stat, search."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "read_file",
                    "write_file",
                    "append_file",
                    "list_dir",
                    "make_dir",
                    "delete_file",
                    "move",
                    "stat",
                    "search",
                ],
                "description": "File system operation to perform.",
            },
            "path": {
                "type": "string",
                "description": "Target path relative to the workspace root.",
            },
            "destination": {
                "type": "string",
                "description": "Destination path for move operation.",
            },
            "content": {
                "type": "string",
                "description": "Content for write_file or append_file.",
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding (default: utf-8).",
            },
            "offset": {
                "type": "integer",
                "description": "Starting line number for read_file (0-based).",
                "minimum": 0,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum lines to read or entries to list.",
                "minimum": 1,
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern for search operation (e.g. '**/*.py').",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether list_dir should traverse subdirectories.",
            },
            "create_parents": {
                "type": "boolean",
                "description": "Create parent directories for write_file/make_dir.",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Allow overwriting existing files for write_file/move.",
            },
        },
        "required": ["operation"],
        "additionalProperties": False,
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        operation = arguments.get("operation")
        try:
            if operation == "read_file":
                return self._read_file(arguments)
            if operation == "write_file":
                return self._write_file(arguments)
            if operation == "append_file":
                return self._append_file(arguments)
            if operation == "list_dir":
                return self._list_dir(arguments)
            if operation == "make_dir":
                return self._make_dir(arguments)
            if operation == "delete_file":
                return self._delete_file(arguments)
            if operation == "move":
                return self._move(arguments)
            if operation == "stat":
                return self._stat(arguments)
            if operation == "search":
                return self._search(arguments)
            return {"ok": False, "error": f"Unknown operation: {operation}"}
        except PermissionError as exc:
            return {"ok": False, "error": f"Permission denied: {exc}"}
        except OSError as exc:
            return {"ok": False, "error": f"OS error: {exc}"}

    def _read_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve_path(arguments.get("path"))
        if isinstance(path, dict):
            return path
        if not path.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        if not path.is_file():
            return {"ok": False, "error": f"Not a file: {path}"}

        size = path.stat().st_size
        if size > self._settings.filesystem_max_read_bytes:
            return {
                "ok": False,
                "error": (
                    f"File too large: {size} bytes exceeds limit "
                    f"{self._settings.filesystem_max_read_bytes}."
                ),
            }

        encoding = arguments.get("encoding") or "utf-8"
        offset = int(arguments.get("offset") or 0)
        limit = arguments.get("limit")

        with path.open("r", encoding=encoding, errors="replace") as fh:
            lines = fh.readlines()

        total_lines = len(lines)
        end = total_lines if limit is None else min(total_lines, offset + int(limit))
        sliced = lines[offset:end]

        return {
            "ok": True,
            "path": str(path),
            "content": "".join(sliced),
            "line_count": total_lines,
            "returned_lines": len(sliced),
            "offset": offset,
            "truncated": end < total_lines,
            "size_bytes": size,
        }

    def _write_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.filesystem_allow_write:
            return {"ok": False, "error": "Filesystem write operations are disabled."}

        path = self._resolve_path(arguments.get("path"))
        if isinstance(path, dict):
            return path

        content = arguments.get("content")
        if content is None:
            return {"ok": False, "error": "Missing content for write_file."}

        overwrite = bool(arguments.get("overwrite", True))
        if path.exists() and not overwrite:
            return {
                "ok": False,
                "error": f"File already exists and overwrite is disabled: {path}",
                "requires_confirmation": True,
            }

        encoding = arguments.get("encoding") or "utf-8"
        size_check = self._check_write_size(content, encoding)
        if size_check is not None:
            return size_check

        if bool(arguments.get("create_parents", True)):
            path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding=encoding) as fh:
            fh.write(content)

        return {
            "ok": True,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "created": True,
        }

    def _append_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.filesystem_allow_write:
            return {"ok": False, "error": "Filesystem write operations are disabled."}

        path = self._resolve_path(arguments.get("path"))
        if isinstance(path, dict):
            return path

        content = arguments.get("content")
        if content is None:
            return {"ok": False, "error": "Missing content for append_file."}

        encoding = arguments.get("encoding") or "utf-8"
        size_check = self._check_write_size(content, encoding)
        if size_check is not None:
            return size_check

        if bool(arguments.get("create_parents", True)):
            path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("a", encoding=encoding) as fh:
            fh.write(content)

        return {
            "ok": True,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "appended": True,
        }

    def _list_dir(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve_path(arguments.get("path") or ".")
        if isinstance(path, dict):
            return path
        if not path.exists():
            return {"ok": False, "error": f"Path not found: {path}"}
        if not path.is_dir():
            return {"ok": False, "error": f"Not a directory: {path}"}

        recursive = bool(arguments.get("recursive", False))
        limit = int(arguments.get("limit") or self._settings.filesystem_max_list_entries)
        limit = min(limit, self._settings.filesystem_max_list_entries)

        entries: list[dict[str, Any]] = []
        iterator = path.rglob("*") if recursive else path.iterdir()
        for entry in iterator:
            if len(entries) >= limit:
                break
            try:
                stat = entry.stat()
                entries.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "relative_path": str(entry.relative_to(self._workspace_root())),
                        "is_dir": entry.is_dir(),
                        "is_file": entry.is_file(),
                        "size_bytes": stat.st_size if entry.is_file() else None,
                        "modified": stat.st_mtime,
                    }
                )
            except OSError:
                continue

        return {
            "ok": True,
            "path": str(path),
            "entry_count": len(entries),
            "entries": entries,
            "truncated": len(entries) >= limit,
        }

    def _make_dir(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.filesystem_allow_write:
            return {"ok": False, "error": "Filesystem write operations are disabled."}

        path = self._resolve_path(arguments.get("path"))
        if isinstance(path, dict):
            return path

        parents = bool(arguments.get("create_parents", True))
        path.mkdir(parents=parents, exist_ok=True)
        return {"ok": True, "path": str(path), "created": True}

    def _delete_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.filesystem_allow_delete:
            return {
                "ok": False,
                "error": "Filesystem delete operations are disabled.",
                "requires_confirmation": True,
            }

        path = self._resolve_path(arguments.get("path"))
        if isinstance(path, dict):
            return path
        if not path.exists():
            return {"ok": False, "error": f"Path not found: {path}"}

        if path == self._workspace_root():
            return {"ok": False, "error": "Refusing to delete workspace root."}

        if path.is_dir():
            try:
                path.rmdir()
            except OSError as exc:
                return {
                    "ok": False,
                    "error": f"Directory not empty or cannot be removed: {exc}",
                }
        else:
            path.unlink()
        return {"ok": True, "path": str(path), "deleted": True}

    def _move(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.filesystem_allow_write:
            return {"ok": False, "error": "Filesystem write operations are disabled."}

        source = self._resolve_path(arguments.get("path"))
        if isinstance(source, dict):
            return source
        destination = self._resolve_path(arguments.get("destination"))
        if isinstance(destination, dict):
            return destination

        if not source.exists():
            return {"ok": False, "error": f"Source not found: {source}"}

        overwrite = bool(arguments.get("overwrite", False))
        if destination.exists() and not overwrite:
            return {
                "ok": False,
                "error": f"Destination already exists: {destination}",
                "requires_confirmation": True,
            }

        if bool(arguments.get("create_parents", True)):
            destination.parent.mkdir(parents=True, exist_ok=True)

        os.replace(source, destination)
        return {
            "ok": True,
            "source": str(source),
            "destination": str(destination),
            "moved": True,
        }

    def _stat(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve_path(arguments.get("path"))
        if isinstance(path, dict):
            return path
        if not path.exists():
            return {"ok": False, "error": f"Path not found: {path}"}

        stat = path.stat()
        return {
            "ok": True,
            "path": str(path),
            "is_dir": path.is_dir(),
            "is_file": path.is_file(),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
            "mode": oct(stat.st_mode),
        }

    def _search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        pattern = arguments.get("pattern")
        if not pattern:
            return {"ok": False, "error": "Missing pattern for search."}

        base = self._resolve_path(arguments.get("path") or ".")
        if isinstance(base, dict):
            return base
        if not base.exists() or not base.is_dir():
            return {"ok": False, "error": f"Search base is not a directory: {base}"}

        limit = int(arguments.get("limit") or self._settings.filesystem_max_list_entries)
        limit = min(limit, self._settings.filesystem_max_list_entries)

        matches: list[str] = []
        for entry in base.glob(pattern):
            if len(matches) >= limit:
                break
            matches.append(str(entry))

        return {
            "ok": True,
            "base": str(base),
            "pattern": pattern,
            "match_count": len(matches),
            "matches": matches,
            "truncated": len(matches) >= limit,
        }

    def _workspace_root(self) -> Path:
        root = self._settings.filesystem_workdir or self._settings.terminal_workdir
        return Path(root).resolve()

    def _resolve_path(self, raw: str | None) -> Path | dict[str, Any]:
        if raw is None or raw == "":
            return {"ok": False, "error": "Missing path argument."}
        base = self._workspace_root()
        candidate = (base / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if candidate != base and base not in candidate.parents:
            return {
                "ok": False,
                "error": f"Path escapes workspace root: {candidate}",
            }
        return candidate

    def _check_write_size(self, content: str, encoding: str) -> dict[str, Any] | None:
        try:
            size = len(content.encode(encoding))
        except (LookupError, UnicodeEncodeError) as exc:
            return {"ok": False, "error": f"Encoding error: {exc}"}
        if size > self._settings.filesystem_max_write_bytes:
            return {
                "ok": False,
                "error": (
                    f"Content too large: {size} bytes exceeds limit "
                    f"{self._settings.filesystem_max_write_bytes}."
                ),
            }
        return None
