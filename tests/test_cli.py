import io
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
