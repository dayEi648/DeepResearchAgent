"""
LangGraph 各 Agent 节点实现

作用：实现 Planner、Researcher、Analyzer、Writer、Reviewer 五个节点的逻辑。
每个节点接收当前 State，执行 LLM 调用或外部工具调用，返回更新后的字段。
"""
import asyncio
import json
from typing import Any

from app.agents.state import ResearchState
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from app.config import settings
from app.rag.vectorstore import similarity_search
from app.tools.mcp_client import MCPClient

# ------------------------------------------------------------------
# 全局：LLM 实例（复用，避免重复初始化）
# ------------------------------------------------------------------

# 默认使用 DeepSeek-v4-pro（指定的模型）
# 如配置了其他厂商的 Key，可自动切换
_model_name = "deepseek-v4-pro"
if settings.zhipu_api_key and not settings.deepseek_api_key:
    _model_name = "glm-4.7-flash"
elif settings.openai_api_key and not settings.deepseek_api_key:
    _model_name = "gpt-4o-mini"

llm = ChatOpenAI(
    api_key=settings.active_llm_api_key,
    base_url=settings.active_llm_base_url,
    model=_model_name,
    temperature=0.3,          # 低温度，输出更稳定
    request_timeout=settings.agent_node_timeout,
)

# ------------------------------------------------------------------
# SSE 事件推送（全局队列，由 graph.py / main.py 管理）
# ------------------------------------------------------------------

TASK_QUEUES: dict[str, asyncio.Queue[dict[str, Any]]] = {}

async def push_event(task_id: str, event: dict[str, Any]) -> None:
    """将事件推送到对应任务的 SSE 队列。"""
    queue = TASK_QUEUES.get(task_id)
    if queue is not None:
        await queue.put(event)

def _task_id_from_config(config: RunnableConfig) -> str:
    """从 RunnableConfig 中提取 task_id（即 thread_id）。"""
    return config["configurable"]["thread_id"]

# ------------------------------------------------------------------
# Node 1: Planner — 任务规划
# ------------------------------------------------------------------

async def planner_node(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """
    Planner Agent：将研究主题拆解为 3~5 个并行的子研究任务。

    输出字段：
        - plan: 子任务清单
        - current_node: "planner"
    """
    task_id = _task_id_from_config(config)
    topic = state["topic"]

    # 推送 SSE 开始事件
    await push_event(task_id, {"event_type": "node_start", "node": "planner"})

    # 构造 Prompt
    messages = [
        SystemMessage(
            content="""你是一位专业的研究规划专家。请将用户的研究主题拆解为 3~5 个并行的子研究任务。
要求：
1. 每个子任务必须是一个具体、可搜索的问题
2. 子任务之间要有互补性，覆盖主题的不同维度
3. 输出严格的 JSON 数组格式，不要有任何其他文字

输出格式示例：
["2026年主流AI Agent框架有哪些","各框架的核心特性与架构对比","社区活跃度与GitHub数据对比","企业级应用场景与案例"]"""
        ),
        HumanMessage(content=f"研究主题：{topic}"),
    ]

    # 调用 LLM
    response = await llm.ainvoke(messages)
    content = response.content.strip()

    # 解析 JSON（LLM 有时会包在 markdown 代码块里）
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
        if content.startswith("json"):
            content = content[4:].strip()
    
    plan = json.loads(content)
    if not isinstance(plan, list) or len(plan) < 1:
        plan = [f"关于{topic}的综合调研"]

    print(f"[Planner] 拆解为 {len(plan)} 个子任务: {plan}")

    # 推送 SSE 完成事件
    await push_event(task_id, {
        "event_type": "node_complete",
        "node": "planner",
        "output": {"plan": plan},
    })

    return {"plan": plan, "current_node": "planner"}

# ------------------------------------------------------------------
# Node 2: Researcher — 并行搜索
# ------------------------------------------------------------------

async def researcher_node(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """
    Researcher Agent：对每个子任务并行调用 MCP Search 收集资料。

    并行方式：内部使用 asyncio.gather，同时发起多个搜索请求。
    输出字段：
        - search_results: dict[str, list[dict]]
        - current_node: "researcher"
    """
    task_id = _task_id_from_config(config)
    plan = state["plan"]

    await push_event(task_id, {"event_type": "node_start", "node": "researcher"})

    # 复用同一个 MCPClient 连接，对所有子任务并行搜索
    # 避免每个子任务都新建 SSE 连接，提升效率
    try:
        async with MCPClient() as client:
            coroutines = [client.search(query) for query in plan]
            results_list = await asyncio.gather(*coroutines, return_exceptions=True)
    except Exception as e:
        print(f"[Researcher] MCP 连接失败: {e}")
        # 连接失败时，所有子任务都返回错误
        results_list = [e] * len(plan)

    # 组装结果字典
    search_results: dict[str, list[dict]] = {}
    for query, result in zip(plan, results_list):
        if isinstance(result, Exception):
            search_results[query] = [{"title": "异常", "url": "", "description": str(result)}]
        else:
            search_results[query] = result

    total_results = sum(len(v) for v in search_results.values())
    print(f"[Researcher] 并行搜索完成，共 {total_results} 条结果")

    await push_event(task_id, {
        "event_type": "node_complete",
        "node": "researcher",
        "output": {"search_results": search_results},
    })

    return {"search_results": search_results, "current_node": "researcher"}

# ------------------------------------------------------------------
# Node 3: Analyzer — 分析整合（带 RAG）
# ------------------------------------------------------------------

async def analyzer_node(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """
    Analyzer Agent：结合 RAG 检索的方法论模板，分析整合所有搜索结果。

    输出字段：
        - analysis: 分析结论文本
        - current_node: "analyzer"
    """
    task_id = _task_id_from_config(config)
    topic = state["topic"]
    search_results = state["search_results"]

    await push_event(task_id, {"event_type": "node_start", "node": "analyzer"})

    # 1. RAG 检索：获取报告写作模板
    try:
        methodology_chunks = similarity_search("技术调研报告结构与写作规范", k=3)
        methodology_text = "\n\n".join(methodology_chunks)
    except Exception as e:
        print(f"[Analyzer] RAG 检索失败（非致命）: {e}")
        methodology_text = ""

    # 2. 构造搜索结果摘要（避免 Prompt 过长）
    search_summary = ""
    for query, results in search_results.items():
        search_summary += f"\n## 子任务：{query}\n"
        for i, r in enumerate(results[:3], 1):  # 每个子任务取前 3 条
            title = r.get("title", "无标题")
            desc = r.get("description", "")[:300]  # 截断，控制长度
            search_summary += f"{i}. {title}: {desc}\n"
    
    # 3. 构造 Prompt
    methodology_section = (
        f"\n\n【参考方法论模板】\n{methodology_text}\n"
        if methodology_text
        else ""
    )

    messages = [
        SystemMessage(
            content=f"""你是一位资深技术分析师。请基于以下搜索结果，撰写一份结构化的分析结论。

要求：
1. 按"概述 → 各维度对比 → 关键发现 → 结论"的结构组织
2. 引用具体数据和事实支撑观点
3. 指出各方案的优势和局限性
4. 语言专业、客观，避免主观臆断{methodology_section}"""
        ),
        HumanMessage(
            content=f"研究主题：{topic}\n\n【搜索结果汇总】{search_summary}"
        ),
    ]

    response = await llm.ainvoke(messages)
    analysis = response.content.strip()

    print(f"[Analyzer] 分析完成，长度 {len(analysis)} 字符")

    await push_event(task_id, {
        "event_type": "node_complete",
        "node": "analyzer",
        "output": {"analysis": analysis[:500] + "..."},  # SSE 只推送摘要
    })

    return {"analysis": analysis, "current_node": "analyzer"}

# ------------------------------------------------------------------
# Node 4: Writer — 报告撰写
# ------------------------------------------------------------------

async def writer_node(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """
    Writer Agent：基于 Analyzer 的分析结论，撰写 Markdown 格式的结构化研究报告。

    输出字段：
        - report: Markdown 报告全文
        - current_node: "writer"
    """
    task_id = _task_id_from_config(config)
    topic = state["topic"]
    analysis = state["analysis"]
    feedback = state.get("review_feedback", "")
    iteration = state.get("iteration_count", 0)

    await push_event(task_id, {"event_type": "node_start", "node": "writer"})

    # 如果有审核反馈（重写场景），加入 Prompt
    feedback_section = ""
    if feedback and iteration > 0:
        feedback_section = f"""\n\n【上一轮审核意见（请针对以下问题进行修改）】\n{feedback}\n"""

    messages = [
        SystemMessage(
            content="""你是一位技术文档写作专家。请将以下分析结论改写为一份完整的 Markdown 格式技术调研报告。

报告要求：
1. 标题用一级标题 `#`
2. 每个大章节用二级标题 `##`
3. 对比内容用 Markdown 表格呈现
4. 包含"概述、方案对比、数据支撑、结论与建议、风险提示"五个章节
5. 语言专业、结构清晰、格式规范"""
        ),
        HumanMessage(
            content=f"研究主题：{topic}\n\n【分析结论】\n{analysis}{feedback_section}"
        ),
    ]

    response = await llm.ainvoke(messages)
    report = response.content.strip()

    # 确保是合法 Markdown（简单清理）
    if not report.startswith("#"):
        report = f"# {topic}\n\n{report}"

    print(f"[Writer] 报告撰写完成，长度 {len(report)} 字符")

    await push_event(task_id, {
        "event_type": "node_complete",
        "node": "writer",
        "output": {"report_length": len(report)},
    })

    return {"report": report, "current_node": "writer"}

# ------------------------------------------------------------------
# Node 5: Reviewer — 质量审核
# ------------------------------------------------------------------

async def reviewer_node(state: ResearchState, config: RunnableConfig) -> dict[str, Any]:
    """
    Reviewer Agent：审核报告质量，判断是否通过。

    审核维度：
        1. 结构完整性（是否包含要求的五个章节）
        2. 逻辑一致性（论据是否支撑结论）
        3. 格式规范性（Markdown 语法、表格等）

    输出字段：
        - review_passed: bool
        - review_feedback: str
        - iteration_count: +1
        - current_node: "reviewer"
    """
    task_id = _task_id_from_config(config)
    topic = state["topic"]
    report = state["report"]
    iteration = state.get("iteration_count", 0)

    await push_event(task_id, {"event_type": "node_start", "node": "reviewer"})

    messages = [
        SystemMessage(
            content="""你是一位技术文档审校专家。请对以下研究报告进行审核，输出严格的 JSON 格式。

审核维度：
1. 结构完整性：是否包含"概述、方案对比、数据支撑、结论与建议、风险提示"
2. 逻辑一致性：论据是否能支撑结论，有无自相矛盾
3. 格式规范性：Markdown 语法是否正确，表格是否规范

输出格式（严格 JSON，不要 Markdown 代码块）：
{"passed": true/false, "feedback": "具体审核意见，如果不通过请指出需要修改的问题"}"""
        ),
        HumanMessage(
            content=f"研究主题：{topic}\n\n【报告全文】\n{report[:8000]}"  # 截断，避免超长
        ),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    # 解析 JSON
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
        if content.startswith("json"):
            content = content[4:].strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # LLM 输出不规范，默认通过（避免卡住）
        result = {"passed": True, "feedback": "解析失败，默认通过"}

    passed = result.get("passed", True)
    feedback = result.get("feedback", "")

    new_iteration = iteration + 1
    print(f"[Reviewer] 第 {new_iteration} 轮审核结果: {'通过' if passed else '不通过'}")

    await push_event(task_id, {
        "event_type": "node_complete",
        "node": "reviewer",
        "output": {"result": "passed" if passed else "rejected", "feedback": feedback},
    })

    return {
        "review_passed": passed,
        "review_feedback": feedback,
        "iteration_count": new_iteration,
        "current_node": "reviewer",
    }
