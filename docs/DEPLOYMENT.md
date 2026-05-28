# OrionXCore 部署指南

## 版本信息

- 当前版本: v0.2.0
- Python 要求: >= 3.11

---

## 1. 快速部署（本地开发）

### 1.1 安装

```bash
# 克隆仓库
git clone https://github.com/gyyzzz/OrionXCore.git
cd OrionXCore

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .

# 可选: 安装 ClickHouse 支持
pip install -e ".[clickhouse]"

# 可选: 安装开发依赖
pip install -e ".[dev]"
```

### 1.2 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
vim .env
```

**必需配置**:
```bash
ORIONXCORE_MODEL=gpt-4.1-mini          # LLM 模型名称
ORIONXCORE_API_KEY=your_api_key        # API 密钥
ORIONXCORE_API_BASE_URL=https://api.openai.com/v1  # API 地址
```

### 1.3 启动服务

```bash
# 直接启动
uvicorn orionxcore.main:app --host 0.0.0.0 --port 8080

# 或使用 CLI
orionx chat
```

---

## 2. 生产部署

### 2.1 使用 Gunicorn + Uvicorn

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动 (4 workers)
gunicorn orionxcore.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --timeout 120 \
  --keep-alive 5
```

### 2.2 使用 systemd 服务

创建服务文件 `/etc/systemd/system/orionxcore.service`:

```ini
[Unit]
Description=OrionXCore AI Agent Service
After=network.target

[Service]
Type=notify
User=orionx
Group=orionx
WorkingDirectory=/opt/orionxcore
Environment="PATH=/opt/orionxcore/.venv/bin"
ExecStart=/opt/orionxcore/.venv/bin/gunicorn orionxcore.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable orionxcore
sudo systemctl start orionxcore
sudo systemctl status orionxcore
```

### 2.3 Nginx 反向代理

```nginx
upstream orionxcore {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name your-domain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;

    location / {
        proxy_pass http://orionxcore;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }
}
```

---

## 3. Docker 部署

### 3.1 构建镜像

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# 复制配置
COPY .env.example .env

# 暴露端口
EXPOSE 8080

# 启动服务
CMD ["uvicorn", "orionxcore.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

构建:
```bash
docker build -t orionxcore:0.2.0 .
```

### 3.2 运行容器

```bash
docker run -d \
  --name orionxcore \
  -p 8080:8080 \
  -e ORIONXCORE_API_KEY=your_api_key \
  -e ORIONXCORE_MODEL=gpt-4.1-mini \
  -v /path/to/workspace:/workspace \
  orionxcore:0.2.0
```

### 3.3 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  orionxcore:
    image: orionxcore:0.2.0
    ports:
      - "8080:8080"
    environment:
      - ORIONXCORE_API_KEY=${ORIONXCORE_API_KEY}
      - ORIONXCORE_MODEL=gpt-4.1-mini
      - ORIONXCORE_ENABLE_TERMINAL=true
      - ORIONXCORE_ENABLE_FILESYSTEM=true
      - ORIONXCORE_TERMINAL_WORKDIR=/workspace
      - ORIONXCORE_FILESYSTEM_WORKDIR=/workspace
    volumes:
      - ./workspace:/workspace
    restart: unless-stopped
```

运行:
```bash
docker-compose up -d
```

---

## 4. 配置说明

### 4.1 核心配置

| 配置项 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `ORIONXCORE_MODEL` | 是 | `gpt-4.1-mini` | LLM 模型名称 |
| `ORIONXCORE_API_KEY` | 是 | 空 | API 密钥 |
| `ORIONXCORE_API_BASE_URL` | 是 | OpenAI URL | API 基础地址 |
| `ORIONXCORE_SYSTEM_PROMPT` | 否 | 默认提示词 | Agent 系统提示 |
| `ORIONXCORE_MAX_ITERATIONS` | 否 | 6 | 最大迭代次数 |
| `ORIONXCORE_HTTP_TIMEOUT` | 否 | 120 | HTTP 超时 (秒) |

### 4.2 终端工具配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ORIONXCORE_ENABLE_TERMINAL` | `true` | 启用终端工具 |
| `ORIONXCORE_TERMINAL_WORKDIR` | `.` | 工作目录 |
| `ORIONXCORE_TERMINAL_TIMEOUT` | 30 | 命令超时 (秒) |
| `ORIONXCORE_ALLOW_RISKY_COMMANDS` | `false` | 允许危险命令 |

### 4.3 数据库工具配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ORIONXCORE_ENABLE_DATABASE` | `false` | 启用数据库工具 |
| `ORIONXCORE_DATABASE_URL` | 空 | ClickHouse 连接 URL |
| `ORIONXCORE_DATABASE_MAX_ROWS` | 200 | 最大返回行数 |
| `ORIONXCORE_DATABASE_QUERY_TIMEOUT_SECONDS` | 30 | 查询超时 |
| `ORIONXCORE_DATABASE_ALLOW_MUTATION` | `false` | 允许变更操作 |
| `ORIONXCORE_DATABASE_ALLOWED_DATABASES` | 空 | 数据库白名单 |

### 4.4 文件系统工具配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ORIONXCORE_ENABLE_FILESYSTEM` | `false` | 启用文件系统工具 |
| `ORIONXCORE_FILESYSTEM_ALLOW_WRITE` | `true` | 允许写入操作 |
| `ORIONXCORE_FILESYSTEM_ALLOW_DELETE` | `false` | 允许删除操作 |
| `ORIONXCORE_FILESYSTEM_MAX_READ_BYTES` | 1048576 | 最大读取字节 (1 MiB) |
| `ORIONXCORE_FILESYSTEM_MAX_WRITE_BYTES` | 1048576 | 最大写入字节 (1 MiB) |
| `ORIONXCORE_FILESYSTEM_MAX_LIST_ENTRIES` | 500 | 最大列表条目 |

---

## 5. 健康检查与监控

### 5.1 健康检查端点

```bash
curl http://localhost:8080/health
```

响应:
```json
{
  "name": "OrionXCore",
  "status": "ok",
  "terminal_enabled": true,
  "database_enabled": false
}
```

### 5.2 工具发现端点

```bash
curl http://localhost:8080/v1/tools
```

### 5.3 日志配置

建议在生产环境配置日志:

```bash
# 启动时设置日志级别
export ORIONXCORE_LOG_LEVEL=INFO
uvicorn orionxcore.main:app --log-level info
```

---

## 6. 安全建议

1. **API 密钥保护**: 不要在代码中硬编码 API 密钥，使用环境变量
2. **HTTPS**: 生产环境必须使用 HTTPS
3. **网络隔离**: 不要直接暴露服务端口，使用反向代理
4. **权限控制**: 
   - `ALLOW_RISKY_COMMANDS=false` (默认)
   - `FILESYSTEM_ALLOW_DELETE=false` (默认)
5. **工作目录限制**: 设置合理的 `TERMINAL_WORKDIR` 和 `FILESYSTEM_WORKDIR`
6. **速率限制**: 建议在反向代理层配置速率限制

---

## 7. 故障排查

### 7.1 服务无法启动

```bash
# 检查配置
cat .env

# 检查依赖
pip list

# 检查端口占用
lsof -i :8080
```

### 7.2 CLI 连接失败

```bash
# 检查服务状态
curl http://localhost:8080/health

# 检查环境变量 (可能有代理干扰)
env | grep -i proxy
```

### 7.3 数据库连接失败

```bash
# 测试 ClickHouse 连接
curl http://clickhouse-host:8123/?query=SELECT%201

# 检查 URL 格式
# 正确格式: clickhousedb://user:pass@host:8123/database
```

---

## 8. 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|----------|
| v0.2.0 | 2026-05-28 | 文件系统工具、CLI readline 改进 |
| v0.1.0 | 2026-05-20 | 初始版本，Agent/数据库/终端工具 |