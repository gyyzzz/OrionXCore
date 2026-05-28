import asyncio
from pathlib import Path

from orionxcore.config import Settings
from orionxcore.tools.filesystem import FileSystemTool


def _make_settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "api_key": "test",
        "enable_filesystem": True,
        "filesystem_workdir": tmp_path,
        "filesystem_allow_write": True,
        "filesystem_allow_delete": True,
        "terminal_workdir": tmp_path,
    }
    base.update(overrides)
    return Settings(**base)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_write_then_read(tmp_path):
    tool = FileSystemTool(_make_settings(tmp_path))

    write_result = _run(
        tool.execute(
            {"operation": "write_file", "path": "hello.txt", "content": "hi there"}
        )
    )
    assert write_result["ok"] is True

    read_result = _run(
        tool.execute({"operation": "read_file", "path": "hello.txt"})
    )
    assert read_result["ok"] is True
    assert read_result["content"] == "hi there"


def test_path_escape_blocked(tmp_path):
    tool = FileSystemTool(_make_settings(tmp_path))
    result = _run(
        tool.execute({"operation": "read_file", "path": "../../../etc/passwd"})
    )
    assert result["ok"] is False
    assert "escapes workspace" in result["error"]


def test_list_dir(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("b")

    tool = FileSystemTool(_make_settings(tmp_path))
    result = _run(tool.execute({"operation": "list_dir", "path": "."}))
    assert result["ok"] is True
    names = {entry["name"] for entry in result["entries"]}
    assert "a.txt" in names and "sub" in names


def test_write_disabled(tmp_path):
    tool = FileSystemTool(_make_settings(tmp_path, filesystem_allow_write=False))
    result = _run(
        tool.execute(
            {"operation": "write_file", "path": "x.txt", "content": "x"}
        )
    )
    assert result["ok"] is False
    assert "disabled" in result["error"]


def test_delete_disabled(tmp_path):
    (tmp_path / "f.txt").write_text("x")
    tool = FileSystemTool(_make_settings(tmp_path, filesystem_allow_delete=False))
    result = _run(tool.execute({"operation": "delete_file", "path": "f.txt"}))
    assert result["ok"] is False
    assert result.get("requires_confirmation") is True


def test_search(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.txt").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("")

    tool = FileSystemTool(_make_settings(tmp_path))
    result = _run(
        tool.execute({"operation": "search", "pattern": "**/*.py"})
    )
    assert result["ok"] is True
    assert result["match_count"] == 2


def test_move(tmp_path):
    (tmp_path / "src.txt").write_text("data")
    tool = FileSystemTool(_make_settings(tmp_path))
    result = _run(
        tool.execute(
            {"operation": "move", "path": "src.txt", "destination": "dst.txt"}
        )
    )
    assert result["ok"] is True
    assert (tmp_path / "dst.txt").exists()
    assert not (tmp_path / "src.txt").exists()
