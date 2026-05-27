import asyncio
import shlex
from pathlib import Path
from typing import Any

from orionxcore.config import Settings
from orionxcore.tools.base import Tool


class TerminalTool(Tool):
    name = "run_terminal_command"
    description = "Execute a shell command in the configured workspace and return stdout, stderr, and exit code."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute.",
            },
            "workdir": {
                "type": "string",
                "description": "Optional working directory relative to the configured terminal workspace.",
            },
            "timeout": {
                "type": "integer",
                "description": "Optional timeout in seconds.",
                "minimum": 1,
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command = (arguments.get("command") or "").strip()
        if not command:
            return {"ok": False, "error": "Missing command."}
        if self._is_risky(command) and not self._settings.allow_risky_commands:
            return {
                "ok": False,
                "error": "Command blocked by safety policy.",
                "requires_confirmation": True,
            }

        workdir = self._resolve_workdir(arguments.get("workdir"))
        timeout = int(arguments.get("timeout") or self._settings.terminal_timeout)
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            return {"ok": False, "error": f"Command timed out after {timeout} seconds."}

        return {
            "ok": process.returncode == 0,
            "command": command,
            "workdir": str(workdir),
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }

    def _resolve_workdir(self, workdir: str | None) -> Path:
        base = self._settings.terminal_workdir.resolve()
        if not workdir:
            return base
        candidate = (base / workdir).resolve()
        if base == candidate or base in candidate.parents:
            return candidate
        return base

    def _is_risky(self, command: str) -> bool:
        lowered = command.lower()
        risky_terms = (
            "rm -rf /",
            "mkfs",
            "shutdown",
            "reboot",
            "halt",
            "poweroff",
            "dd if=",
            "chmod -r 777 /",
            ":(){:|:&};:",
        )
        if any(term in lowered for term in risky_terms):
            return True
        try:
            tokens = shlex.split(command)
        except ValueError:
            return True
        return any(token in {"sudo", "su"} for token in tokens)

