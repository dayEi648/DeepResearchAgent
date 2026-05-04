"""
自定义 Redis Checkpoint Saver

作用：将 LangGraph 的执行状态（Checkpoint）持久化到 Redis，实现断点续传。
核心方法：
    - put:      保存状态快照
    - get_tuple: 读取最新快照
    - list:     列出历史快照（调试用）

Key 格式：langgraph:checkpoint:{thread_id}
"""

import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as redis
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class RedisCheckpointSaver(BaseCheckpointSaver):
    """基于 Redis 的 Checkpoint 持久化实现。"""

    def __init__(self, redis_client: redis.Redis, ttl: int = 86400 * 7):
        """
        参数：
            redis_client: 已连接的 Redis 异步客户端
            ttl: Checkpoint 在 Redis 中的存活时间（默认 7 天）
        """
        # BaseCheckpointSaver 需要一个序列化器实例
        super().__init__(serde=JsonPlusSerializer())
        self._redis = redis_client
        self._ttl = ttl
        self._prefix = "langgraph:checkpoint"

    def _key(self, thread_id: str) -> str:
        """生成 Redis Key。"""
        return f"{self._prefix}:{thread_id}"

    def _encode_typed(self, obj: Any) -> dict[str, str]:
        """
        使用 serde 序列化对象，返回可 JSON 存储的字典。

        因为 dumps_typed 返回的 bytes 是 msgpack 格式，不能直接存入 JSON，
        所以用 base64 编码转成 ASCII 字符串。
        """
        type_name, data_bytes = self.serde.dumps_typed(obj)
        return {
            "type": type_name,
            "data": base64.b64encode(data_bytes).decode("ascii"),
        }

    def _decode_typed(self, encoded: dict[str, str]) -> Any:
        """从 JSON 字典还原 serde 序列化的对象。"""
        type_name = encoded["type"]
        data_bytes = base64.b64decode(encoded["data"])
        return self.serde.loads_typed((type_name, data_bytes))

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> RunnableConfig:
        """
        保存 Checkpoint 到 Redis。

        参数：
            config: 包含 thread_id 的运行配置
            checkpoint: LangGraph 自动生成的状态快照
            metadata: 元数据（如开始时间、节点名等）
            new_versions: 各通道的版本号

        返回：
            更新后的 config（包含新的 checkpoint_id）
        """
        thread_id = config["configurable"]["thread_id"]

        # 序列化 checkpoint、metadata、new_versions
        payload = {
            "checkpoint": self._encode_typed(checkpoint),
            "metadata": self._encode_typed(metadata),
            "new_versions": self._encode_typed(new_versions),
        }

        # 写入 Redis（payload 是纯 JSON，可直接用 json.dumps）
        await self._redis.set(
            self._key(thread_id),
            json.dumps(payload),
            ex=self._ttl,
        )

        return config

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """
        从 Redis 读取最新的 Checkpoint。

        参数：
            config: 包含 thread_id 的运行配置

        返回：
            CheckpointTuple（包含状态快照）或 None（未找到）
        """
        thread_id = config["configurable"]["thread_id"]
        raw = await self._redis.get(self._key(thread_id))
        if raw is None:
            return None

        # 反序列化
        payload = json.loads(raw)
        checkpoint = self._decode_typed(payload["checkpoint"])
        metadata = self._decode_typed(payload["metadata"])

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None,  # 简化：不保存父配置
            pending_writes=[],   # 简化：不保存待写入
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """
        列出 Checkpoint（简化实现：只返回最新的一个）。

        实际项目中如需查看历史版本，可改用 Redis List 存储多条记录。
        """
        if config is None:
            return

        tuple_data = await self.aget_tuple(config)
        if tuple_data is not None:
            yield tuple_data

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        保存待处理的写入（简化：暂不实现）。

        LangGraph 在并行节点执行时用到此方法。对于本项目，
        并行 Researcher 的结果合并通过 State 的 dict 更新完成，
        不依赖 pending writes 机制。
        """
        pass
