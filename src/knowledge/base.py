"""知识库抽象基类与数据契约。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# ============================================================
# 异常
# ============================================================


class KnowledgeBaseError(Exception):
    """知识库模块基础异常。"""

    pass


class EmbeddingError(KnowledgeBaseError):
    """嵌入生成失败。"""

    pass


class VectorStoreError(KnowledgeBaseError):
    """向量存储操作失败。"""

    pass


# ============================================================
# 数据类
# ============================================================


@dataclass
class SearchResult:
    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0
    source_id: str = ""


# ============================================================
# 抽象基类
# ============================================================


class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本嵌入向量。"""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """为单个查询生成嵌入向量。"""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量维度。"""
        ...


class BaseVectorStore(ABC):
    @abstractmethod
    def add_documents(
        self,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str] | None = None,
    ) -> list[str]:
        """向向量库添加文档块。"""
        ...

    @abstractmethod
    def search(self, query: str, top_k: int = 5, where: dict | None = None) -> list[SearchResult]:
        """语义检索相似文档，可选 metadata 过滤。"""
        ...

    @abstractmethod
    def delete_collection(self) -> None:
        """删除当前集合及其所有数据。"""
        ...

    @abstractmethod
    def count(self) -> int:
        """返回集合中的文档数量。"""
        ...

    @abstractmethod
    def update_documents(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """更新已有文档的文本和元数据（重新嵌入）。"""
        ...

    @abstractmethod
    def delete_by_id(self, ids: list[str]) -> None:
        """按 ID 列表删除文档。"""
        ...
