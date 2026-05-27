# OrionXCore 中文说明

OrionXCore 是一个轻量级、可配置的 AI 编程代理服务。只需要配置模型、API Key 和 API Base URL，即可启动服务，并通过标准 HTTP 接口为 IDE 插件、脚本、Web UI 或其他客户端提供类似 Codex / Claude Code 的智能编程助手能力。

## 项目目标

- 提供终端执行能力
- 提供数据库自然语言查询能力
- 支持多轮 Agent 式任务执行
- 兼容 OpenAI 风格模型接口
- 通过插件化 Tool 扩展终端、数据库、文件系统等能力

## 当前初始化版本包含

- 基于 FastAPI 的 HTTP 服务
- 健康检查、工具列表、普通响应、SSE 流式响应接口
- OpenAI 兼容的 `/chat/completions` 调用客户端
- 基础 Agent Loop，可在模型与 Tool 之间多轮迭代
- Terminal Tool，支持命令执行和基础风险拦截
- Database Tool，目前仅支持 ClickHouse
- 基于环境变量的配置加载

## 核心能力规划

### 1. Terminal 执行能力

- 接收自然语言指令并驱动模型生成命令
- 支持执行 Shell 命令并返回 stdout、stderr、exit code
- 支持命令失败后的继续推理和重试
- 支持危险命令拦截与确认机制

### 2. 数据库智能查询

- 配置数据库连接后执行数据库查询
- 当前阶段优先支持 ClickHouse
- 返回结构化结果，便于上层客户端做展示和解释

说明：
当前版本已具备数据库 Tool 骨架，但“自然语言直接转 SQL”的提示词和约束策略还会在后续继续增强。

### 3. 多轮智能执行

- 保持会话消息上下文
- 支持模型连续调用多个 Tool
- 每一步结果自动反馈给下一轮推理
- 形成基础 ReAct / Agentic Loop

## 目录结构

```text
OrionXCore/
├── .env.example
├── .gitignore
├── README.md
├── README_zh.md
├── pyproject.toml
├── src/
│   └── orionxcore/
│       ├── api/
│       ├── llm/
│       ├── services/
│       ├── tools/
│       ├── app.py
│       ├── config.py
│       ├── main.py
│       └── schemas.py
└── tests/
```

## 环境要求

- Python 3.11 或更高版本

当前本地虚拟环境已按 `Python 3.11.12` 初始化。

## 快速开始

### 1. 激活虚拟环境

```bash
source .venv/bin/activate
```

如果尚未创建虚拟环境，可执行：

```bash
uv venv --python 3.11 .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -e '.[dev,clickhouse]'
```

### 2. 配置环境变量

复制模板文件：

```bash
cp .env.example .env
```

至少需要配置以下字段：

- `ORIONXCORE_MODEL`
- `ORIONXCORE_API_KEY`
- `ORIONXCORE_API_BASE_URL`

### 3. 启动服务

```bash
uvicorn orionxcore.main:app --host 0.0.0.0 --port 8080
```

### 4. 使用 CLI

```bash
orionx ask "列出 monitor 库里的表"
orionx ask "统计 metrics 表总行数并做简要说明" --session-id demo
orionx ask "显示原始 agent 响应" --raw
orionx chat
```

## 配置说明

### 基础配置

- `ORIONXCORE_APP_NAME`：服务名称
- `ORIONXCORE_HOST`：监听地址
- `ORIONXCORE_PORT`：监听端口
- `ORIONXCORE_MODEL`：模型名称
- `ORIONXCORE_API_KEY`：模型服务 API Key
- `ORIONXCORE_API_BASE_URL`：模型服务接口地址
- `ORIONXCORE_SYSTEM_PROMPT`：系统提示词
- `ORIONXCORE_MAX_ITERATIONS`：单次 Agent 最大迭代轮数
- `ORIONXCORE_HTTP_TIMEOUT`：模型请求超时时间

### Terminal Tool 配置

- `ORIONXCORE_ENABLE_TERMINAL`：是否启用终端工具
- `ORIONXCORE_TERMINAL_WORKDIR`：终端默认工作目录
- `ORIONXCORE_TERMINAL_TIMEOUT`：单条命令超时时间
- `ORIONXCORE_ALLOW_RISKY_COMMANDS`：是否允许危险命令

### Database Tool 配置

- `ORIONXCORE_ENABLE_DATABASE`：是否启用数据库工具
- `ORIONXCORE_DATABASE_URL`：数据库连接串
- `ORIONXCORE_DATABASE_MAX_ROWS`：最大返回行数
- `ORIONXCORE_DATABASE_ALLOW_MUTATION`：是否允许写操作

## HTTP 接口

### 1. 健康检查

```bash
curl http://localhost:8080/health
```

### 2. 获取可用工具列表

```bash
curl http://localhost:8080/v1/tools
```

### 3. 普通 Agent 响应接口

```bash
curl -X POST http://localhost:8080/v1/agent/respond \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "列出当前工作区中的文件，并总结项目结构。"
      }
    ]
  }'
```

当 Agent 调用数据库工具时，`/v1/agent/respond` 现在还会附带更细的事件，
例如 `database_trace`、`database_schema_context`、`database_sql_attempt`、
`database_result_summary`，方便前端展示查询过程。

### 4. SSE 流式接口

```bash
curl -N -X POST http://localhost:8080/v1/agent/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "检查当前目录并告诉我你发现了什么。"
      }
    ]
  }'
```

### 5. OpenAI 兼容的 chat completions 接口

普通请求示例：

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

带 Tool 的请求示例：

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

如果响应中返回 `finish_reason: "tool_calls"`，则说明这一轮需要由客户端执行工具。客户端应当：

- 保留 assistant 返回的 `tool_calls`
- 执行对应工具
- 追加一条 `role: "tool"` 的消息，并带上 `tool_call_id`、`name` 和工具执行结果

然后再次调用 `/v1/chat/completions`，把完整的 `messages` 继续传回服务，以完成下一轮生成。

## 数据库支持说明

当前数据库 Tool 目前只支持 ClickHouse：

- 连接串示例：`clickhousedb://username:password@localhost:8123/default`
- 默认只允许只读查询
- 只允许单条只读 SQL，不允许多语句执行
- 查询返回行数受 `ORIONXCORE_DATABASE_MAX_ROWS` 控制
- 查询超时由 `ORIONXCORE_DATABASE_QUERY_TIMEOUT_SECONDS` 控制
- 目前已支持 `list_tables` 和 `describe_table` 这类 schema 探测操作
- 目前已支持最小版 `text_to_sql` 流程，并在 SQL 执行失败时自动修正重试一次
- 可通过 `ORIONXCORE_DATABASE_ALLOWED_DATABASES` 限制 schema 探测和 Text-to-SQL 只访问白名单中的库
- `text_to_sql` 返回里现在会附带 trace 信息，包括 schema 摘要、生成 SQL、重试原因和最终 SQL

默认情况下，数据库写操作是关闭的。只有当明确需要写入时，才建议开启：

```env
ORIONXCORE_DATABASE_ALLOW_MUTATION=true
```

## 当前实现边界

当前版本是初始化骨架，重点是搭建统一服务入口和执行主链路。以下能力还会继续增强：

- 更成熟的会话持久化
- 更严格的终端沙箱和用户确认流程
- 更完善的 Text-to-SQL 提示和数据库安全策略
- 更丰富的文件系统 Tool
- 外部插件发现与动态注册
- 鉴权、限流、审计日志

## 本地验证状态

当前仓库已经完成：

- 虚拟环境创建
- 主依赖与可选依赖安装
- 基础测试通过

已验证命令：

```bash
.venv/bin/python -m pytest -q
```

## 下一步建议

- 补一版真正兼容 OpenAI `chat/completions` 响应结构的接口
- 增加文件系统读写 Tool
- 为 Terminal 和 Database Tool 增加显式审批机制
- 增加会话管理与历史上下文持久化
