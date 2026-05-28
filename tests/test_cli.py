import io
import builtins
from contextlib import redirect_stdout

from orionxcore import cli


def test_cli_ask_raw_outputs_json(monkeypatch) -> None:
    def fake_post_json(base_url, path, payload, timeout):
        return {
            "message": {"content": "hello"},
            "events": [],
            "iterations": 1,
        }

    monkeypatch.setattr(cli, "post_json", fake_post_json)
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli.main(["ask", "hello", "--raw"])

    output = stdout.getvalue()
    assert exit_code == 0
    assert '"content": "hello"' in output


def test_cli_ask_formats_database_events(monkeypatch) -> None:
    def fake_post_json(base_url, path, payload, timeout):
        return {
            "message": {"content": "There are 42 users."},
            "events": [
                {"type": "iteration", "payload": {"iteration": 1}},
                {
                    "type": "database_trace",
                    "payload": {
                        "question": "How many users?",
                        "database": "monitor",
                        "final_sql": "SELECT count() FROM metrics",
                    },
                },
                {
                    "type": "database_result_summary",
                    "payload": {
                        "ok": True,
                        "row_count": 1,
                        "columns": ["users"],
                    },
                },
            ],
            "iterations": 1,
        }

    monkeypatch.setattr(cli, "post_json", fake_post_json)
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli.main(["ask", "How many users?"])

    output = stdout.getvalue()
    assert exit_code == 0
    assert "Assistant" in output
    assert "There are 42 users." in output
    assert "database_trace" in output
    assert "database_result_summary" in output


def test_cli_chat_uses_session_and_exits(monkeypatch) -> None:
    calls = []

    def fake_post_json(base_url, path, payload, timeout):
        calls.append(payload)
        return {
            "message": {"content": "There is one table: metrics."},
            "events": [],
            "iterations": 1,
            "session_id": payload["session_id"],
        }

    inputs = iter(["列出 monitor 库里的表", "quit"])

    monkeypatch.setattr(cli, "post_json", fake_post_json)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(cli, "uuid4", lambda: type("U", (), {"hex": "abc12345deadbeef"})())

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli.main(["chat"])

    output = stdout.getvalue()
    assert exit_code == 0
    assert "OrionXCore CLI" in output  # Logo appears
    assert "Session: chat-abc12345" in output
    assert "assistant>" in output
    assert calls[0]["session_id"] == "chat-abc12345"
    assert calls[0]["messages"][0]["content"] == "列出 monitor 库里的表"
