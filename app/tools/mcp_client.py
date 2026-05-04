"""
MCP 客户端封装

作用：通过 SSE 远程连接阿里云 IQS Search MCP Server，调用搜索工具执行搜索。

生命周期：
    通过 async with 建立/关闭 SSE 长连接。

工具说明：
    - common_search: 标准搜索工具，返回完整结构化结果（推荐）
    - web_search: 轻量版搜索工具，返回更精简的结果
    具体可用工具名请通过 list_all_tools() 确认，然后修改 search() 中的 tool_name。

注意：
    如果 SSE 连接在你的环境中不可用，可以回退到 HTTP 直接调用方式
    （参考阿里云官方 HTTP API 文档）。
"""
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession

# SSE 远程连接（mcp>=1.6.0 支持）
# 如果导入失败或 API 变化，请先执行：pip install --upgrade mcp
from mcp.client.sse import sse_client

from app.config import settings
from app.tools.search_cache import SearchCache

class MCPClient:
    """MCP 客户端，通过 SSE 连接远程 IQS Search MCP Server。"""

    def __init__(self, search_cache: SearchCache | None = None):
        """
        参数：
            search_cache: 搜索结果缓存实例（可选，传入则启用缓存）
        """
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._search_cache = search_cache

    async def __aenter__(self):
        """异步上下文管理器入口：启动所有 MCP Server。"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口：关闭所有 MCP Server 进程。"""
        await self._exit_stack.aclose()
    
    async def connect(self) -> None:
        """
        通过 SSE 远程连接 IQS Search MCP Server。

        连接参数从 mcp_settings.json 读取，支持动态配置 URL 和 Headers。
        如 SSE 连接方式在你的 mcp SDK 版本中不可用，可回退到 HTTP 直接调用
        （参考阿里云官方文档）。
        """
         # 从 mcp_settings.json 读取配置
        mcp_cfg = settings.mcp_config
        server_cfg = mcp_cfg.get("mcpServers", {}).get("iqs-search", {})

        iqs_url = server_cfg.get("url", "")
        headers = server_cfg.get("headers", {})

        if not iqs_url:
            raise RuntimeError("mcp_settings.json 中未配置 iqs-search 的 url")

        if not settings.iqssearch_api_key:
            raise RuntimeError("IQSSEARCH_API_KEY 未配置，请检查 .env 文件")

        # 建立 SSE 传输连接
        transport = await self._exit_stack.enter_async_context(
            sse_client(iqs_url, headers=headers)
        )
        read, write = transport

        # 创建 ClientSession 并初始化
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        print("[MCP] IQS Search MCP Server (SSE) 已连接")
    
    # ------------------------------------------------------------------
    # 对外接口：搜索（阿里云 IQS Search）
    # ------------------------------------------------------------------

    async def search(self, query: str) -> list[dict[str, Any]]:
        """
        调用 IQS Search MCP Server 的搜索工具执行搜索。

        参数：
            query: 搜索关键词
            tool_name: MCP 工具名，默认 "common_search"（标准版）。
                       如果 list_all_tools() 显示工具名不同，请修改此处。

        返回：
            搜索结果列表，每项包含 title, url, description

        注意：
            解析逻辑做了多层兼容：先尝试 JSON 解析（取 pageItems/results），
            失败则整段作为 description。如实际返回格式不符，请调整解析逻辑。
        """
        # 1. 查缓存
        if self._search_cache:
            cached = await self._search_cache.get(query)
            if cached is not None:
                print(f"[Cache] 命中: {query[:40]}...")
                return cached

        # 2. 调用 MCP 工具 common_search
        if self._session is None:
            raise RuntimeError("IQS Search MCP Server 未连接")

        # 默认使用 common_search（标准搜索）。
        # 如 list_all_tools() 输出显示工具名不同（如 web_search），请修改此处。
        tool_name = "common_search"

        result = await self._session.call_tool(
            tool_name,
            {"query": query},
        )

        # 解析结果（MCP 返回的是 Content 对象列表）
        search_results = []
        for content in result.content:
            if getattr(content, "type", None) == "text":
                import json
                try:
                    data = json.loads(content.text)
                    # 如果是列表，逐条解析
                    if isinstance(data, list):
                        for item in data:
                            search_results.append({
                                "title": item.get("title", "无标题"),
                                "url": item.get("url", item.get("link", "")),
                                "description": item.get("description", item.get("snippet", item.get("mainText", ""))),
                            })
                    # 如果是字典，尝试取 results / pageItems
                    elif isinstance(data, dict):
                        items = data.get("results", data.get("pageItems", [data]))
                        if not isinstance(items, list):
                            items = [items]
                        for item in items:
                            search_results.append({
                                "title": item.get("title", "无标题"),
                                "url": item.get("url", item.get("link", "")),
                                "description": item.get("description", item.get("snippet", item.get("mainText", ""))),
                            })
                    else:
                        search_results.append({"title": "", "url": "", "description": content.text})
                except json.JSONDecodeError:
                    # 非 JSON（常见情况：markdown 格式返回），整段作为 description
                    search_results.append({"title": "", "url": "", "description": content.text})

        # 3. 写缓存
        if self._search_cache and search_results:
            await self._search_cache.set(query, search_results)

        print(f"[Search] '{query[:40]}...' 获取 {len(search_results)} 条结果")
        return search_results

    # ------------------------------------------------------------------
    # 辅助：列出所有可用工具（调试用）
    # ------------------------------------------------------------------

    async def list_all_tools(self) -> None:
        """打印 IQS MCP Server 提供的工具列表（调试用）。"""
        if self._session is None:
            print("[MCP] 未连接")
            return
        tools = await self._session.list_tools()
        print(f"\n[MCP] IQS Search 提供的工具:")
        for tool in tools.tools:
            print(f"  - {tool.name}: {tool.description}")