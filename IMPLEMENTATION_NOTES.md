# OrionXCore 实现说明

这份文档整理了 OrionXCore 当前的实现状态，重点说明当前架构、请求流转、数据库能力以及 CLI 的实现方式。

## 1. 当前定位

OrionXCore 当前处于 Alpha 到 PoC 之间的阶段，主要提供两种使用模式：

- Agent 模式：通过 `/v1/agent/respond` 和 `/v1/agent/stream`
- OpenAI 兼容模式：通过 `/v1/chat/completions`

目前实现最完整、最有辨识度的一条能力链是 ClickHouse 数据库工作流。

## 2. 运行架构

当前主要运行组件如下：

- API 层：`src/orionxcore/api/routes.py`
- Agent 编排：`src/orionxcore/services/agent.py`
- 模型客户端：`src/orionxcore/llm/openai_compat.py`
- Tool 系统：`src/orionxcore/tools/*`
- 配置管理：`src/orionxcore/config.py`
- CLI 客户端：`src/orionxcore/cli.py`

应用入口：

- `src/orionxcore/main.py`

## 3. API 面

### 3.1 健康检查与工具发现

- `GET /health`
- `GET /v1/tools`

### 3.2 Agent 模式

- `POST /v1/agent/respond`
- `POST /v1/agent/stream`

这条链路是服务端主导的。服务会自己决定是否调用工具、是否继续多轮推理，并在最终返回中附带中间事件。

### 3.3 OpenAI 兼容模式

- `POST /v1/chat/completions`

这条链路更接近 OpenAI 的客户端驱动方式，目前已经支持：

- `tools`
- `tool_choice`
- `parallel_tool_calls`
- `temperature`、`top_p`、`max_tokens`、`stop`
- 非流式和流式输出
- `tool` 消息 continuation
- DeepSeek 所需的 `reasoning_content` 回传

## 4. 模型接入层

当前模型客户端是：

- `src/orionxcore/llm/openai_compat.py`

它默认面向 OpenAI 兼容的 `/chat/completions` 接口，目前负责：

- 发送标准工具定义
- 解析模型返回的 tool calls
- 将内容块整理为文本
- 保留原始 assistant message 到 `raw_message`

这里保留 `raw_message` 很重要，因为部分模型提供方，例如 DeepSeek，会要求在后续 continuation 时把 `reasoning_content` 一起传回。

## 5. Agent Loop

服务端主循环实现位于：

- `src/orionxcore/services/agent.py`

整体流程如下：

1. 组装消息列表
2. 向模型发请求
3. 如果模型返回 tool calls：
   - 发出 `tool_call` 事件
   - 执行工具
   - 发出 `tool_result` 事件
   - 把工具结果追加为 `tool` 消息
   - 继续下一轮
4. 如果模型不再返回 tool calls：
   - 发出最终 assistant 事件
   - 返回最终结果

针对数据库工具，Agent 还会额外发出更细粒度事件：

- `database_trace`
- `database_schema_context`
- `database_sql_attempt`
- `database_result_summary`

这些事件来自数据库工具返回的 `trace` 数据。

## 6. 数据库实现

当前数据库能力已经刻意收敛为 ClickHouse-only。

实现文件：

- `src/orionxcore/tools/database.py`

### 6.1 当前支持的操作

- `query`
- `list_tables`
- `describe_table`
- `text_to_sql`

### 6.2 安全模型

当前数据库安全边界包括：

- 只支持 ClickHouse
- 只允许单条 SQL
- 只允许只读语句
- 限制最大返回行数
- 通过 `SET max_execution_time` 设置查询超时
- 支持库白名单限制

相关配置项：

- `ORIONXCORE_ENABLE_DATABASE`
- `ORIONXCORE_DATABASE_URL`
- `ORIONXCORE_DATABASE_MAX_ROWS`
- `ORIONXCORE_DATABASE_QUERY_TIMEOUT_SECONDS`
- `ORIONXCORE_DATABASE_ALLOWED_DATABASES`
- `ORIONXCORE_DATABASE_ALLOW_MUTATION`

### 6.3 Schema 探测

当前已经实现两个 schema 相关操作：

- `list_tables`
- `describe_table`

此外还有一个内部 schema context 构建逻辑，供 Text-to-SQL 使用。

### 6.4 Text-to-SQL 主链路

`text_to_sql` 当前流程如下：

1. 从 ClickHouse 元数据表构建 schema context
2. 调用模型生成只读 ClickHouse SQL
3. 执行 SQL
4. 如果执行失败，则带上：
   - 上一次 SQL
   - 执行错误
   再次请求模型修正 SQL
5. 自动重试一次
6. 返回最终结果和 trace 数据

当前返回的 trace 信息包括：

- 原始问题
- schema context
- 每次尝试的 SQL
- 重试原因
- 最终 SQL
- 尝试次数

## 7. CLI

CLI 入口：

- `orionx`

实现文件：

- `src/orionxcore/cli.py`

当前支持的命令：

- `orionx ask "prompt"`
- `orionx ask "prompt" --raw`
- `orionx chat`

### 7.1 `ask`

这条命令会调用 `/v1/agent/respond`，并格式化输出：

- 最终 assistant 响应
- iteration 事件
- tool 事件
- 数据库 trace 事件

### 7.2 `chat`

这是最小版交互式会话模式，支持：

- 未指定时自动生成 `session_id`
- 多轮复用同一个 `session_id`
- 输入 `quit` 或 `exit` 退出
- 支持 `--raw`

### 7.3 CLI 的 HTTP 行为

CLI 当前使用 `httpx`，并显式设置了：

- 自定义超时
- `trust_env=False`

这一点非常重要，因为之前本地请求 `127.0.0.1` 时，会被系统代理环境变量影响，导致 CLI 返回错误而 `curl` 正常。

## 8. 测试覆盖

目前已经有比较实用的测试覆盖，主要包括：

- 健康检查接口
- OpenAI 兼容 chat completions
- tool-calling continuation
- 数据库工具能力
- Agent 模式下的数据库 trace 事件
- CLI 的格式化输出与交互行为

代表性测试文件：

- `tests/test_health.py`
- `tests/test_chat_completions.py`
- `tests/test_database_tool.py`
- `tests/test_agent_database_events.py`
- `tests/test_cli.py`

## 9. 当前已知缺口

目前仍然存在的关键缺口包括：

- 还没有真正的服务端 session 持久化
- Terminal 安全模型还比较基础
- 还没有鉴权、限流、审计这类生产能力
- Text-to-SQL 的结果解释还比较基础
- 数据库支持当前仍然只聚焦 ClickHouse

## 10. 文件系统工具 (新增)

已实现完整的文件系统工具链 (`src/orionxcore/tools/filesystem.py`)：

### 10.1 支持的操作

- `read_file` - 读取文件内容（支持偏移、行数限制）
- `write_file` - 写入文件（支持创建父目录、覆盖控制）
- `append_file` - 追加内容到文件
- `list_dir` - 列出目录（支持递归）
- `make_dir` - 创建目录
- `delete_file` - 删除文件或空目录
- `move` - 移动/重命名文件
- `stat` - 获取文件信息
- `search` - Glob 模式搜索

### 10.2 安全模型

- 路径穿越保护：只允许 workspace 目录及其子目录
- 读写大小限制：默认 1 MiB
- 列表条目限制：默认 500 条
- 写入/删除权限独立控制

### 10.3 配置项

- `ORIONXCORE_ENABLE_FILESYSTEM` - 启用文件系统工具
- `ORIONXCORE_FILESYSTEM_ALLOW_WRITE` - 允许写入操作
- `ORIONXCORE_FILESYSTEM_ALLOW_DELETE` - 允许删除操作
- `ORIONXCORE_FILESYSTEM_MAX_READ_BYTES` - 最大读取字节
- `ORIONXCORE_FILESYSTEM_MAX_WRITE_BYTES` - 最大写入字节
- `ORIONXCORE_FILESYSTEM_MAX_LIST_ENTRIES` - 最大列表条目

## 11. 推荐下一步

基于当前代码状态，比较值得继续推进的方向是：

1. 给数据库结果增加自然语言摘要/解释
2. 在服务端真正持久化 `session_id`
3. 继续完善 CLI 的交互体验
4. 强化 Terminal 的确认机制和安全模型
5. 文件系统工具增强：补丁式修改、文本搜索
