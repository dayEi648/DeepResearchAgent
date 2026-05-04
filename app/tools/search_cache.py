"""
Redis 搜索缓存模块

作用：缓存 MCP Search 的搜索结果，相同查询在 1 小时内直接返回缓存，降低 API 成本。
Key 格式：search:cache:{md5(query)}
TTL：3600 秒
"""
import hashlib
import json
from typing import Any

import redis.asyncio as redis

from app.config import settings

class SearchCache:
    """搜索结果缓存封装"""
    def __init__(self, redis_client: redis.Redis):
        """
        参数：
            redis_client: 已连接的 Redis 异步客户端
        """
        self.redis = redis_client
        self._redis = redis_client
        self._ttl = 3600  # 缓存有效期：1 小时
        self._prefix = "search:cache"

    def _key(self, query: str) -> str:
        """根据查询内容生成 Redis Key（用 MD5 避免特殊字符）"""
        md5_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
        return f"{self._prefix}:{md5_hash}"

    async def get(self, query: str) -> list[dict[str, Any]] | None:
        """
        获取缓存的搜索结果。

        参数：
            query: 搜索查询词

        返回：
            缓存存在且未过期：返回搜索结果列表
            缓存不存在或已过期：返回 None
        """
        raw = await self._redis.get(self._key(query))
        if raw is None:
            return None
        # Redis 存的是 JSON 字符串，解析回 Python 对象
        return json.loads(raw)

    async def set(self, query: str, results: list[dict[str, Any]]) -> None:
        """
        将搜索结果写入缓存。

        参数：
            query: 搜索查询词
            results: 搜索结果列表
        """
        await self._redis.set(
            self._key(query),
            json.dumps(results, ensure_ascii=False),
            ex=self._ttl,
        )
        
    async def delete(self, query: str) -> None:
        """手动删除某条缓存（调试用）。"""
        await self._redis.delete(self._key(query))        