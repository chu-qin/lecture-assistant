"""Sentence-Transformers 文本嵌入器。"""

import logging
from typing import Any

import streamlit as st
from sentence_transformers import SentenceTransformer

from ..config import EmbeddingConfig
from .base import BaseEmbedder, EmbeddingError


@st.cache_resource
def get_embedder(config: EmbeddingConfig) -> "SentenceTransformersEmbedder":
    """缓存嵌入模型实例，避免重复加载 ~90MB 模型文件。"""
    return SentenceTransformersEmbedder(config)


logger = logging.getLogger(__name__)

# BGE 模型查询时需要的 instruction prefix
_BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


class SentenceTransformersEmbedder(BaseEmbedder):
    def __init__(self, config: EmbeddingConfig):
        self._config = config
        logger.info("加载嵌入模型: %s (device=%s)", config.model_name, config.device)
        try:
            self._model: Any = SentenceTransformer(
                config.model_name,
                device=config.device,
            )
        except Exception as e:
            raise EmbeddingError(f"嵌入模型加载失败: {e}")

        self._dim = self._model.get_sentence_embedding_dimension()
        logger.info("嵌入模型加载完成，维度=%d", self._dim)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            embeddings = self._model.encode(
                texts,
                normalize_embeddings=self._config.normalize,
                show_progress_bar=False,
            )
            return embeddings.tolist()  # type: ignore[union-attr]
        except Exception as e:
            raise EmbeddingError(f"文本嵌入失败: {e}")

    def embed_query(self, query: str) -> list[float]:
        prefixed = f"{_BGE_QUERY_PREFIX}{query}"
        try:
            embedding = self._model.encode(
                [prefixed],
                normalize_embeddings=self._config.normalize,
                show_progress_bar=False,
            )
            return embedding[0].tolist()  # type: ignore[union-attr]
        except Exception as e:
            raise EmbeddingError(f"查询嵌入失败: {e}")

    @property
    def dimension(self) -> int:
        return self._dim
