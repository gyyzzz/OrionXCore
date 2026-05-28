# OrionXCore 技术架构文档

## 1. 项目概述

OrionXCore 是一个轻量级、可配置的 AI 编码代理服务。它提供标准 HTTP 接口，允许 IDE 插件、脚本或 Web UI 调用 AI 代理来执行终端命令和查询数据库。

**版本**: 0.1.0 (Alpha/PoC 阶段)

**核心定位**:
- 提供 Agent 模式（服务端驱动）和 OpenAI 兼容模式（客户端驱动）两种使用方式
- 聚焦 ClickHouse 数据库的自然语言查询和 Text-to-SQL 工作流
- 可扩展的工具系统架构

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Client Layer                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   CLI        │    │   Web UI     │    │  IDE Plugin  │          │
│  │  (orionx)    │    │              │    │              │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
└─────────┼────────────────────┼────────────────────┼─────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  routes.py                                                  │   │
│  │  ├── /health                    (健康检查)                  │   │
│  │  ├── /v1/tools                  (工具发现)                  │   │
│  │  ├── /v1/agent/respond          (Agent 非流式)              │   │
│  │  ├── /v1/agent/stream           (Agent SSE 流式)            │   │
│  │  └── /v1/chat/completions       (OpenAI 兼容)               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Service Layer                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  AgentService (agent.py)                                    │   │
│  │  - 迭代执行循环 (max_iterations)                            │   │
│  │  - 消息组装与工具调用处理                                    │   │
│  │  - SSE 流式事件生成                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LLM Client Layer                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  OpenAICompatibleClient (openai_compat.py)                  │   │
│  │  - HTTP 请求构建                                            │   │
│  │  - 工具定义格式化                                            │   │
│  │  - 响应解析 (ToolCall, LLMResponse)                         │   │
│  │  - DeepSeek reasoning_content 支持                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Tool Layer                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐ │
│  │  TerminalTool        │  │  DatabaseTool        │  │  FileSystemTool      │ │
│  │  - Shell 命令执行    │  │  - ClickHouse 查询   │  │  - 文件读写          │ │
│  │  - 安全策略检查      │  │  - Schema 探测       │  │  - 目录列表          │ │
│  │  - 路径限制          │  │  - Text-to-SQL       │  │  - 安全路径限制      │ │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ToolRegistry (registry.py)                                 │   │
│  │  - 工具收集与过滤                                            │   │
│  │  - OpenAI 工具定义格式化                                     │   │
│  │  - 工具执行调度                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    External Services                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐                │
│  │  LLM API             │  │  ClickHouse          │                │
│  │  (OpenAI兼容接口)    │  │  Database            │                │
│  └──────────────────────┘  └──────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块目录结构

```
src/orionxcore/
├── __init__.py          # 包版本定义
├── main.py              # FastAPI 应用实例 (uvicorn 入口)
├── app.py               # 应用工厂函数 create_app()
├── config.py            # Pydantic Settings 配置管理
├── schemas.py           # Pydantic 数据模型定义
├── cli.py               # 命令行客户端
│
├── api/
│   ├── __init__.py
│   └── routes.py        # FastAPI 路由定义
│
├── llm/
│   ├── __init__.py
│   └── openai_compat.py # OpenAI 兼容 HTTP 客户端
│
├── services/
│   ├── __init__.py
│   └── agent.py         # Agent 服务核心逻辑
│
└── tools/
    ├── __init__.py
    ├── base.py          # 抽象 Tool 基类
    ├── registry.py      # 工具注册与执行管理
    ├── terminal.py      # 终端命令执行工具
    └── database.py      # ClickHouse 数据库工具
```

---

## 3. 核心模块详解

### 3.1 配置系统 (`config.py`)

配置系统使用 `pydantic-settings` 实现，支持环境变量和 `.env` 文件加载。

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORIONXCORE_",   # 环境变量前缀
        env_file=".env",            # 配置文件
        extra="ignore",             # 忽略未定义的变量
    )
```

**核心配置项**:

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `model` | str | `gpt-4.1-mini` | LLM 模型名称 |
| `api_key` | str | 空 | API 密钥 (必需) |
| `api_base_url` | str | OpenAI URL | LLM API 地址 |
| `system_prompt` | str | 默认提示词 | Agent 系统提示 |
| `max_iterations` | int | 6 | Agent 最大迭代次数 |
| `http_timeout` | int | 120 | HTTP 请求超时 (秒) |

**工具配置项**:

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_terminal` | bool | True | 启用终端工具 |
| `terminal_workdir` | Path | 当前目录 | 终端工作目录 |
| `terminal_timeout` | int | 30 | 命令超时 (秒) |
| `allow_risky_commands` | bool | False | 允许危险命令 |
| `enable_database` | bool | False | 启用数据库工具 |
| `database_url` | str | 空 | ClickHouse 连接 URL |
| `database_max_rows` | int | 200 | 最大返回行数 |
| `database_query_timeout_seconds` | int | 30 | 查询超时 (秒) |
| `database_allow_mutation` | bool | False | 允许变更 SQL |
| `database_allowed_databases` | str | 空 | 数据库白名单 |

**配置获取**:
```python
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```
使用 `lru_cache` 确保配置单例，避免重复加载。

---

### 3.2 数据模型 (`schemas.py`)

#### 核心消息模型

```python
class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")  # 允许额外字段

    role: Literal["system", "user", "assistant", "tool"]
    content: Any                              # 支持多种内容类型
    name: str | None = None                   # tool 消息的工具名
    tool_call_id: str | None = None           # tool 消息的调用 ID
```

**关键设计**: `extra="allow"` 支持模型返回额外字段（如 DeepSeek 的 `reasoning_content`），确保兼容性。

#### Agent 请求/响应模型

```python
class AgentRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None            # 会话 ID (待持久化)
    metadata: dict[str, Any] = Field(default_factory=dict)

class AgentEvent(BaseModel):
    type: str                                 # 事件类型
    payload: dict[str, Any]                   # 事件数据

class AgentResponse(BaseModel):
    message: ChatMessage                      # 最终消息
    events: list[AgentEvent] = Field(default_factory=list)  # 事件列表
    iterations: int                           # 执行迭代次数
    session_id: str | None = None
```

#### OpenAI 兼容模型

```python
class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
```

---

### 3.3 Agent 服务 (`services/agent.py`)

AgentService 是核心编排层，实现迭代执行循环。

#### 核心类结构

```python
@dataclass
class ChatCompletionTurnResult:
    content: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str
    model: str
    reasoning_content: str | None = None     # DeepSeek 支持

class AgentService:
    def __init__(self, settings: Settings, registry: ToolRegistry):
        self._settings = settings
        self._registry = registry
        self._client = OpenAICompatibleClient(settings)
```

#### Agent Loop 执行流程

```
┌───────────────────────────────────────────────────────────────────┐
│                      _run_loop()                                   │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  for iteration in range(1, max_iterations + 1):                   │
│      │                                                             │
│      ├─► emit("iteration", {iteration})                           │
│      │                                                             │
│      ├─► LLM API 请求                                              │
│      │   client.complete(messages, tools, ...)                    │
│      │                                                             │
│      ├─► if tool_calls:                                           │
│      │   │                                                         │
│      │   ├─► 构建 assistant message (含 tool_calls)               │
│      │   │   - 保留 reasoning_content (DeepSeek)                  │
│      │   │                                                         │
│      │   ├─► for each tool_call:                                  │
│      │   │   ├─► emit("tool_call", {name, arguments})             │
│      │   │   ├─► registry.execute(name, arguments)                │
│      │   │   ├─► emit("tool_result", {name, result})              │
│      │   │   ├─► emit database_trace events (如果适用)            │
│      │   │   ├─► append tool message                              │
│      │   │                                                         │
│      │   ├─► continue (下一轮迭代)                                 │
│      │                                                             │
│      └─► else (无 tool_calls):                                     │
│          ├─► emit("assistant", {content})                         │
│          ├─► return final_message, iteration                      │
│                                                                    │
│  ──► 达到 max_iterations:                                         │
│      return "最大迭代次数已达到" 消息                              │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

#### 数据库追踪事件

当工具为 `database_query` 时，AgentService 会发出详细追踪事件：

```python
def _emit_tool_trace_events(self, tool_name, result, emit):
    if tool_name != "database_query":
        return

    # 基础追踪信息
    emit(AgentEvent(type="database_trace", payload={
        "question": trace.get("question"),
        "database": trace.get("database"),
        "tables": trace.get("tables"),
        "attempt_count": trace.get("attempt_count"),
        "final_sql": trace.get("final_sql"),
    }))

    # Schema 上下文
    emit(AgentEvent(type="database_schema_context", ...))

    # SQL 尝试记录
    emit(AgentEvent(type="database_sql_attempt", ...))

    # 结果摘要
    emit(AgentEvent(type="database_result_summary", ...))
```

---

### 3.4 LLM 客户端 (`llm/openai_compat.py`)

#### 核心数据结构

```python
@dataclass
class ToolCall:
    id: str                    # 工具调用唯一 ID
    name: str                   # 工具名称
    arguments: dict[str, Any]   # 解析后的参数

@dataclass
class LLMResponse:
    content: str                           # 文本内容
    tool_calls: list[ToolCall]             # 工具调用列表
    raw_message: dict[str, Any]            # 原始消息 (含 reasoning_content)
```

#### HTTP 请求构建

```python
async def complete(self, messages, tools, ...):
    payload = {
        "model": model or settings.model,
        "messages": messages,
        "tools": tools,
        "tool_choice": tool_choice if tool_choice else ("auto" if tools else "none"),
    }
    # 可选参数: parallel_tool_calls, temperature, top_p, max_tokens, stop

    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    response = await client.post(
        f"{settings.api_base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
    )
```

#### 内容扁平化处理

支持多种内容格式：
```python
def _flatten_content(self, content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # 处理多部分内容 [{type: "text", text: "..."}, ...]
        return "\n".join(part for part in parts if part)
    return str(content)
```

---

### 3.5 工具系统 (`tools/`)

#### 抽象基类 (`base.py`)

```python
class Tool(ABC):
    name: str                           # 工具唯一名称
    description: str                    # 工具描述
    input_schema: dict[str, Any]        # JSON Schema 输入定义

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """执行工具，返回结果字典"""
        raise NotImplementedError
```

#### 工具注册表 (`registry.py`)

```python
class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._tools = {tool.name: tool for tool in tools}

    # 工具描述 (用于 /v1/tools)
    def describe(self) -> list[ToolDescriptor]: ...

    # OpenAI 工具定义格式
    def as_openai_tools(self) -> list[dict[str, Any]]:
        return [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            }
        } for tool in self._tools.values()]

    # 按请求过滤工具
    def filtered(self, requested_tools) -> ToolRegistry: ...

    # 执行工具
    async def execute(self, name: str, arguments: dict) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        return await tool.execute(arguments)
```

**工具构建**:
```python
def build_registry(settings: Settings) -> ToolRegistry:
    tools: list[Tool] = []
    if settings.enable_terminal:
        tools.append(TerminalTool(settings))
    if settings.enable_database:
        tools.append(DatabaseTool(settings))
    return ToolRegistry(tools)
```

#### 终端工具 (`terminal.py`)

**输入 Schema**:
```json
{
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Shell 命令"},
        "workdir": {"type": "string", "description": "可选工作目录"},
        "timeout": {"type": "integer", "minimum": 1}
    },
    "required": ["command"]
}
```

**安全策略**:
```python
def _is_risky(self, command: str) -> bool:
    lowered = command.lower()
    risky_terms = (
        "rm -rf /", "mkfs", "shutdown", "reboot", "halt",
        "poweroff", "dd if=", "chmod -r 777 /", ":(){:|:&};:",
    )
    # 检查危险命令模式
    # 检查 sudo/su
```

**路径限制**:
```python
def _resolve_workdir(self, workdir: str | None) -> Path:
    base = settings.terminal_workdir.resolve()
    candidate = (base / workdir).resolve()
    # 防止路径穿越: 只允许 base 目录及其子目录
    if base == candidate or base in candidate.parents:
        return candidate
    return base
```

**执行流程**:
```python
async def execute(self, arguments):
    command = arguments.get("command")
    if self._is_risky(command) and not settings.allow_risky_commands:
        return {"ok": False, "error": "Command blocked", "requires_confirmation": True}

    process = await asyncio.create_subprocess_shell(
        command,
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
```

#### 数据库工具 (`database.py`)

**输入 Schema**:
```json
{
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["query", "list_tables", "describe_table", "text_to_sql"]
        },
        "question": {"type": "string"},
        "statement": {"type": "string"},
        "database": {"type": "string"},
        "table": {"type": "string"},
        "tables": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer", "minimum": 1}
    }
}
```

**操作类型**:

| 操作 | 说明 | 参数 |
|------|------|------|
| `query` | 执行只读 SQL | `statement` |
| `list_tables` | 列出数据库表 | `database` (可选) |
| `describe_table` | 描述表结构 | `table`, `database` (可选) |
| `text_to_sql` | 自然语言转 SQL | `question`, `database`, `tables` (可选) |

**安全模型**:
```python
def _validate_read_only_statement(self, statement):
    # 只允许单条 SQL
    if self._contains_multiple_statements(statement):
        return {"ok": False, "error": "Multiple SQL statements not allowed"}

    # 只允许只读语句
    allowed_prefixes = ("select", "show", "describe", "desc", "explain", "with")

    # 检查变更语句
    if self._looks_mutating(statement):
        return {"ok": False, "error": "Mutation statements blocked"}
```

**Text-to-SQL 流程**:
```
┌─────────────────────────────────────────────────────────────────┐
│                      _text_to_sql()                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 构建 schema_context                                          │
│     ├─► 查询 system.columns 获取表结构                           │
│     ├─► 应用 database白名单过滤                                   │
│     ├─► 生成格式化 schema 文本                                    │
│                                                                  │
│  2. 第一次 SQL 生成                                              │
│     ├─► LLM API 请求 (system_prompt + schema + question)        │
│     ├─► 执行 SQL                                                 │
│                                                                  │
│  3. if 执行成功:                                                 │
│     ├─► trace["attempt_count"] = 1                              │
│     ├─► 返回结果 + trace                                         │
│                                                                  │
│  4. else 执行失败:                                               │
│     ├─► 记录错误                                                 │
│     ├─► 第二次 SQL 生成 (带 previous_sql + previous_error)      │
│     ├─► 执行修正后的 SQL                                         │
│     ├─► trace["attempt_count"] = 2                              │
│     ├─► 返回结果 + trace                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Trace 数据结构**:
```python
trace = {
    "question": "查询问题",
    "operation": "text_to_sql",
    "database": "目标数据库",
    "tables": ["相关表列表"],
    "schema_context": "Schema 文本",
    "attempts": [
        {"attempt": 1, "sql": "第一次SQL", "error": "错误信息"},
        {"attempt": 2, "sql": "修正SQL", "retry_reason": "重试原因"}
    ],
    "attempt_count": 2,
    "final_sql": "最终执行的SQL"
}
```

#### 文件系统工具 (`filesystem.py`)

**输入 Schema**:
```json
{
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["read_file", "write_file", "append_file", "list_dir",
                     "make_dir", "delete_file", "move", "stat", "search"]
        },
        "path": {"type": "string"},
        "destination": {"type": "string"},
        "content": {"type": "string"},
        "encoding": {"type": "string"},
        "offset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1},
        "pattern": {"type": "string"},
        "recursive": {"type": "boolean"},
        "create_parents": {"type": "boolean"},
        "overwrite": {"type": "boolean"}
    },
    "required": ["operation"]
}
```

**操作类型**:

| 操作 | 说明 | 参数 |
|------|------|------|
| `read_file` | 读取文件内容 | `path`, `encoding`, `offset`, `limit` |
| `write_file` | 写入文件 | `path`, `content`, `encoding`, `create_parents`, `overwrite` |
| `append_file` | 追加内容 | `path`, `content`, `encoding`, `create_parents` |
| `list_dir` | 列出目录 | `path`, `recursive`, `limit` |
| `make_dir` | 创建目录 | `path`, `create_parents` |
| `delete_file` | 删除文件/空目录 | `path` |
| `move` | 移动/重命名 | `path`, `destination`, `overwrite`, `create_parents` |
| `stat` | 文件信息 | `path` |
| `search` | Glob 搜索 | `pattern`, `path`, `limit` |

**安全模型**:

```python
def _resolve_path(self, raw: str | None) -> Path | dict[str, Any]:
    # 防止路径穿越: 只允许 workspace 目录及其子目录
    base = self._workspace_root()
    candidate = (base / raw).resolve()
    if candidate != base and base not in candidate.parents:
        return {"ok": False, "error": f"Path escapes workspace root: {candidate}"}
    return candidate
```

**配置项**:

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_filesystem` | bool | False | 启用文件系统工具 |
| `filesystem_workdir` | Path | None | 工作目录 (默认用 terminal_workdir) |
| `filesystem_allow_write` | bool | True | 允许写入操作 |
| `filesystem_allow_delete` | bool | False | 允许删除操作 |
| `filesystem_max_read_bytes` | int | 1048576 | 最大读取字节 (1 MiB) |
| `filesystem_max_write_bytes` | int | 1048576 | 最大写入字节 (1 MiB) |
| `filesystem_max_list_entries` | int | 500 | 最大列表条目数 |

**返回格式示例**:

```json
// read_file
{
    "ok": true,
    "path": "/workspace/hello.txt",
    "content": "Hello World",
    "line_count": 1,
    "returned_lines": 1,
    "offset": 0,
    "truncated": false,
    "size_bytes": 11
}

// list_dir
{
    "ok": true,
    "path": "/workspace",
    "entry_count": 3,
    "entries": [
        {"name": "src", "is_dir": true, "relative_path": "src"},
        {"name": "README.md", "is_file": true, "size_bytes": 1024}
    ],
    "truncated": false
}

// search
{
    "ok": true,
    "base": "/workspace",
    "pattern": "**/*.py",
    "match_count": 5,
    "matches": ["/workspace/main.py", "/workspace/utils.py"],
    "truncated": false
}
```

---

### 3.6 API 路由 (`api/routes.py`)

#### 路由定义

```python
router = APIRouter()

# 健康检查
@router.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    return {
        "name": settings.app_name,
        "status": "ok",
        "terminal_enabled": settings.enable_terminal,
        "database_enabled": settings.enable_database,
    }

# 工具发现
@router.get("/v1/tools")
async def list_tools(settings: Settings = Depends(get_settings)):
    return build_registry(settings).describe()

# Agent 非流式响应
@router.post("/v1/agent/respond")
async def respond(request: AgentRequest, agent_service: AgentService):
    return await agent_service.run(request)

# Agent SSE 流式
@router.post("/v1/agent/stream")
async def stream(request: AgentRequest, agent_service: AgentService):
    async def event_stream():
        for event in agent_service.stream(request):
            yield f"event: {event.type}\n"
            yield f"data: {json.dumps(event.payload)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

# OpenAI 兼容 Chat Completions
@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, agent_service):
    if request.stream:
        # SSE 流式输出
        async def event_stream():
            for chunk in agent_service.stream_chat_completion(request):
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    return await agent_service.run_chat_completion(request)
```

#### 依赖注入

```python
def get_agent_service(settings: Settings = Depends(get_settings)) -> AgentService:
    return AgentService(settings=settings, registry=build_registry(settings))
```

使用 FastAPI 的依赖注入系统，自动组装服务和工具。

---

### 3.7 CLI 客户端 (`cli.py`)

#### 命令结构

```bash
orionx [全局选项] <命令> [命令选项] [参数]
```

**全局选项**:
- `--base-url`: 服务地址 (默认 http://127.0.0.1:8080)
- `--timeout`: HTTP 超时 (默认 120s)

**命令**:
- `ask`: 单次查询
- `chat`: 交互式会话

#### ask 命令

```python
def ask(base_url, timeout, prompt, session_id, raw):
    client = httpx.Client(timeout=timeout, trust_env=False)  # 关键: 禁用代理

    response = client.post(
        f"{base_url}/v1/agent/respond",
        json={"messages": [{"role": "user", "content": prompt}], "session_id": session_id}
    )

    if raw:
        print(response.json())
    else:
        format_events(response.json())
```

#### chat 命令

```python
def chat(base_url, timeout, session_id, raw):
    if not session_id:
        session_id = str(uuid.uuid4())[:8]  # 自动生成会话 ID

    messages = []
    while True:
        prompt = input("> ")
        if prompt in ("quit", "exit"):
            break

        messages.append({"role": "user", "content": prompt})
        response = client.post(f"{base_url}/v1/agent/respond", json={...})
        messages.append(response.json()["message"])

        format_events(response.json())
```

**关键设计**: `trust_env=False` 防止本地请求被系统代理拦截。

---

## 4. 请求处理流程

### 4.1 Agent 模式请求流程

```
Client
  │
  │ POST /v1/agent/respond
  │ Body: {messages: [{role: "user", content: "..."}]}
  │
  ▼
routes.py: respond()
  │
  │ Depends(get_agent_service)
  │ → AgentService(settings, registry)
  │
  ▼
AgentService.run()
  │
  │ _build_messages() → 添加 system_prompt
  │
  ▼
_run_loop()
  │
  │ iteration 1:
  │ ├─► emit("iteration", {iteration: 1})
  │ ├─► OpenAICompatibleClient.complete()
  │ │    → POST {api_base_url}/chat/completions
  │ │    → 返回 LLMResponse
  │ │
  │ ├─► if tool_calls:
  │ │    ├─► emit("tool_call", {name, arguments})
  │ │    ├─► ToolRegistry.execute(name, arguments)
  │ │    │    → TerminalTool/DatabaseTool.execute()
  │ │    ├─► emit("tool_result", {name, result})
  │ │    ├─► append tool message
  │ │    └─► continue
  │ │
  │ └─► else:
  │      ├─► emit("assistant", {content})
  │      └─► return ChatMessage, iteration
  │
  ▼
AgentResponse
  │
  │ {message, events, iterations, session_id}
  │
  ▼
Client (JSON 响应)
```

### 4.2 OpenAI 兼容模式请求流程

```
Client
  │
  │ POST /v1/chat/completions
  │ Body: {model, messages, tools, tool_choice, stream}
  │
  ▼
routes.py: chat_completions()
  │
  ▼
AgentService.run_chat_completion() / stream_chat_completion()
  │
  │ _run_chat_completion_turn()
  │ ├─► _build_messages() (无 system_prompt)
  │ ├─► registry.filtered(request.tools)
  │ ├─► OpenAICompatibleClient.complete()
  │ │
  │ ├─► if tool_calls:
  │ │    └─► ChatCompletionTurnResult(finish_reason="tool_calls")
  │ │
  │ └─► else:
  │      └─► ChatCompletionTurnResult(finish_reason="stop")
  │
  ▼
ChatCompletionResponse
  │
  │ {id, object, created, model, choices, usage}
  │ choices[0].message = {role, content, tool_calls, reasoning_content}
  │
  ▼
Client (OpenAI 格式响应)
```

**客户端续接流程**:
```
1. 收到 finish_reason="tool_calls" 的响应
2. 客户端本地执行工具
3. 构建 messages:
   - 原 messages
   - assistant message (含 tool_calls)
   - tool message (tool_call_id, name, content)
4. 再次 POST /v1/chat/completions
5. 继续对话
```

---

## 5. 扩展开发指南

### 5.1 添加新工具

1. **创建工具类**:

```python
# src/orionxcore/tools/my_tool.py
from orionxcore.tools.base import Tool
from orionxcore.config import Settings

class MyTool(Tool):
    name = "my_tool"
    description = "My custom tool description"
    input_schema = {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parameter 1"},
        },
        "required": ["param1"],
    }

    def __init__(self, settings: Settings):
        self._settings = settings

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        param1 = arguments.get("param1")
        # 执行逻辑
        return {"ok": True, "result": "..."}
```

2. **注册工具**:

```python
# src/orionxcore/tools/registry.py
def build_registry(settings: Settings) -> ToolRegistry:
    tools: list[Tool] = []
    if settings.enable_terminal:
        tools.append(TerminalTool(settings))
    if settings.enable_database:
        tools.append(DatabaseTool(settings))
    if settings.enable_my_tool:  # 新增配置项
        tools.append(MyTool(settings))
    return ToolRegistry(tools)
```

3. **添加配置项**:

```python
# src/orionxcore/config.py
class Settings(BaseSettings):
    enable_my_tool: bool = False
    my_tool_option: str = "default"
```

### 5.2 添加新 API 端点

```python
# src/orionxcore/api/routes.py
from orionxcore.schemas import MyRequest, MyResponse

@router.post("/v1/my_endpoint", response_model=MyResponse)
async def my_endpoint(
    request: MyRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    # 处理逻辑
    return MyResponse(...)
```

### 5.3 自定义 LLM 客户端

如需支持非 OpenAI 兼容的模型：

1. 创建新客户端类:
```python
# src/orionxcore/llm/my_client.py
class MyLLMClient:
    async def complete(self, messages, tools, ...) -> LLMResponse:
        # 自定义请求逻辑
        ...
```

2. 在 AgentService 中使用:
```python
class AgentService:
    def __init__(self, settings, registry):
        if settings.llm_provider == "my_provider":
            self._client = MyLLMClient(settings)
        else:
            self._client = OpenAICompatibleClient(settings)
```

---

## 6. 测试架构

### 6.1 测试文件结构

```
tests/
├── test_health.py              # 健康检查端点
├── test_chat_completions.py    # OpenAI 兼容接口
├── test_database_tool.py       # 数据库工具操作
├── test_agent_database_events.py  # Agent 数据库事件
└── test_cli.py                 # CLI 格式化输出
```

### 6.2 测试策略

使用 `pytest` + `fastapi.testclient.TestClient`:

```python
from fastapi.testclient import TestClient
from orionxcore.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

**数据库工具测试**: 使用 mock 或配置测试 ClickHouse 实例。

---

## 7. 部署架构

### 7.1 单机部署

```bash
# 安装
pip install -e .

# 配置
cp .env.example .env
# 编辑 .env

# 启动
uvicorn orionxcore.main:app --host 0.0.0.0 --port 8080
```

### 7.2 生产部署建议

- 使用 Gunicorn + Uvicorn workers
- 配置反向代理 (Nginx)
- 启用 HTTPS
- 添加认证中间件
- 配置日志和监控

---

## 8. 当前限制与未来规划

### 8.1 当前限制

- 无服务端 session 持久化
- 无文件系统工具
- 终端安全模型较基础
- 无认证、限流、审计
- 仅支持 ClickHouse 数据库

### 8.2 未来规划

1. **Session 持久化**: 服务端存储会话历史
2. **文件系统工具**: 文件读写、编辑
3. **增强终端安全**: 确认机制、沙箱执行
4. **认证系统**: API Key 验证、JWT
5. **多数据库支持**: PostgreSQL、MySQL 等
6. **审计日志**: 操作记录、追溯

---

## 9. 附录

### 9.1 环境变量完整列表

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ORIONXCORE_APP_NAME` | 应用名称 | OrionXCore |
| `ORIONXCORE_HOST` | 服务主机 | 0.0.0.0 |
| `ORIONXCORE_PORT` | 服务端口 | 8080 |
| `ORIONXCORE_MODEL` | LLM 模型 | gpt-4.1-mini |
| `ORIONXCORE_API_KEY` | API 密钥 | (必需) |
| `ORIONXCORE_API_BASE_URL` | API 地址 | https://api.openai.com/v1 |
| `ORIONXCORE_SYSTEM_PROMPT` | 系统提示词 | 默认值 |
| `ORIONXCORE_MAX_ITERATIONS` | 最大迭代 | 6 |
| `ORIONXCORE_HTTP_TIMEOUT` | HTTP 超时 | 120 |
| `ORIONXCORE_ENABLE_TERMINAL` | 启用终端 | true |
| `ORIONXCORE_TERMINAL_WORKDIR` | 工作目录 | . |
| `ORIONXCORE_TERMINAL_TIMEOUT` | 命令超时 | 30 |
| `ORIONXCORE_ALLOW_RISKY_COMMANDS` | 允许危险命令 | false |
| `ORIONXCORE_ENABLE_DATABASE` | 启用数据库 | false |
| `ORIONXCORE_DATABASE_URL` | 数据库 URL | (必需) |
| `ORIONXCORE_DATABASE_MAX_ROWS` | 最大行数 | 200 |
| `ORIONXCORE_DATABASE_QUERY_TIMEOUT_SECONDS` | 查询超时 | 30 |
| `ORIONXCORE_DATABASE_ALLOW_MUTATION` | 允许变更 | false |
| `ORIONXCORE_DATABASE_ALLOWED_DATABASES` | 数据库白名单 | (空) |
| `ORIONXCORE_ENABLE_FILESYSTEM` | 启用文件系统 | false |
| `ORIONXCORE_FILESYSTEM_ALLOW_WRITE` | 允许写入 | true |
| `ORIONXCORE_FILESYSTEM_ALLOW_DELETE` | 允许删除 | false |
| `ORIONXCORE_FILESYSTEM_MAX_READ_BYTES` | 最大读取字节 | 1048576 |
| `ORIONXCORE_FILESYSTEM_MAX_WRITE_BYTES` | 最大写入字节 | 1048576 |
| `ORIONXCORE_FILESYSTEM_MAX_LIST_ENTRIES` | 最大列表条目 | 500 |

### 9.2 事件类型列表

| 事件类型 | 说明 | payload |
|----------|------|---------|
| `iteration` | 迭代开始 | `{iteration: int}` |
| `tool_call` | 工具调用 | `{name, arguments}` |
| `tool_result` | 工具结果 | `{name, result}` |
| `assistant` | 最终响应 | `{content}` |
| `final` | SSE 结束 | `{message, iterations, session_id}` |
| `database_trace` | 数据库追踪 | `{question, database, tables, attempt_count, final_sql}` |
| `database_schema_context` | Schema 上下文 | `{schema_context}` |
| `database_sql_attempt` | SQL 尝试 | `{attempt, sql, retry_reason, error}` |
| `database_result_summary` | 结果摘要 | `{ok, row_count, columns, generated_sql}` |

### 9.3 工具返回格式

**终端工具**:
```json
{
    "ok": true,
    "command": "ls -la",
    "workdir": "/path/to/dir",
    "exit_code": 0,
    "stdout": "...",
    "stderr": ""
}
```

**数据库工具**:
```json
{
    "ok": true,
    "dialect": "clickhouse",
    "row_count": 10,
    "columns": ["col1", "col2"],
    "rows": [{...}, ...],
    "generated_sql": "SELECT ...",  // text_to_sql 专用
    "trace": {...}                   // text_to_sql 专用
}
```

---

*文档版本: 0.1.0 | 最后更新: 2026-05-27*