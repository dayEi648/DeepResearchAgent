"""
LangGraph 状态定义

作用：定义 ResearchState TypedDict，作为整个工作流中各节点共享的数据结构。
LangGraph 会自动在每个节点执行前后，把当前 State 的快照保存到 Checkpoint。
"""
from typing import TypedDict

class ResearchState(TypedDict, total=False):
    """
    研究工作流的状态结构。

    total=False 表示所有字段都是可选的，节点可以只返回需要更新的字段。
    """
    # --- 用户输入 ---
    topic: str
    """用户提交的研究主题"""

    # --- Planner 输出 ---
    plan: list[str]
    """拆解出的子任务清单（3~5 项）"""

    # --- Researcher 输出 ---
    search_results: dict[str, list[dict]]
    """搜索结果，key=子任务名称, value=搜索结果列表"""

    # --- Analyzer 输出 ---
    analysis: str
    """分析结论文本"""

    # --- Writer 输出 ---
    report: str
    """Markdown 格式报告全文"""

    # --- Reviewer 输出 ---
    review_feedback: str
    """审核意见"""
    review_passed: bool
    """审核是否通过"""

    # --- 控制字段 ---
    task_id: str
    """任务唯一标识（由 FastAPI 层传入）"""
    iteration_count: int
    """审核循环次数（0~2），防死循环"""
    current_node: str
    """当前执行节点名（用于 SSE 进度推送）"""