# OrionXCore

```
 ██████╗ ██████╗ ██╗ ██████╗ ███╗   ██╗██╗  ██╗
██╔═══██╗██╔══██╗██║██╔═══██╗████╗  ██║╚██╗██╔╝
██║   ██║██████╔╝██║██║   ██║██╔██╗ ██║ ╚███╔╝
██║   ██║██╔══██╗██║██║   ██║██║╚██╗██║ ██╔██╗
╚██████╔╝██║  ██║██║╚██████╔╝██║ ╚████║██╔╝ ██╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝
```

OrionXCore is a lightweight, configurable AI coding agent service. Configure the model, API Key, and API Base URL to start the service, which provides standard HTTP interfaces for CLI, Web UI, or other clients.

Chinese documentation: [README_zh.md](README_zh.md)

**Documentation**: [Architecture](docs/ARCHITECTURE.md) | [Deployment](docs/DEPLOYMENT.md)

---

## Why OrionXCore?

OrionXCore differs from tools like **OpenAI Codex**, **Claude Code**, and **GitHub Copilot** in several key ways:

| Feature | OrionXCore | Claude Code / Codex | Copilot |
|---------|------------|---------------------|---------|
| **Deployment** | **Self-hosted service** | CLI/Desktop app | IDE extension |
| **Model Flexibility** | Any OpenAI-compatible API | Flexible configuration | Locked to provider |
| **Integration** | **HTTP API** for any client | Direct usage only | IDE only |
| **Database Tools** | ClickHouse only + Text-to-SQL | All databases via MCP | N/A |
| **File System** | Configurable sandbox | Full access | IDE workspace |
| **Customization** | Open source | Closed | Closed |
| **Multi-turn Agent** | **Server-side** loop | Client-side | Single request |

### Key Advantages

1. **API-First Design**: Exposes standard REST/SSE endpoints that any client can call - IDE plugins, web UIs, scripts, or mobile apps.

2. **Model Agnostic**: Works with any OpenAI-compatible API (OpenAI, Azure, DeepSeek, local models via Ollama/vLLM, etc.). You control the model, not the vendor.

3. **Database-Native**: Built-in ClickHouse integration with Text-to-SQL workflow, schema introspection, and automatic SQL retry on errors.

4. **Sandboxed Execution**: Terminal and filesystem tools with configurable security boundaries - path limits, size limits, permission controls.

5. **Open Source**: Fully customizable. Add new tools, modify behavior, integrate with your existing systems.

### When to Use OrionXCore

- **You need a service, not a CLI**: Want to integrate AI coding into your web app, IDE plugin, or automation pipeline.
- **You have your own LLM**: Using self-hosted models or alternative providers.
- **You need a simple ClickHouse-MCP tool**: Natural language queries against ClickHouse or similar data warehouses (although ClickHouse officially provides an MCP server, I find this tool more convenient for my personal needs).
- **You want control**: Customize security policies, tools, and behavior for your environment.

## Goals

- Terminal execution via tool calling
- Database querying via natural language plus Text-to-SQL workflows
- Multi-turn agentic execution with iterative planning and tool use
- OpenAI-compatible model integration with pluggable tools
- REST and SSE endpoints for client integration

Starting from practical needs, continuously improving server-side functionality.

Also building some simple and useful client tools.

## Current Features

This initial scaffold includes:

- FastAPI service with health, tool discovery, REST, and SSE endpoints
- OpenAI-compatible chat-completions client
- Agent loop that supports tool-calling until completion
- Terminal tool with basic risk controls and command execution
- Database tool for ClickHouse
- Environment-driven configuration

## Quick Start

For detailed deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

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

4. Use the CLI:

```bash
orionx ask "List the tables in the monitor database."
orionx ask "Count the rows in metrics and summarize the result." --session-id demo
orionx ask "Show me the raw agent response." --raw
orionx chat
```

5. Open the browser playground:

```text
http://127.0.0.1:8080/playground
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
- `ORIONXCORE_ENABLE_FILESYSTEM`
- `ORIONXCORE_FILESYSTEM_ALLOW_WRITE`
- `ORIONXCORE_FILESYSTEM_ALLOW_DELETE`

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

For database tool calls, `/v1/agent/respond` now includes additional events such as
`database_trace`, `database_schema_context`, `database_sql_attempt`, and
`database_result_summary`.

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

### Browser playground

Open `/playground` in the browser to test `/v1/agent/respond` and `/v1/chat/completions`
with editable JSON payloads and raw response inspection.

## Database Notes

The database tool currently supports ClickHouse only.

- Use a ClickHouse SQLAlchemy URL such as `clickhousedb://username:password@localhost:8123/default`
- Queries are read-only by default
- Only single-statement read-only SQL is allowed
- Result rows are capped by `ORIONXCORE_DATABASE_MAX_ROWS`
- Query timeout is controlled by `ORIONXCORE_DATABASE_QUERY_TIMEOUT_SECONDS`
- Schema introspection supports `list_tables` and `describe_table`
- Natural-language querying now supports a minimal `text_to_sql` flow with one automatic retry on SQL errors
- `ORIONXCORE_DATABASE_ALLOWED_DATABASES` can restrict schema discovery and Text-to-SQL context to an approved database whitelist
- `text_to_sql` responses include trace metadata such as schema context, generated SQL, retry reason, and final SQL

By default, mutation statements are blocked. Enable `ORIONXCORE_DATABASE_ALLOW_MUTATION=true` only when that is explicitly desired.

## Filesystem Notes

The filesystem tool provides safe file operations within a configured workspace.

- Enable with `ORIONXCORE_ENABLE_FILESYSTEM=true`
- Operations: `read_file`, `write_file`, `append_file`, `list_dir`, `make_dir`, `delete_file`, `move`, `stat`, `search`
- Path traversal protection: only allows operations within `ORIONXCORE_FILESYSTEM_WORKDIR` (defaults to `ORIONXCORE_TERMINAL_WORKDIR`)
- Read/write size limits: `ORIONXCORE_FILESYSTEM_MAX_READ_BYTES` and `ORIONXCORE_FILESYSTEM_MAX_WRITE_BYTES` (default 1 MiB)
- Write/delete permissions controlled separately via `ORIONXCORE_FILESYSTEM_ALLOW_WRITE` and `ORIONXCORE_FILESYSTEM_ALLOW_DELETE`

## Next Build Steps

- Web-based demo
- Better sandboxing and approval workflows for terminal execution
- Native streaming from model providers
- Auth, rate limiting, and audit logs
