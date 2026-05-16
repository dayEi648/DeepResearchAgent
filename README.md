# Deep Research Agent — 智能深度研究助手

一个基于 **LangGraph** 多 Agent 协作编排的自动化深度研究系统。用户只需输入一个研究主题，系统即可自动完成「任务拆解 → 并行搜索 → 分析整合 → 报告撰写 → 质量审核」的全流程，最终输出结构化的 Markdown 研究报告。

---

## 核心功能

### 自动化研究流水线

系统内置 5 个协作 Agent，按状态机顺序执行：

| 节点 | 职责 | 关键技术 |
|------|------|---------|
| **Planner** | 将研究主题拆解为 3~5 个并行的子研究任务 | Prompt Engineering、JSON 结构化输出 |
| **Researcher** | 对每个子任务并行调用 MCP Search 收集资料 | MCP 协议、异步并发 (`asyncio.gather`) |
| **Analyzer** | 结合 RAG 检索的方法论模板，分析整合所有搜索结果 | ChromaDB 向量检索、上下文增强 |
| **Writer** | 基于分析结论撰写 Markdown 格式结构化报告 | 长文本生成、格式控制 |
| **Reviewer** | 从完整性、逻辑性、格式规范性三方面审核报告 | Self-reflection Prompt、条件边循环 |

- **审核回退机制**：Reviewer 不通过时，自动回退到 Writer 重写（最多循环 2 次，防止死循环）。
- **SSE 实时推送**：前端通过 EventSource 实时接收各 Agent 节点的执行状态与进度。

### 断点续传

长任务执行过程中若服务重启，可从 **Redis Checkpoint** 恢复状态，继续执行，无需重新开始。

### 搜索缓存与并发限流

- **Redis 搜索缓存**：相同查询在 1 小时内直接走缓存，降低 API 成本与延迟。
- **Sliding Window 限流**：基于 Redis 限制同时执行的研究任务数（默认 5 个），防止资源耗尽。

---

## 技术栈

### 后端

| 技术 | 版本 | 作用 |
|------|------|------|
| Python | 3.11+ | 主开发语言 |
| FastAPI | ≥0.115 | 异步 Web 框架，暴露 RESTful API 与 SSE 流式端点 |
| Uvicorn | ≥0.32 | ASGI 服务器 |
| LangGraph | ≥0.3 | Agent 工作流编排核心，定义状态机、节点、边与持久化策略 |
| LangChain | ≥0.3 | LLM 调用抽象、RAG 检索链 |
| MCP | ≥1.6 | 标准化协议，安全调用外部搜索工具 |
| ChromaDB | ≥0.6 | 本地向量数据库，存储"研究方法论知识库" |
| Redis | 5.x | Checkpoint 持久化、搜索结果缓存、并发限流 |
| Pydantic Settings | ≥2.7 | 环境变量与配置管理 |
| aiofiles | ≥24.1 | 异步文件写入，本地保存报告 |
| oss2 | ≥2.18 | 阿里云 OSS 上传，生成云端下载链接 |

### 前端

| 技术 | 版本 | 作用 |
|------|------|------|
| Vue | 3.5+ | 响应式单页应用框架 |
| Vue Router | 5.x | 前端路由 |
| Vite | 8.x | 构建工具 |
| Pinia | 3.x | 全局状态管理 |
| Axios | 1.16+ | HTTP 客户端 |
| marked | 18.x | Markdown 渲染引擎 |
| highlight.js | 11.x | 代码语法高亮 |

### 外部服务

- **LLM**：DeepSeek / OpenAI / 智谱（兼容 OpenAI 格式）
- **搜索**：阿里云 IQS Search（通过 MCP SSE 远程接入）
- **Embedding**：阿里云百炼 `text-embedding-v4`
- **云存储**：阿里云 OSS（可选，未配置时仅本地保存）

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         用户层                               │
│         (Vue 3 SPA / curl / Postman)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ POST /research
                       │ GET  /research/{task_id}/stream (SSE)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI 服务层                          │
│  • 异步接收请求，生成 task_id                                │
│  • SSE 流式推送 Agent 节点执行进度                           │
│  • 查询 Redis Checkpoint 返回当前状态/结果                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     Redis 基础设施层                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────┐  │
│  │ Checkpoint Store│ │  Search Cache   │ │ Rate Limiter │  │
│  │ (LangGraph状态) │ │ (URL→Content)   │ │ (Sliding Win)│  │
│  └─────────────────┘ └─────────────────┘ └──────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph 编排层                          │
│                                                             │
│   ┌──────────┐     ┌──────────────────┐                    │
│   │ Planner  │────▶│ Researcher Agent │──┐                 │
│   │  Agent   │     │   (并行 × N)      │  │                 │
│   └──────────┘     └──────────────────┘  │                 │
│                                          ▼                 │
│   ┌──────────┐     ┌──────────────────┐  │                 │
│   │ Reviewer │◀────│   Writer Agent   │◀─┘                 │
│   │  Agent   │     └──────────────────┘                     │
│   └────┬─────┘              ▲                               │
│        │                   │                               │
│        └──────不通过────────┘ (条件边，最多循环2次)          │
│              通过                                           │
│                │                                            │
│                ▼                                            │
│        ┌──────────────────┐                               │
│        │ 本地写入 + OSS 上传 │  保存报告.md + 云端外链       │
│        │ (aiofiles/oss2)  │                               │
│        └──────────────────┘                               │
│                                                             │
│   注：Analyzer Agent 在 Writer 之前，结合 RAG 做分析整合    │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      外部依赖层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ LLM API      │  │ MCP Search   │  │ 本地写入 / OSS   │   │
│  │ (DeepSeek等) │  │ (IQS Search) │  │ (aiofiles)      │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
│  ┌──────────────┐                                           │
│  │ ChromaDB     │  研究方法论向量知识库                      │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

### 前端页面

| 页面 | 路径 | 说明 |
|------|------|------|
| 主题提交页 | `/` | 纯黑首屏，输入研究主题并提交 |
| 进度监控页 | `/task/:task_id` | 浅灰背景，横向步骤条 + 实时日志 + 进度条 |
| 报告展示页 | `/report/:task_id` | 纯白背景，Apple 风格 Markdown 排版 + 目录导航 |

---

## 项目结构

```
DeepSearch/
├── app/                          # 后端 FastAPI 应用
│   ├── agents/                   # LangGraph Agent 节点与状态机
│   │   ├── state.py              # ResearchState 状态定义
│   │   ├── nodes.py              # 5 个 Agent 节点实现
│   │   └── graph.py              # LangGraph 状态机构建 + 条件边
│   ├── routers/                  # FastAPI 路由（API 接口）
│   │   └── research.py           # /research 路由（提交、查询、SSE）
│   ├── tools/                    # 工具封装
│   │   ├── mcp_client.py         # MCP 客户端（SSE 连接 IQS Search）
│   │   ├── search_cache.py       # Redis 搜索缓存
│   │   ├── rate_limiter.py       # Redis 滑动窗口限流器
│   │   ├── redis_checkpoint.py   # 自定义 Redis Checkpoint Saver
│   │   └── oss_client.py         # 阿里云 OSS 客户端封装
│   ├── rag/                      # RAG 知识库
│   │   └── vectorstore.py        # ChromaDB 向量库初始化与检索
│   ├── config.py                 # 配置管理（Pydantic Settings）
│   └── main.py                   # FastAPI 入口（CORS、健康检查、路由注册）
├── frontend/
│   └── DeepResearchAgent/        # Vue 3 + Vite SPA
│       ├── src/
│       │   ├── views/            # 页面视图（Submit / Progress / Report）
│       │   ├── components/       # 可复用组件（导航、步骤条、日志面板等）
│       │   ├── stores/           # Pinia 全局状态管理
│       │   ├── api/              # Axios API 封装 + SSE 连接
│       │   ├── utils/            # 工具函数（Markdown 渲染、目录提取）
│       │   └── styles/           # 全局样式（CSS Variables、动画）
│       ├── index.html
│       ├── package.json
│       └── vite.config.js
├── knowledge_base/               # 研究方法论原始文档（Markdown）
├── reports/                      # 生成的报告本地输出目录
├── deploy/                       # 部署配置文件（Nginx、systemd、手册）
├── chroma_db/                    # ChromaDB 向量库本地数据
├── .env                          # 环境变量（API Key、Redis、OSS 等）
├── .env.example                  # 环境变量模板
├── requirements.txt              # Python 依赖
├── mcp_settings.json             # MCP Server 配置
└── README.md                     # 本文件
```

---

## 快速开始

### 环境准备

- Python 3.11+
- Node.js 18+（前端构建需要）
- Redis 7.0+

### 1. 安装后端依赖

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .\.venv\Scripts\Activate.ps1  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```ini
# LLM API（至少填一个，默认优先 DeepSeek）
DEEPSEEK_API_KEY=sk-xxx

# 阿里云百炼（Embedding 向量模型，免费额度）
DASHSCOPE_API_KEY=sk-xxx

# 阿里云 IQS Search
IQSSEARCH_API_KEY=xxx

# Redis
REDIS_URL=redis://localhost:6379/0

# 阿里云 OSS（可选，未配置时仅本地保存报告）
OSS_BUCKET_NAME=your-bucket
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_ACCESS_KEY_ID=xxx
OSS_ACCESS_KEY_SECRET=xxx
```

### 3. 启动 Redis

```bash
redis-server
```

### 4. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 启动前端（可选）

```bash
cd frontend/DeepResearchAgent
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，后端在 `http://localhost:8000`。

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查（Redis、ChromaDB 就绪状态） |
| `POST` | `/research` | 提交研究任务 |
| `GET` | `/research/{task_id}` | 查询任务状态与结果 |
| `GET` | `/research/{task_id}/stream` | SSE 流式获取执行进度 |

### 提交研究任务

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic":"2026年AI Agent开发框架对比调研"}'
```

响应：

```json
{
  "code": 2000,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending",
    "stream_url": "/research/550e8400-e29b-41d4-a716-446655440000/stream"
  }
}
```

### SSE 流式监听进度

```bash
curl -N \
  -H "Accept: text/event-stream" \
  http://localhost:8000/research/550e8400-e29b-41d4-a716-446655440000/stream
```

---

## 核心特性

- **多 Agent 协作状态机**：5 个 Agent 按 LangGraph 状态机顺序执行，支持条件边循环回退。
- **MCP 协议集成**：通过 SSE 远程接入阿里云 IQS Search，实现 LLM 对外部信息源的标准化、安全化调用。
- **RAG 知识增强**：基于研究方法向量库（ChromaDB）引导 LLM 输出结构化、专业化的调研报告。
- **Redis 三重角色**：Checkpoint 持久化（断点续传）、搜索缓存、并发限流。
- **双保险报告存储**：本地异步写入 + 阿里云 OSS 云端上传，未配置 OSS 时自动降级为本地存储。
- **SSE 实时推送**：前端实时观测各 Agent 节点执行状态，断线后自动重连并从最新状态续推。

---

##  RAG 知识库

系统内置「研究方法论知识库」，用于规范 LLM 的输出质量：

- 优质技术调研报告模板
- 竞品分析框架（SWOT 等）
- 行业白皮书目录结构示例

文档存放于 `knowledge_base/` 目录，启动时自动切分、向量化并存入 ChromaDB，供 Analyzer 节点检索引用。
