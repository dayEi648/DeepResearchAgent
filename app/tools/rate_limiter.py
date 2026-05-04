"""
Redis 并发限流器

作用：基于 Sliding Window 算法，限制全局同时执行的研究任务数量，防止 API 配额耗尽。
Key 格式：rate_limit:research:{当前分钟时间戳}
"""

import time

import redis.asyncio as redis

from app.config import settings


class RateLimiter:
    """基于 Redis 的滑动窗口限流器。"""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client
        self._max_concurrent = settings.max_concurrent_research
        self._window = 60  # 滑动窗口宽度：60 秒
        self._prefix = "rate_limit:research"

    def _key(self) -> str:
        """按当前分钟生成 Key，实现滑动窗口。"""
        # 用当前时间戳（秒级）整除 60，得到当前分钟的标识
        window_id = int(time.time()) // self._window
        return f"{self._prefix}:{window_id}"

    async def acquire(self) -> bool:
        """
        尝试获取一个执行槽位。

        返回：
            True: 获取成功，可以执行新任务
            False: 当前并发已满，请稍后重试
        """
        key = self._key()
        current = await self._redis.get(key)
        current_val = int(current) if current else 0

        if current_val >= self._max_concurrent:
            return False

        # 原子性自增（INCR），防止并发竞争
        new_val = await self._redis.incr(key)
        # 如果是第一次设置（new_val == 1），同时设置过期时间
        if new_val == 1:
            await self._redis.expire(key, self._window)

        # 自增后可能超出限制（极端并发场景），需要回退
        if new_val > self._max_concurrent:
            await self._redis.decr(key)
            return False

        return True

    async def release(self) -> None:
        """
        释放一个执行槽位（任务完成或失败时调用）。

        注意：如果 Key 已过期（任务执行超过 60 秒），这里会忽略错误，不影响逻辑。
        """
        key = self._key()
        try:
            current = await self._redis.get(key)
            if current and int(current) > 0:
                await self._redis.decr(key)
        except Exception:
            # Key 已过期或网络抖动，安全忽略
            pass