"""
配置管理模块

作用：集中管理所有环境变量和配置项，通过 Pydantic Settings 自动从 .env 文件加载。
用法：from app.config import settings
"""
import json
import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """应用配置类，所有配置项都在这里定义。"""

    # Pydantic Settings 会自动读取 .env 文件
    model_config = SettingsConfigDict(
        env_file = ".env",           # 从 .env 加载环境变量
        env_file_encoding = "utf-8", # 文件编码
        extra="ignore",              # 忽略 .env 中未定义的多余变量
    )

    # --- LLM 配置（默认 DeepSeek，兼容 OpenAI 格式） ---
    deepseek_api_key: str | None = None
    openai_api_key: str | None = None
    zhipu_api_key: str | None = None

    # --- 阿里云百炼（Embedding 向量模型） ---
    dashscope_api_key: str | None = None
    
    # --- 阿里云 IQS Search ---
    iqssearch_api_key: str | None = None

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- 限流 ---
    max_concurrent_research: int = 5

    # --- 超时 ---
    agent_node_timeout: int = 60

    # --- 阿里云 OSS ---
    oss_bucket_name: str | None = None
    oss_endpoint: str | None = None
    oss_access_key_id: str | None = None
    oss_access_key_secret: str | None = None
    oss_report_prefix: str = "reports"  # OSS 中报告文件的存储前缀

    # --- 项目路径 ---
    project_root: Path = Path(__file__).parent.parent
    reports_dir: Path = project_root / "reports"
    knowledge_base_dir: Path = project_root / "knowledge_base"
    mcp_settings_path: Path = project_root / "mcp_settings.json"

    # --- 派生属性：实际使用的 LLM API Key ---
    @property
    def active_llm_api_key(self) -> str:
        """返回当前生效的 LLM API Key（优先级：DeepSeek > OpenAI > Zhipu）"""
        if self.deepseek_api_key:
            return self.deepseek_api_key
        if self.openai_api_key:
            return self.openai_api_key
        if self.zhipu_api_key:
            return self.zhipu_api_key
        raise ValueError("至少需要一个 LLM API Key（DEEPSEEK_API_KEY / OPENAI_API_KEY / ZHIPU_API_KEY）")

    @property
    def active_llm_base_url(self) -> str | None:
        """返回当前生效的 LLM Base URL。"""
        if self.deepseek_api_key:
            return "https://api.deepseek.com"
        if self.openai_api_key:
            return None  # OpenAI 使用默认官方地址
        if self.zhipu_api_key:
            return "https://open.bigmodel.cn/api/paas/v4/"
        return None
    
    # --- MCP 配置（读取 JSON 并替换变量占位符） ---
    @property
    def mcp_config(self) -> dict[str, Any]:
        """
        读取 mcp_settings.json，并替换 ${VAR_NAME} 格式的占位符为实际值。

        支持从当前 Settings 实例和环境变量中查找替换值。
        """
        import re

        raw = self.mcp_settings_path.read_text(encoding="utf-8")

        def _replace_var(match: re.Match) -> str:
            """替换 ${VAR_NAME} 为对应的配置值。"""
            var_name = match.group(1)
            # 优先从当前 settings 实例查找（如 iqssearch_api_key）
            if hasattr(self, var_name.lower()):
                val = getattr(self, var_name.lower())
                if val is not None:
                    return str(val)
            # 其次从环境变量查找
            env_val = os.environ.get(var_name)
            if env_val is not None:
                return env_val
            # 找不到则保留原样，便于调试时发现
            return match.group(0)

        # 匹配 ${VAR_NAME} 格式
        resolved = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", _replace_var, raw)
        return json.loads(resolved)

# 全局单例：整个应用共享同一个 settings 实例
settings = Settings()

# 确保 reports 目录存在（本地开发/兜底用）
settings.reports_dir.mkdir(parents=True, exist_ok=True)