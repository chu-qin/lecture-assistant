"""ChromaDB 向量存储实现。"""

import logging
import uuid
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import ChromaDBConfig
from .base import BaseEmbedder, BaseVectorStore, SearchResult, VectorStoreError

logger = logging.getLogger(__name__)


class ChromaVectorStore(BaseVectorStore):
    def __init__(self, config: ChromaDBConfig, embedder: BaseEmbedder):
        self._config = config
        self._embedder = embedder

        persist_path = Path(config.persist_directory).resolve()
        persist_path.mkdir(parents=True, exist_ok=True)

        logger.info("初始化 ChromaDB，持久化路径: %s", persist_path)
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self._collection = self._client.get_or_create_collection(
            name=config.collection_name,
            metadata={"hnsw:space": config.distance_metric},
        )
        logger.info(
            "ChromaDB collection '%s' 就绪，文档数: %d",
            config.collection_name,
            self._collection.count(),
        )

    def add_documents(
        self,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str] | None = None,
    ) -> list[str]:
        if len(chunks) != len(metadatas):
            raise VectorStoreError(
                f"chunks 和 metadatas 长度不一致: {len(chunks)} vs {len(metadatas)}"
            )
        if not chunks:
            return []

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in chunks]

        logger.info("正在嵌入 %d 个文本块...", len(chunks))
        embeddings = self._embedder.embed(chunks)

        logger.info("正在写入 ChromaDB...")
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        logger.info("已添加 %d 个文档块到知识库", len(chunks))
        return ids

    def search(self, query: str, top_k: int = 5, where: dict | None = None) -> list[SearchResult]:
        query_embedding = self._embedder.embed_query(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            where=where,
        )

        search_results: list[SearchResult] = []
        if not results["ids"] or not results["ids"][0]:
            return search_results

        for i, doc_id in enumerate(results["ids"][0]):
            search_results.append(
                SearchResult(
                    content=(
                        results.get("documents", [[""]])[0][i]
                        if results.get("documents")
                        else ""
                    ),
                    metadata=(
                        results.get("metadatas", [[{}]])[0][i]
                        if results.get("metadatas")
                        else {}
                    ),
                    score=(
                        1.0 - results.get("distances", [[0.0]])[0][i]
                        if results.get("distances")
                        else 0.0
                    ),
                    source_id=doc_id,
                )
            )

        return search_results

    def delete_collection(self) -> None:
        name = self._config.collection_name
        logger.warning("正在删除 collection: %s", name)
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": self._config.distance_metric},
        )
        logger.info("Collection 已重建")

    def count(self) -> int:
        return self._collection.count()

    def update_documents(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        if not ids:
            return
        if len(ids) != len(texts) or len(ids) != len(metadatas):
            raise VectorStoreError(
                f"ids、texts、metadatas 长度不一致: {len(ids)} vs {len(texts)} vs {len(metadatas)}"
            )
        logger.info("正在更新 %d 个文档...", len(ids))
        embeddings = self._embedder.embed(texts)
        self._collection.update(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts,
        )
        logger.info("已更新 %d 个文档", len(ids))

    def delete_by_id(self, ids: list[str]) -> None:
        if not ids:
            return
        logger.info("正在删除 %d 个文档...", len(ids))
        self._collection.delete(ids=ids)
        logger.info("已删除 %d 个文档", len(ids))
