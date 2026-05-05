"""
FastAPI 应用入口

作用：
    1. 创建 FastAPI 实例
    2. 注册路由（/health、/research）
    3. 启动时初始化 RAG 向量库
    4. 提供静态文件服务（reports/ 目录）
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import research


# ------------------------------------------------------------------
# 生命周期事件：启动时初始化 RAG 向量库
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件处理器（替代已弃用的 @app.on_event）."""
    print("[Startup] 正在初始化 RAG 向量库...")
    from app.rag.vectorstore import init_vectorstore
    init_vectorstore()
    print("[Startup] 初始化完成，服务就绪")
    yield
    # 如需在服务关闭时清理资源，写在 yield 后面


# ------------------------------------------------------------------
# 创建 FastAPI 应用（注入 lifespan）
# ------------------------------------------------------------------

app = FastAPI(
    title="智能深度研究助手",
    description="基于 LangGraph + MCP + RAG + Redis 的多 Agent 协作研究系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：允许前端跨域访问
# 生产环境：前端和后端部署在同一域名下时，CORS 实际上不会触发。
# 但为了兼容本地开发、以及未来可能的前后端分离部署，保留通配符配置。
# 注意：allow_origins=["*"] 与 allow_credentials=True 同时使用时，
# 浏览器会有安全警告。生产环境若在同一域名下，可去掉 CORS 中间件。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# 路由注册
# ------------------------------------------------------------------

@app.get("/health")
async def health_check() -> dict:
    """
    健康检查接口。

    检查 Redis 和 ChromaDB 是否就绪。
    """
    import redis.asyncio as redis

    redis_status = "connected"
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
    except Exception:
        redis_status = "disconnected"

    chromadb_status = "connected"
    try:
        from app.rag.vectorstore import init_vectorstore
        init_vectorstore()
    except Exception:
        chromadb_status = "disconnected"

    # IQS Search MCP 是远程 SSE 服务，此处仅做配置项展示，不做实时连通性检查
    mcp_servers = ["iqs-search"]

    healthy = redis_status == "connected" and chromadb_status == "connected"
    status_code = 200 if healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "code": 2000 if healthy else 5031,
            "data": {
                "status": "healthy" if healthy else "unhealthy",
                "redis": redis_status,
                "chromadb": chromadb_status,
                "mcp_servers": mcp_servers,
            },
        },
    )


# 注册研究任务路由
app.include_router(research.router)

# 静态文件：reports/ 目录下的 .md 文件可直接下载（本地开发/兜底用）
app.mount("/reports", StaticFiles(directory=str(settings.reports_dir)), name="reports")