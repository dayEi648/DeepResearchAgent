"""
研究任务路由

接口：
    POST   /research              提交研究任务
    GET    /research/{task_id}    查询任务状态与结果
    GET    /research/{task_id}/stream  SSE 流式推送进度
"""

import asyncio
import json
import uuid
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.status import (
    HTTP_202_ACCEPTED,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
)

from app.agents.graph import build_graph
from app.agents.nodes import TASK_QUEUES
from app.agents.state import ResearchState
from app.config import settings
from app.tools.rate_limiter import RateLimiter
from app.tools.redis_checkpoint import RedisCheckpointSaver

router = APIRouter(prefix="/research", tags=["research"])

# ------------------------------------------------------------------
# 全局：Redis 客户端、限流器、Checkpoint Saver
# ------------------------------------------------------------------

_redis_client: redis.Redis | None = None
_rate_limiter: RateLimiter | None = None
_checkpoint_saver: RedisCheckpointSaver | None = None


async def _get_redis() -> redis.Redis:
    """获取或创建 Redis 连接（懒加载）。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


async def _get_rate_limiter() -> RateLimiter:
    """获取或创建限流器。"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(await _get_redis())
    return _rate_limiter


async def _get_checkpoint_saver() -> RedisCheckpointSaver:
    """获取或创建 Checkpoint Saver。"""
    global _checkpoint_saver
    if _checkpoint_saver is None:
        _checkpoint_saver = RedisCheckpointSaver(await _get_redis())
    return _checkpoint_saver


# ------------------------------------------------------------------
# 请求/响应模型
# ------------------------------------------------------------------

class ResearchRequest(BaseModel):
    """提交研究任务的请求体。"""
    topic: str = Field(..., min_length=1, max_length=500, description="研究主题")


class ResearchResponse(BaseModel):
    """提交成功后的响应。"""
    task_id: str
    status: str
    stream_url: str


# ------------------------------------------------------------------
# 接口 1：提交研究任务
# ------------------------------------------------------------------

@router.post("", status_code=HTTP_202_ACCEPTED)
async def create_research(request: ResearchRequest) -> dict[str, Any]:
    """
    提交一个新的研究任务。

    流程：
        1. 限流检查
        2. 生成 task_id
        3. 创建 SSE 队列
        4. 后台启动 LangGraph 执行
    """
    # 1. 限流检查
    limiter = await _get_rate_limiter()
    if not await limiter.acquire():
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": 4291,
                "message": "并发研究任务数已达上限",
                "detail": {"max_concurrent": settings.max_concurrent_research},
            },
        )

    # 2. 生成 task_id
    task_id = str(uuid.uuid4())
    topic = request.topic.strip()

    # 3. 创建 SSE 事件队列（用于推送进度）
    TASK_QUEUES[task_id] = asyncio.Queue()

    # 4. 后台启动 LangGraph（不阻塞 HTTP 响应）
    asyncio.create_task(_run_research(task_id, topic))

    return {
        "code": 2000,
        "data": {
            "task_id": task_id,
            "status": "pending",
            "stream_url": f"/research/{task_id}/stream",
        },
    }


async def _run_research(task_id: str, topic: str) -> None:
    """
    后台执行 LangGraph 研究流程。

    这是真正的业务逻辑，在 asyncio.create_task 中运行，不占用 HTTP 连接。
    """
    limiter = await _get_rate_limiter()

    try:
        # 构建图（注入 Checkpoint Saver）
        saver = await _get_checkpoint_saver()
        graph = build_graph(checkpointer=saver)

        # 初始状态
        initial_state: ResearchState = {
            "task_id": task_id,
            "topic": topic,
            "iteration_count": 0,
            "current_node": "pending",
        }

        # 运行配置（thread_id = task_id，实现任务级隔离）
        config = {"configurable": {"thread_id": task_id}}

        # 执行图（ainvoke 是异步版本）
        await graph.ainvoke(initial_state, config=config)

        print(f"[Task] {task_id} 执行完成")

        # 推送 END 事件，通知前端任务已结束
        queue = TASK_QUEUES.get(task_id)
        if queue:
            await queue.put({
                "event_type": "node_complete",
                "task_id": task_id,
                "node": "END",
                "output": {"status": "completed"},
            })

    except Exception as e:
        print(f"[Task] {task_id} 执行失败: {e}")
        # 推送错误事件到 SSE
        queue = TASK_QUEUES.get(task_id)
        if queue:
            await queue.put({
                "event_type": "error",
                "task_id": task_id,
                "node": "unknown",
                "error_code": 5001,
                "message": str(e),
            })

    finally:
        # 释放限流槽位
        await limiter.release()


# ------------------------------------------------------------------
# 接口 2：查询任务状态
# ------------------------------------------------------------------

@router.get("/{task_id}")
async def get_research(task_id: str) -> dict[str, Any]:
    """
    查询指定任务的当前状态和结果。

    支持断点续传后查询：服务重启后，从 Redis Checkpoint 读取最新状态。
    """
    # 尝试从 Redis Checkpoint 读取状态
    saver = await _get_checkpoint_saver()
    config = {"configurable": {"thread_id": task_id}}

    try:
        checkpoint_tuple = await saver.aget_tuple(config)
    except Exception:
        checkpoint_tuple = None

    if checkpoint_tuple is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail={"code": 4041, "message": "任务不存在"},
        )

    # 从 Checkpoint 中提取状态字段
    checkpoint = checkpoint_tuple.checkpoint
    channel_values = checkpoint.get("channel_values", {})

    status = channel_values.get("current_node", "unknown")
    iteration_count = channel_values.get("iteration_count", 0)
    report = channel_values.get("report")
    report_path = channel_values.get("report_path")

    # 映射节点到进度百分比
    progress_map = {
        "pending": 0,
        "planner": 20,
        "researcher": 40,
        "analyzer": 60,
        "writer": 80,
        "reviewer": 90,
        "save_report": 100,
        "END": 100,
    }
    progress = progress_map.get(status, 0)

    # 判断最终状态
    task_status = "running"
    if status in ("save_report", "END"):
        task_status = "completed"
    elif status == "failed":
        task_status = "failed"

    response: dict[str, Any] = {
        "task_id": task_id,
        "topic": channel_values.get("topic", ""),
        "status": task_status,
        "current_node": status,
        "progress": progress,
        "iteration_count": iteration_count,
        "report": report,
        "report_path": report_path,
        "created_at": None,
        "updated_at": None,
    }

    # 如果已完成，包含完整报告
    if task_status == "completed":
        response["report"] = report
        response["report_path"] = report_path

    return {"code": 2000, "data": response}


# ------------------------------------------------------------------
# 接口 3：SSE 流式推送
# ------------------------------------------------------------------

@router.get("/{task_id}/stream")
async def stream_research(task_id: str) -> StreamingResponse:
    """
    SSE 流式推送任务执行进度。

    连接建立后，服务端通过 EventSource 格式逐条推送节点事件。
    客户端断线后重连，会从当前最新状态继续推送（不重复已完成的节点）。
    """
    # 如果队列不存在（可能是服务重启），重新创建
    if task_id not in TASK_QUEUES:
        TASK_QUEUES[task_id] = asyncio.Queue()

        # 尝试从 Checkpoint 恢复当前状态，发送一个 sync 事件
        try:
            saver = await _get_checkpoint_saver()
            config = {"configurable": {"thread_id": task_id}}
            cp = await saver.aget_tuple(config)
            if cp:
                node = cp.checkpoint.get("channel_values", {}).get("current_node", "unknown")
                await TASK_QUEUES[task_id].put({
                    "event_type": "node_start",
                    "task_id": task_id,
                    "node": node,
                    "note": "sync_from_checkpoint",
                })
        except Exception:
            pass

    async def event_generator():
        """异步生成器：从队列中取出事件，格式化为 SSE。"""
        queue = TASK_QUEUES[task_id]

        while True:
            try:
                # 等待事件，最多 60 秒（超过则发送心跳或检查任务是否已结束）
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                # 发送心跳保活
                yield f"data: {json.dumps({'event_type': 'heartbeat', 'task_id': task_id})}\n\n"
                continue

            # 格式化为 SSE 格式
            yield f"data: {json.dumps(event)}\n\n"

            # 结束条件
            if event.get("node") == "END" or event.get("event_type") == "error":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲（如有）
        },
    )