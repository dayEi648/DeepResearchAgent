# Deep Research Agent — 部署手册

> 目标：将项目部署到阿里云 ECS（2核2G），实现线上访问。

---

## 一、服务器环境准备

### 1.1 连接 ECS

```bash
# 用阿里云控制台获取的密码或密钥登录
ssh root@<你的ECS公网IP>
```

### 1.2 安装基础依赖

```bash
# 更新软件源
apt update && apt upgrade -y

# 安装必要工具
apt install -y python3 python3-venv python3-pip git nginx redis-server

# 安装 Node.js 18+（用于构建前端）
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# 验证版本
python3 --version   # 应 >= 3.11
node -v             # 应 >= 18
nginx -v
redis-cli ping      # 应返回 PONG
```

---

## 二、部署项目代码

### 2.1 创建目录并上传代码

```bash
mkdir -p /var/www/deepresearch
cd /var/www/deepresearch
```

**方式 A：Git 克隆（推荐，如果你已推送到 GitHub）**
```bash
git clone <你的仓库地址> .
```

**方式 B：本地压缩上传（Windows 用户）**
```powershell
# 在 Windows PowerShell 中执行
# 先确保 node_modules 和 .venv 不包含在压缩包里
Compress-Archive -Path "app", "frontend", "knowledge_base", "reports", "requirements.txt", ".env.example", "mcp_settings.json" -DestinationPath "deepresearch.zip"

# 用 scp 上传到服务器
scp deepresearch.zip root@<ECS_IP>:/var/www/deepresearch/
```

```bash
# 在服务器上解压
apt install -y unzip
cd /var/www/deepresearch
unzip deepresearch.zip
```

### 2.2 配置环境变量

```bash
cd /var/www/deepresearch
cp .env.example .env
nano .env
```

填写以下关键配置：

```ini
# LLM API（至少填一个）
DEEPSEEK_API_KEY=sk-xxx

# 阿里云百炼（Embedding）
DASHSCOPE_API_KEY=sk-xxx

# 阿里云 IQS Search
IQSSEARCH_API_KEY=xxx

# Redis（本机）
REDIS_URL=redis://localhost:6379/0

# 阿里云 OSS（必填，否则报告无法上传）
OSS_BUCKET_NAME=your-bucket-name
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
```

> ⚠️ **安全提醒**：`.env` 文件绝不要提交到 Git！ECS 上手动放置即可。

### 2.3 创建 Python 虚拟环境并安装依赖

```bash
cd /var/www/deepresearch
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 初始化 ChromaDB 向量库

```bash
cd /var/www/deepresearch
source .venv/bin/activate
python -c "from app.rag.vectorstore import init_vectorstore; init_vectorstore()"
```

> 第一次会加载 knowledge_base/ 文档并切分向量化，稍等片刻。

---

## 三、构建前端

```bash
cd /var/www/deepresearch/frontend/DeepResearchAgent
npm install
npm run build
```

构建产物在 `frontend/DeepResearchAgent/dist/` 目录下，Nginx 会从这个目录提供静态文件。

---

## 四、配置 systemd 服务（后端保活）

### 4.1 复制服务文件

```bash
cp /var/www/deepresearch/deploy/deepresearch.service /etc/systemd/system/
```

### 4.2 创建运行用户（如不存在）

```bash
useradd -r -s /bin/false www-data 2>/dev/null || true
chown -R www-data:www-data /var/www/deepresearch
```

### 4.3 启动并启用服务

```bash
systemctl daemon-reload
systemctl enable deepresearch
systemctl start deepresearch
systemctl status deepresearch
```

查看日志：
```bash
journalctl -u deepresearch -f
```

---

## 五、配置 Nginx

### 5.1 复制配置文件

```bash
cp /var/www/deepresearch/deploy/nginx.conf /etc/nginx/sites-available/deepresearch
ln -sf /etc/nginx/sites-available/deepresearch /etc/nginx/sites-enabled/

# 删除默认配置（避免冲突）
rm -f /etc/nginx/sites-enabled/default
```

### 5.2 检查配置并重启

```bash
nginx -t
systemctl restart nginx
systemctl enable nginx
```

---

## 六、开放安全组端口

在阿里云控制台 → ECS → 安全组，添加规则：

| 协议 | 端口范围 | 授权对象 | 说明 |
|------|---------|---------|------|
| TCP | 80 | 0.0.0.0/0 | HTTP |
| TCP | 443 | 0.0.0.0/0 | HTTPS（如需） |
| TCP | 22 | 你的IP | SSH（限制来源更安全） |

> 注意：不要开放 8000 端口！后端只监听 127.0.0.1，由 Nginx 反向代理访问。

---

## 七、验证部署

### 7.1 健康检查

```bash
curl http://<ECS公网IP>/health
```

预期返回：
```json
{"code":2000,"data":{"status":"healthy","redis":"connected","chromadb":"connected","mcp_servers":["iqs-search"]}}
```

### 7.2 完整流程测试

1. 浏览器访问 `http://<ECS公网IP>/`
2. 输入研究主题，点击提交
3. 观察进度页，等待任务完成
4. 进入报告页，点击"下载 Markdown"
5. 确认能正常下载完整文件

---

## 八、后续维护

### 更新代码

```bash
cd /var/www/deepresearch
git pull  # 或重新上传代码
source .venv/bin/activate
pip install -r requirements.txt  # 如有新依赖
cd frontend/DeepResearchAgent && npm run build
systemctl restart deepresearch
```

### 查看日志

```bash
# 后端日志
journalctl -u deepresearch -n 100

# Nginx 访问日志
tail -f /var/log/nginx/deepresearch.access.log

# Nginx 错误日志
tail -f /var/log/nginx/deepresearch.error.log
```

### 重启服务

```bash
systemctl restart deepresearch
systemctl restart nginx
```

---

## 九、可选：配置 HTTPS（强烈推荐）

使用 Let's Encrypt 免费证书：

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

按提示操作即可自动配置 HTTPS 并续期。

---

## 十、故障排查

| 现象 | 可能原因 | 解决 |
|------|---------|------|
| 502 Bad Gateway | 后端没启动 | `systemctl status deepresearch` |
| 刷新页面 404 | Nginx 没配 SPA 回退 | 检查 `try_files` 配置 |
| SSE 不推送 | Nginx 缓冲未关闭 | 检查 `proxy_buffering off` |
| 报告下载 0KB | OSS 未配置或上传失败 | 检查 `.env` 和后端日志 |
| CORS 错误 | 前端 baseURL 不对 | 确认生产环境用相对路径 |
