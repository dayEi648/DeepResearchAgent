"""
LangGraph 状态机构建

作用：定义节点、边、条件流转逻辑，编译成可执行的图。
编译时注入 RedisCheckpointSaver，实现断点续传。
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from app.agents.nodes import (
    analyzer_node,
    planner_node,
    push_event,
    researcher_node,
    reviewer_node,
    writer_node,
)
from app.agents.state import ResearchState

def should_continue(state: ResearchState) -> str:
    """
    条件边决策函数：Reviewer 之后决定下一步走向。

    返回：
        "save_report": 审核通过，保存报告
        "rewrite":     审核不通过，且还能重试（iteration < 2）
        "END":         审核不通过，但已达最大重试次数，强制结束
    """
    passed = state.get("review_passed", False)
    iteration = state.get("iteration_count", 0)

    if passed:
        return "save_report"

    # 不通过，检查是否还能重试
    if iteration < 2:
        print(f"[Graph] 审核不通过，第 {iteration} 轮，回退到 Writer 重写")
        return "rewrite"
    else:
        print(f"[Graph] 审核不通过，已达最大重试次数（{iteration} 轮），强制结束")
        return "END"
    

async def save_report_node(state: ResearchState) -> dict:
    """
    保存报告节点：
        1. 使用 aiofiles 异步写入本地磁盘（兜底/开发环境）
        2. 上传到阿里云 OSS（线上环境，返回可下载外链）

    注意：
        如果 OSS 未配置（.env 中缺少相关配置），则只保存本地文件，
        保持向后兼容，不影响本地开发。
    """
    import aiofiles

    from app.config import settings
    from app.tools.oss_client import oss_client

    task_id = state.get("task_id", "unknown")
    report = state["report"]

    # 推送 SSE 开始事件
    await push_event(task_id, {"event_type": "node_start", "node": "save_report"})

    # ---- 1. 本地保存（始终执行，作为兜底） ----
    filename = f"{task_id}.md"
    filepath = settings.reports_dir / filename

    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(report)

    print(f"[Graph] 报告已保存到本地: {filepath}")

    # ---- 2. 上传到 OSS（如果已配置） ----
    report_url = str(filepath)  # 默认用本地路径
    if oss_client.enabled:
        try:
            report_url = await oss_client.upload_report(task_id, report)
            print(f"[Graph] 报告已上传到 OSS: {report_url}")
        except Exception as e:
            print(f"[Graph] OSS 上传失败（将使用本地路径）: {e}")
    else:
        print("[Graph] OSS 未配置，跳过上传")

    # 推送 SSE 完成事件
    await push_event(task_id, {
        "event_type": "node_complete",
        "node": "save_report",
        "output": {"report_path": report_url},
    })

    return {"current_node": "save_report", "report_path": report_url}

def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """
    构建并编译 LangGraph 状态机。

    参数：
        checkpointer: RedisCheckpointSaver 实例（可选，传入则启用断点续传）

    返回：
        编译好的 StateGraph 实例
    """
    # 1. 创建状态图
    builder = StateGraph(ResearchState)

    # 2. 添加节点
    builder.add_node("planner", planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("writer", writer_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("save_report", save_report_node)

    # 3. 添加边
    builder.set_entry_point("planner")           # 起点
    builder.add_edge("planner", "researcher")    # 普通边
    builder.add_edge("researcher", "analyzer")   # 普通边
    builder.add_edge("analyzer", "writer")       # 普通边
    builder.add_edge("writer", "reviewer")       # 普通边

    # 4. 条件边：reviewer 之后根据审核结果分支
    builder.add_conditional_edges(
        "reviewer",
        should_continue,           # 决策函数
        {
            "save_report": "save_report",
            "rewrite": "writer",   # 回退到 writer 重写
            "END": END,            # 强制结束
        },
    )
    
    # save_report 之后结束
    builder.add_edge("save_report", END)

    # 5. 编译（注入 Checkpoint Saver）
    graph = builder.compile(checkpointer=checkpointer)
    print("[Graph] LangGraph 状态机编译完成")
    return graph
