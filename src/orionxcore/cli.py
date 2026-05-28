import argparse
import json
import sys
from typing import Any
from uuid import uuid4

import httpx

# ASCII art logo
LOGO = """
 ██████╗ ██████╗ ██╗ ██████╗ ███╗   ██╗██╗  ██╗
██╔═══██╗██╔══██╗██║██╔═══██╗████╗  ██║╚██╗██╔╝
██║   ██║██████╔╝██║██║   ██║██╔██╗ ██║ ╚███╔╝
██║   ██║██╔══██╗██║██║   ██║██║╚██╗██║ ██╔██╗
╚██████╔╝██║  ██║██║╚██████╔╝██║ ╚████║██╔╝ ██╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝
"""

VERSION = "0.2.0"


def print_banner() -> None:
    """Print the OrionX logo and version."""
    print(LOGO)
    print(f"  OrionXCore CLI v{VERSION}")
    print("")

# Configure readline for proper backspace/delete handling
# macOS uses libedit which requires different syntax than GNU readline
try:
    import readline
    if "libedit" in (readline.__doc__ or ""):
        # macOS libedit bindings
        readline.parse_and_bind("bind ^? ed-delete-prev-char")  # Backspace
        readline.parse_and_bind("bind ^H ed-delete-prev-char")  # Ctrl-H
        readline.parse_and_bind("bind ^[[3~ ed-delete-next-char")  # Delete key
    else:
        # GNU readline bindings
        readline.parse_and_bind("set enable-keypad on")
except ImportError:
    pass  # readline not available on some platforms


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orionx", description="OrionXCore command line client.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
        help="Base URL for the OrionXCore service.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout in seconds.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Send a prompt to /v1/agent/respond.")
    ask_parser.add_argument("prompt", help="Natural language prompt to send.")
    ask_parser.add_argument("--session-id", help="Optional session ID.")
    ask_parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw JSON response instead of formatted output.",
    )
    ask_parser.add_argument(
        "--json",
        action="store_true",
        help="Alias for --raw.",
    )

    chat_parser = subparsers.add_parser("chat", help="Start an interactive chat session.")
    chat_parser.add_argument("--session-id", help="Optional session ID. Generated automatically if omitted.")
    chat_parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw JSON responses for each turn.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ask":
        return run_ask(args)
    if args.command == "chat":
        return run_chat(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


def run_ask(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "messages": [
            {
                "role": "user",
                "content": args.prompt,
            }
        ]
    }
    if args.session_id:
        payload["session_id"] = args.session_id

    response = post_json(
        base_url=args.base_url,
        path="/v1/agent/respond",
        payload=payload,
        timeout=args.timeout,
    )

    if args.raw or args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0

    render_agent_response(response)
    return 0


def run_chat(args: argparse.Namespace) -> int:
    print_banner()
    session_id = args.session_id or f"chat-{uuid4().hex[:8]}"
    print(f"Session: {session_id}")
    print("Type 'exit' or 'quit' to stop.")
    print("")

    while True:
        try:
            prompt = input("you> ").strip()
        except EOFError:
            print("")
            return 0
        except KeyboardInterrupt:
            print("")
            return 0

        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            return 0

        response = post_json(
            base_url=args.base_url,
            path="/v1/agent/respond",
            payload={
                "messages": [{"role": "user", "content": prompt}],
                "session_id": session_id,
            },
            timeout=args.timeout,
        )

        if args.raw:
            print(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            render_agent_response(response, assistant_label="assistant>")


def post_json(base_url: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        print(f"HTTP error {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        raise SystemExit(1) from exc
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def render_agent_response(response: dict[str, Any], assistant_label: str = "Assistant") -> None:
    print(assistant_label)
    print(response.get("message", {}).get("content", ""))
    print("")

    events = response.get("events") or []
    if not events:
        return

    print("Events")
    for event in events:
        event_type = event.get("type", "")
        payload = event.get("payload", {})
        print(format_event(event_type, payload))


def format_event(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "assistant":
        # Skip assistant event as it's already printed via message.content
        return ""
    if event_type == "iteration":
        return f"- iteration #{payload.get('iteration')}"
    if event_type == "tool_call":
        return f"- tool_call {payload.get('name')}: {json.dumps(payload.get('arguments', {}), ensure_ascii=False)}"
    if event_type == "tool_result":
        result = payload.get("result", {})
        status = "ok" if result.get("ok") else "error"
        return f"- tool_result {payload.get('name')} [{status}]"
    if event_type == "database_trace":
        return (
            f"- database_trace question={payload.get('question')!r} "
            f"database={payload.get('database')!r} final_sql={payload.get('final_sql')!r}"
        )
    if event_type == "database_schema_context":
        return f"- database_schema_context\n{indent_text(payload.get('schema_context', ''))}"
    if event_type == "database_sql_attempt":
        return (
            f"- database_sql_attempt #{payload.get('attempt')}: {payload.get('sql')!r}"
            + (f" retry_reason={payload.get('retry_reason')!r}" if payload.get("retry_reason") else "")
            + (f" error={payload.get('error')!r}" if payload.get("error") else "")
        )
    if event_type == "database_result_summary":
        return (
            f"- database_result_summary ok={payload.get('ok')} "
            f"row_count={payload.get('row_count')} columns={payload.get('columns')}"
        )
    if event_type == "assistant":
        return f"- assistant: {payload.get('content', '')}"
    return f"- {event_type}: {json.dumps(payload, ensure_ascii=False)}"


def indent_text(text: str) -> str:
    if not text:
        return "  <empty>"
    return "\n".join(f"  {line}" for line in text.splitlines())
