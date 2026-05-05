"""
RAG 向量数据库模块

作用：管理 ChromaDB 向量库，提供文档加载、切分、存入、检索功能。

生命周期：
    - 应用启动时调用 init_vectorstore() 初始化（加载知识库文档）
    - 运行时通过 similarity_search() 检索相关内容
"""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


# 全局单例：应用启动后只初始化一次
_vectorstore: Chroma | None = None


def init_vectorstore() -> Chroma:
    """
    初始化 ChromaDB 向量库。

    步骤：
        1. 加载 knowledge_base/ 下所有 .md 文件
        2. 切分成小块（chunk_size=500, overlap=50）
        3. 用阿里云百炼 text-embedding-v4 向量化（默认 1024 维，免费额度）
        4. 存入本地 ChromaDB（目录：./chroma_db）

    返回：
        初始化好的 Chroma 实例
    """
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    persist_dir = settings.project_root / "chroma_db"

    # 如果 chroma_db 已存在且非空，直接加载已有向量库（防止重复写入）
    if persist_dir.exists() and any(persist_dir.iterdir()):
        print("[RAG] 发现已有向量库，直接加载...")
        _vectorstore = Chroma(
            collection_name="methodology",
            embedding_function=DashScopeEmbeddings(
                dashscope_api_key=settings.dashscope_api_key,
                model="text-embedding-v4",
            ),
            persist_directory=str(persist_dir),
        )
        return _vectorstore

    # 1. 加载所有 Markdown 文档
    docs = []
    kb_dir = settings.knowledge_base_dir
    if kb_dir.exists():
        for md_file in kb_dir.glob("*.md"):
            loader = TextLoader(str(md_file), encoding="utf-8")
            docs.extend(loader.load())

    if not docs:
        print("[RAG] 警告：knowledge_base/ 目录下没有找到 .md 文件，RAG 将不可用")
        # 创建一个空的 Chroma 实例，避免后续代码报错
        _vectorstore = Chroma(
            collection_name="methodology",
            embedding_function=DashScopeEmbeddings(
                dashscope_api_key=settings.dashscope_api_key,
                model="text-embedding-v4",
            ),
            persist_directory=str(persist_dir),
        )
        return _vectorstore

    # 2. 切分文档
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,      # 每块 500 字符
        chunk_overlap=50,    # 重叠 50 字符，保证语义连贯
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", " "],  # 优先按标题切分
    )
    chunks = splitter.split_documents(docs)
    print(f"[RAG] 知识库加载完成：{len(docs)} 篇文档 → 切分为 {len(chunks)} 个片段")

    # 3. 向量化并存入 ChromaDB
    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=DashScopeEmbeddings(
            dashscope_api_key=settings.dashscope_api_key,
            model="text-embedding-v4",
        ),
        collection_name="methodology",
        persist_directory=str(persist_dir),
    )
    print("[RAG] ChromaDB 向量库初始化完成")

    return _vectorstore


def similarity_search(query: str, k: int = 3) -> list[str]:
    """
    检索与研究主题相关的知识库片段。

    参数：
        query: 查询词（如"技术调研报告结构"）
        k: 返回最相关的 k 条片段

    返回：
        文本片段列表
    """
    vs = init_vectorstore()
    results = vs.similarity_search(query, k=k)
    return [doc.page_content for doc in results]    