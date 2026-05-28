"""测试 SentenceTransformersEmbedder — 文本嵌入。"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.config import EmbeddingConfig
from src.knowledge.base import EmbeddingError
from src.knowledge.embedder import SentenceTransformersEmbedder


@pytest.fixture
def emb_config():
    return EmbeddingConfig(
        model_name="BAAI/bge-small-zh-v1.5",
        device="cpu",
        normalize=True,
    )


@pytest.fixture
def mock_st_model():
    """创建一个模拟的 SentenceTransformer 模型。"""
    mock = MagicMock()
    mock.get_sentence_embedding_dimension.return_value = 512
    mock.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    return mock


class TestEmbed:
    """SentenceTransformersEmbedder.embed() 单元测试。"""

    def test_embed_calls_model(self, emb_config, mock_st_model):
        with patch("src.knowledge.embedder.SentenceTransformer",
                   return_value=mock_st_model):
            embedder = SentenceTransformersEmbedder(emb_config)
            result = embedder.embed(["text1", "text2"])

        assert len(result) == 2
        assert len(result[0]) == 3
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
        mock_st_model.encode.assert_called_once()
        call_kwargs = mock_st_model.encode.call_args
        assert call_kwargs[1]["normalize_embeddings"] is True
        assert call_kwargs[1]["show_progress_bar"] is False

    def test_embed_query_applies_prefix(self, emb_config, mock_st_model):
        with patch("src.knowledge.embedder.SentenceTransformer",
                   return_value=mock_st_model):
            embedder = SentenceTransformersEmbedder(emb_config)
            embedder.embed_query("测试查询")

        call_args = mock_st_model.encode.call_args[0][0]
        assert call_args[0].startswith("为这个句子生成表示以用于检索相关文章：")
        assert "测试查询" in call_args[0]

    def test_embed_empty_list(self, emb_config, mock_st_model):
        with patch("src.knowledge.embedder.SentenceTransformer",
                   return_value=mock_st_model):
            embedder = SentenceTransformersEmbedder(emb_config)
            result = embedder.embed([])

        assert result == []
        mock_st_model.encode.assert_not_called()

    def test_dimension_property(self, emb_config, mock_st_model):
        with patch("src.knowledge.embedder.SentenceTransformer",
                   return_value=mock_st_model):
            embedder = SentenceTransformersEmbedder(emb_config)

        assert embedder.dimension == 512

    def test_embedder_load_failure(self, emb_config):
        with patch("src.knowledge.embedder.SentenceTransformer",
                   side_effect=RuntimeError("模型下载失败")):
            with pytest.raises(EmbeddingError, match="模型下载失败"):
                SentenceTransformersEmbedder(emb_config)

    def test_embed_encode_failure(self, emb_config, mock_st_model):
        mock_st_model.encode.side_effect = RuntimeError("encode error")
        with patch("src.knowledge.embedder.SentenceTransformer",
                   return_value=mock_st_model):
            embedder = SentenceTransformersEmbedder(emb_config)
            with pytest.raises(EmbeddingError, match="encode error"):
                embedder.embed(["text"])

    def test_embed_query_encode_failure(self, emb_config, mock_st_model):
        mock_st_model.encode.side_effect = RuntimeError("query error")
        with patch("src.knowledge.embedder.SentenceTransformer",
                   return_value=mock_st_model):
            embedder = SentenceTransformersEmbedder(emb_config)
            with pytest.raises(EmbeddingError, match="query error"):
                embedder.embed_query("query")

    def test_normalize_false(self, emb_config, mock_st_model):
        emb_config.normalize = False
        with patch("src.knowledge.embedder.SentenceTransformer",
                   return_value=mock_st_model):
            embedder = SentenceTransformersEmbedder(emb_config)
            embedder.embed(["text"])

        call_kwargs = mock_st_model.encode.call_args
        assert call_kwargs[1]["normalize_embeddings"] is False
