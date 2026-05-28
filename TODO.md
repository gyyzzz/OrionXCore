# OrionXCore TODO

当前阶段目标：把项目从 Alpha 骨架推进到“数据库优先、具备基础交互能力的可用 PoC”。

## 当前状态

已完成：

- [X]  服务骨架：FastAPI、REST、SSE、配置加载
- [X]  OpenAI 兼容 `chat/completions` 基础能力
- [X]  DeepSeek `reasoning_content` continuation 兼容
- [X]  ClickHouse-only 数据库能力收敛
- [X]  数据库 schema introspection：`list_tables`、`describe_table`
- [X]  最小版 Text-to-SQL
- [X]  SQL 自动修正重试一次
- [X]  数据库 trace 返回
- [X]  Agent 数据库事件流
- [X]  数据库白名单
- [X]  只读 SQL / 单语句限制 / 查询超时
- [X]  最小 CLI：`orionx ask`

进行中：

- [ ]  CLI 交互式会话：`orionx chat`

## 优先级

1. 数据库能力继续增强
2. CLI / 交互体验
3. Agent 会话能力
4. Terminal 安全与执行
5. 文件系统 Tool
6. 可观测性与接入体验

## 阶段 1：数据库能力

### 1.1 ClickHouse 基础

- [X]  只保留 ClickHouse
- [X]  补 ClickHouse 连接配置
- [X]  工具层报告数据库方言
- [X]  配置库白名单

### 1.2 Schema 探测

- [X]  `list_tables`
- [X]  `describe_table`
- [X]  schema context 构建
- [X]  白名单约束 schema 探测

### 1.3 Text-to-SQL

- [X]  自然语言问题转 SQL
- [X]  只读 SQL 生成约束
- [X]  SQL 执行失败自动修正重试
- [X]  返回 `generated_sql`
- [X]  返回 `trace`

### 1.4 数据库安全

- [X]  只允许只读语句
- [X]  禁止多语句执行
- [X]  行数限制
- [X]  查询超时
- [ ]  更细的高风险查询确认机制

### 1.5 数据库下一步

- [ ]  给查询结果增加自然语言摘要/解释
- [ ]  增加表白名单配置
- [ ]  更稳的 SQL 结果截断和大结果说明

## 阶段 2：Agent 与会话

- [X]  Agent 可调用数据库工具
- [X]  Agent 返回数据库细粒度事件
- [X]  工具执行 trace 可观察
- [ ]  服务侧真正持久化 `session_id`
- [ ]  多轮数据库追问稳定延续
- [ ]  数据库结果解释进一步融入 Agent

## 阶段 3：CLI / 交互体验

- [X]  `orionx ask`
- [X]  `--raw`
- [X]  基础事件格式化
- [ ]  `orionx chat`
- [ ]  更细的输出控制：`--quiet`、`--show-events`
- [ ]  数据库事件更好的表格化展示

## 阶段 4：Terminal 能力

- [ ]  更细的风险分级
- [ ]  更清晰的确认机制
- [ ]  输出截断与审计增强

## 阶段 5：文件系统 Tool

- [X]  文件系统工具基础框架
- [X]  `list_dir` - 目录列表（支持递归）
- [X]  `read_file` - 文件读取（支持偏移、限制）
- [X]  `write_file` - 文件写入
- [X]  `append_file` - 文件追加
- [X]  `make_dir` - 创建目录
- [X]  `delete_file` - 删除文件/空目录
- [X]  `move` - 移动/重命名
- [X]  `stat` - 文件信息
- [X]  `search` - Glob 搜索
- [X]  路径安全限制（防止穿越工作目录）
- [X]  读写大小限制配置
- [X]  写入/删除权限独立控制

## 当前推荐执行顺序

1. 完成 `orionx chat`
2. 给数据库结果增加自然语言摘要/解释
3. 补服务侧 `session_id` 持久化
4. 再继续补 Terminal、文件系统和可观测性

## 当前 PoC 验收情况

- [X]  能连接 ClickHouse
- [X]  能列出表
- [X]  能查看字段
- [X]  能做最小版 Text-to-SQL
- [X]  能自动修正一次 SQL
- [X]  能返回结构化结果与 trace
- [X]  能通过 Agent 事件流观察数据库执行过程
- [ ]  能在稳定的多轮 session 中持续追问
