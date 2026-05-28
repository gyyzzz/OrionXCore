# OrionXCore 中文说明

```
 ██████╗ ██████╗ ██╗ ██████╗ ███╗   ██╗██╗  ██╗
██╔═══██╗██╔══██╗██║██╔═══██╗████╗  ██║╚██╗██╔╝
██║   ██║██████╔╝██║██║   ██║██╔██╗ ██║ ╚███╔╝
██║   ██║██╔══██╗██║██║   ██║██║╚██╗██║ ██╔██╗
╚██████╔╝██║  ██║██║╚██████╔╝██║ ╚████║██╔╝ ██╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝
```

OrionXCore 是一个轻量级、可配置的 AI 编程代理服务。只需要配置模型、API Key 和 API Base URL，即可启动服务，并通过标准 HTTP 接口为 IDE 插件、脚本、Web UI 或其他客户端提供智能编程助手能力。

英文文档: [README.md](README.md)

**文档**: [架构文档](docs/ARCHITECTURE.md) | [部署指南](docs/DEPLOYMENT.md)

---

## 为什么选择 OrionXCore？

OrionXCore 与 **OpenAI Codex**、**Claude Code**、**GitHub Copilot** 等工具的主要区别：

| 特性 | OrionXCore | Claude Code / Codex | Copilot |
|------|------------|---------------------|---------|
| **部署方式** | 自托管服务 | CLI/桌面应用 | IDE 扩展 |
| **模型灵活性** | 任意 OpenAI 兼容 API | 锁定供应商 | 锁定供应商 |
| **集成方式** | HTTP API，任意客户端 | 仅直接使用 | 仅 IDE |
| **数据库工具** | 内置 ClickHouse + Text-to-SQL | 有限/无 | 无 |
| **文件系统** | 可配置沙盒 | 完全访问 | IDE 工作区 |
| **定制化** | 完全开源 | 闭源 | 闭源 |
| **多轮 Agent** | 服务端循环 | 客户端 | 单次请求 |

### 核心优势

1. **API 优先设计**: 暴露标准 REST/SSE 接口，任何客户端都可以调用——IDE 插件、Web UI、脚本或移动应用。

2. **模型无关**: 支持任意 OpenAI 兼容 API（OpenAI、Azure、DeepSeek、本地模型如 Ollama/vLLM 等）。你控制模型，而不是供应商。

3. **数据库原生**: 内置 ClickHouse 集成，支持 Text-to-SQL 工作流、Schema 探测和 SQL 错误自动重试。

4. **沙盒执行**: 终端和文件系统工具具有可配置的安全边界——路径限制、大小限制、权限控制。

5. **开源可定制**: 完全可定制。添加新工具、修改行为、与现有系统集成。

### 适用场景

- **你需要服务，而不是 CLI**: 想将 AI 编程集成到 Web 应用、IDE 插件或自动化流程中。
- **你有自己的 LLM**: 使用自托管模型或替代供应商。
- **你需要数据库查询**: 对 ClickHouse 或类似数据仓库进行自然语言查询。
- **你想要控制**: 为你的环境定制安全策略、工具和行为。

---

## 目标

- 终端执行能力（通过 Tool Calling）
- 数据库自然语言查询 + Text-to-SQL 工作流
- 多轮 Agent 执行（迭代规划与工具调用）
- OpenAI 兼容的模型集成与可插拔工具
- REST 和 SSE 接口供客户端集成

---

## 当前功能

- FastAPI 服务：健康检查、工具发现、REST、SSE 接口
- OpenAI 兼容的 `/chat/completions` 客户端
- Agent 循环：支持工具调用直到完成
- Terminal Tool：基础风险控制与命令执行
- Database Tool：支持 ClickHouse
- Filesystem Tool：文件读写、目录列表、搜索
- 环境变量驱动的配置

---

## 快速开始

详细部署说明请参考 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

1. 创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. 复制配置模板并填写模型设置：

```bash
cp .env.example .env
```

3. 启动服务：

```bash
uvicorn orionxcore.main:app --host 0.0.0.0 --port 8080
```

4. 使用 CLI：

```bash
orionx ask "列出 monitor 库里的表。"
orionx ask "统计 metrics 表总行数并做简要说明" --session-id demo
orionx ask "显示原始 agent 响应" --raw
orionx chat
```

5. 打开浏览器调试页：

```text
http://127.0.0.1:8080/playground
```

---

## 配置

### 核心配置

- `ORIONXCORE_MODEL`
- `ORIONXCORE_API_KEY`
- `ORIONXCORE_API_BASE_URL`

### 工具配置

- `ORIONXCORE_ENABLE_TERMINAL`
- `ORIONXCORE_ENABLE_DATABASE`
- `ORIONXCORE_DATABASE_URL`
- `ORIONXCORE_ALLOW_RISKY_COMMANDS`
- `ORIONXCORE_ENABLE_FILESYSTEM`
- `ORIONXCORE_FILESYSTEM_ALLOW_WRITE`
- `ORIONXCORE_FILESYSTEM_ALLOW_DELETE`

---

## HTTP 接口

### 健康检查

```bash
curl http://localhost:8080/health
```

### 获取可用工具列表

```bash
curl http://localhost:8080/v1/tools
```

### Agent 请求

```bash
curl -X POST http://localhost:8080/v1/agent/respond \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "列出当前工作区中的文件，并总结项目结构。"}
    ]
  }'
```

当 Agent 调用数据库工具时，`/v1/agent/respond` 会附带额外事件：
`database_trace`、`database_schema_context`、`database_sql_attempt`、`database_result_summary`。

### SSE 流式接口

```bash
curl -N -X POST http://localhost:8080/v1/agent/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "检查当前目录并告诉我你发现了什么。"}
    ]
  }'
```

### OpenAI 兼容接口

普通请求：

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [
      {"role": "user", "content": "总结一下这个项目。"}
    ]
  }'
```

带工具的请求：

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [
      {"role": "user", "content": "检查当前工作区。"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "run_terminal_command",
          "description": "在配置好的工作目录中执行 Shell 命令。",
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

如果响应返回 `finish_reason: "tool_calls"`，客户端需执行工具，然后追加：
- 包含 `tool_calls` 的 assistant 消息
- 带 `tool_call_id`、`name` 和工具结果的 `tool` 消息

再次调用 `/v1/chat/completions` 继续对话。

### 浏览器 Playground

访问 `/playground` 可在浏览器中调试 `/v1/agent/respond` 和 `/v1/chat/completions`，支持编辑 JSON 请求体和查看原始响应。

---

## 数据库说明

当前数据库工具仅支持 ClickHouse。

- 连接串格式：`clickhousedb://username:password@localhost:8123/default`
- 默认只允许只读查询
- 只允许单条只读 SQL，不允许多语句执行
- 返回行数受 `ORIONXCORE_DATABASE_MAX_ROWS` 控制
- 查询超时由 `ORIONXCORE_DATABASE_QUERY_TIMEOUT_SECONDS` 控制
- Schema 探测支持 `list_tables` 和 `describe_table`
- 自然语言查询支持最小版 `text_to_sql` 流程，SQL 执行失败时自动重试一次
- 可通过 `ORIONXCORE_DATABASE_ALLOWED_DATABASES` 限制访问白名单库
- `text_to_sql` 返回包含 trace 信息：schema 上下文、生成 SQL、重试原因、最终 SQL

默认情况下，数据库写操作是关闭的。仅在明确需要时开启：

```env
ORIONXCORE_DATABASE_ALLOW_MUTATION=true
```

---

## 文件系统说明

文件系统工具在配置的工作区内提供安全的文件操作。

- 启用：`ORIONXCORE_ENABLE_FILESYSTEM=true`
- 操作：`read_file`、`write_file`、`append_file`、`list_dir`、`make_dir`、`delete_file`、`move`、`stat`、`search`
- 路径穿越保护：只允许 `ORIONXCORE_FILESYSTEM_WORKDIR` 内的操作（默认使用 `ORIONXCORE_TERMINAL_WORKDIR`）
- 读写大小限制：`ORIONXCORE_FILESYSTEM_MAX_READ_BYTES` 和 `ORIONXCORE_FILESYSTEM_MAX_WRITE_BYTES`（默认 1 MiB）
- 写入/删除权限分别通过 `ORIONXCORE_FILESYSTEM_ALLOW_WRITE` 和 `ORIONXCORE_FILESYSTEM_ALLOW_DELETE` 控制

---

## 下一步开发

完整开发路线图请参考 [TODO.md](TODO.md)。

- 会话持久化与可恢复对话
- 更好的终端执行沙箱与审批流程
- 模型原生流式输出
- 外部工具插件动态加载
- 鉴权、限流、审计日志