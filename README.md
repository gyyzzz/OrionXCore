# OrionXCore

OrionXCore is a lightweight, configurable AI coding agent service. You provide a model, API key, and API base URL, then expose a standard HTTP interface that IDE plugins, scripts, or Web UIs can call.

Chinese documentation: [README_zh.md](README_zh.md)

## Goals

- Terminal execution via tool calling
- Database querying via natural language plus Text-to-SQL workflows
- Multi-turn agentic execution with iterative planning and tool use
- OpenAI-compatible model integration with pluggable tools
- REST and SSE endpoints for client integration

## Initial Scope

This initial scaffold includes:

- FastAPI service with health, tool discovery, REST, and SSE endpoints
- OpenAI-compatible chat-completions client
- Agent loop that supports tool-calling until completion
- Terminal tool with basic risk controls and command execution
- Database tool for SQL databases and MongoDB
- Environment-driven configuration

## Quick Start

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. Copy the environment template and fill in your model settings:

```bash
cp .env.example .env
```

3. Start the service:

```bash
uvicorn orionxcore.main:app --host 0.0.0.0 --port 8080
```

## Configuration

Core settings:

- `ORIONXCORE_MODEL`
- `ORIONXCORE_API_KEY`
- `ORIONXCORE_API_BASE_URL`

Optional tool settings:

- `ORIONXCORE_ENABLE_TERMINAL`
- `ORIONXCORE_ENABLE_DATABASE`
- `ORIONXCORE_DATABASE_URL`
- `ORIONXCORE_ALLOW_RISKY_COMMANDS`

## API

### Health

```bash
curl http://localhost:8080/health
```

### List available tools

```bash
curl http://localhost:8080/v1/tools
```

### Agent request

```bash
curl -X POST http://localhost:8080/v1/agent/respond \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "List the files in the current workspace and summarize the project structure."}
    ]
  }'
```

### SSE streaming

```bash
curl -N -X POST http://localhost:8080/v1/agent/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Check the current directory and tell me what you find."}
    ]
  }'
```

### OpenAI-compatible chat completions

Non-streaming request:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [
      {"role": "user", "content": "Summarize this project."}
    ]
  }'
```

Tool-calling request:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [
      {"role": "user", "content": "Inspect the workspace."}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "run_terminal_command",
          "description": "Execute a shell command in the configured workspace.",
          "parameters": {
            "type": "object",
            "properties": {
              "command": {"type": "string"}
            },
            "required": ["command"]
          }
        }
      }
    ],
    "tool_choice": "auto",
    "parallel_tool_calls": false
  }'
```

If the response returns `finish_reason: "tool_calls"`, execute the requested tool client-side, append:

- the assistant message containing `tool_calls`
- a `tool` role message with `tool_call_id`, `name`, and serialized tool result

Then call `/v1/chat/completions` again with the expanded `messages` array to continue the interaction.

## Database Notes

The database tool supports:

- SQLite through SQLAlchemy
- MySQL and PostgreSQL through SQLAlchemy when the corresponding driver is installed
- MongoDB when `pymongo` is installed and `ORIONXCORE_DATABASE_URL` uses a MongoDB URI

By default, mutation statements are blocked. Enable `ORIONXCORE_DATABASE_ALLOW_MUTATION=true` only when that is explicitly desired.

## Next Build Steps

- Session persistence and resumable conversations
- Better sandboxing and approval workflows for terminal execution
- Native streaming from model providers
- Richer file-system tools
- Structured tool plugin loading from external packages
- Auth, rate limiting, and audit logs
