"""
阿里云 OSS 客户端封装

作用：将生成的研究报告上传到阿里云 OSS，并提供获取下载链接的能力。

注意：
    oss2 是同步 SDK，所有上传/下载操作通过 asyncio.to_thread() 包装，
    避免阻塞 FastAPI 的异步事件循环。

Bucket 权限建议：
    - 若希望用户直接通过外链下载（最简单），可将 Bucket 设为公共读，
      或只对 reports/ 前缀设置公共读策略。
    - 若_bucket 为私有，本模块会自动生成带签名的临时 URL（默认7天有效）。
"""

import asyncio
from typing import Any

import oss2

from app.config import settings


class OSSClient:
    """阿里云 OSS 客户端封装。"""

    def __init__(self):
        """
        初始化 OSS 客户端。

        如果 OSS 配置不完整，后续调用上传方法时会抛出 RuntimeError。
        """
        self._bucket: oss2.Bucket | None = None
        self._enabled = bool(
            settings.oss_bucket_name
            and settings.oss_endpoint
            and settings.oss_access_key_id
            and settings.oss_access_key_secret
        )

        if self._enabled:
            auth = oss2.Auth(
                settings.oss_access_key_id,
                settings.oss_access_key_secret,
            )
            self._bucket = oss2.Bucket(
                auth,
                settings.oss_endpoint,
                settings.oss_bucket_name,
            )

    @property
    def enabled(self) -> bool:
        """OSS 是否已配置并可用。"""
        return self._enabled

    def _object_key(self, task_id: str) -> str:
        """生成 OSS 对象 Key（路径）。"""
        prefix = settings.oss_report_prefix.strip("/")
        return f"{prefix}/{task_id}.md"

    def _upload_sync(self, task_id: str, content: str) -> str:
        """
        同步上传报告到 OSS（内部方法，应由异步方法包装调用）。

        返回：
            可下载的 URL（公共读 URL 或签名 URL）
        """
        if self._bucket is None:
            raise RuntimeError("OSS 未配置，无法上传。请检查 .env 中的 OSS 相关配置。")

        key = self._object_key(task_id)
        # 上传字符串内容，Content-Type 设为 text/markdown
        self._bucket.put_object(key, content.encode("utf-8"), headers={"Content-Type": "text/markdown; charset=utf-8"})

        # 尝试获取公共访问 URL；若 bucket 为私有，则返回签名 URL（7天有效）
        url = self._bucket._make_url(self._bucket.bucket_name, key)
        # 简单判断：如果能获取到不带签名的公共 URL 就返回，否则返回签名 URL
        try:
            # 生成一个带签名、7天有效的临时 URL
            signed_url = self._bucket.sign_url("GET", key, 7 * 24 * 3600)
            return signed_url
        except Exception:
            # 兜底：返回公共 URL（如果 bucket 是公共读）
            return url

    def _download_sync(self, task_id: str) -> str:
        """
        同步从 OSS 下载报告内容（内部方法）。

        返回：
            报告文本（Markdown）
        """
        if self._bucket is None:
            raise RuntimeError("OSS 未配置，无法下载。")

        key = self._object_key(task_id)
        result = self._bucket.get_object(key)
        return result.read().decode("utf-8")

    # ------------------------------------------------------------------
    # 对外异步接口
    # ------------------------------------------------------------------

    async def upload_report(self, task_id: str, content: str) -> str:
        """
        异步上传报告到 OSS。

        参数：
            task_id: 任务 ID，作为文件名
            content: Markdown 报告全文

        返回：
            可下载的 URL 字符串
        """
        return await asyncio.to_thread(self._upload_sync, task_id, content)

    async def download_report(self, task_id: str) -> str:
        """
        异步从 OSS 下载报告内容。

        参数：
            task_id: 任务 ID

        返回：
            报告文本（Markdown）
        """
        return await asyncio.to_thread(self._download_sync, task_id)

    def get_public_url(self, task_id: str) -> str:
        """
        获取报告的公共访问 URL（同步方法，仅构造 URL，不请求 OSS）。

        注意：
            如果 bucket 是私有的，这个 URL 无法直接访问，
            应使用 upload_report 返回的签名 URL。
        """
        if self._bucket is None:
            raise RuntimeError("OSS 未配置。")
        key = self._object_key(task_id)
        endpoint = self._bucket.endpoint
        # 确保 endpoint 带协议头
        if not endpoint.startswith("http"):
            endpoint = "https://" + endpoint
        return f"{endpoint}/{key}"


# 全局单例
oss_client = OSSClient()
