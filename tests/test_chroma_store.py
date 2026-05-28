"""测试 ChromaVectorStore — ChromaDB 向量存储操作。"""

import uuid
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.config import ChromaDBConfig
from src.knowledge.base import SearchResult, VectorStoreError
from src.knowledge.chroma_store import ChromaVectorStore

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def chroma_config():
    """返回测试用 ChromaDBConfig。"""
    return ChromaDBConfig(
        persist_directory="data/chroma_db",
        collection_name="course_content",
        distance_metric="cosine",
    )


@pytest.fixture
def mock_embedder():
    """返回模拟的 BaseEmbedder。"""
    m = MagicMock()
    m.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
    m.embed_query.return_value = [0.5, 0.6]
    type(m).dimension = PropertyMock(return_value=128)
    return m


@pytest.fixture
def mock_collection():
    """返回模拟的 ChromaDB collection。"""
    m = MagicMock()
    m.count.return_value = 5
    m.query.return_value = {
        "ids": [["id1", "id2"]],
        "documents": [["doc text 1", "doc text 2"]],
        "metadatas": [[{"source": "test1"}, {"source": "test2"}]],
        "distances": [[0.15, 0.35]],
    }
    return m


@pytest.fixture
def store(chroma_config, mock_embedder, mock_collection, tmp_path):
    """返回使用 mock 依赖的 ChromaVectorStore。"""
    chroma_config.persist_directory = str(tmp_path / "chroma_db")
    with patch("src.knowledge.chroma_store.chromadb.PersistentClient") as mock_client_cls:
        mock_client_cls.return_value.get_or_create_collection.return_value = mock_collection
        yield ChromaVectorStore(chroma_config, mock_embedder)


# ============================================================
# TestInit
# ============================================================


class TestInit:
    """测试 __init__ — 构造函数。"""

    def test_creates_persist_directory(self, store, chroma_config, tmp_path):
        import os

        expected = str(tmp_path / "chroma_db")
        assert os.path.isdir(expected)

    def test_initializes_persistent_client(self, mock_collection):
        config = ChromaDBConfig(persist_directory="/tmp/test_chroma")
        embedder = MagicMock()
        embedder.embed.return_value = []
        embedder.embed_query.return_value = []
        type(embedder).dimension = PropertyMock(return_value=128)

        with patch("src.knowledge.chroma_store.chromadb.PersistentClient") as mock_cls:
            mock_cls.return_value.get_or_create_collection.return_value = mock_collection
            ChromaVectorStore(config, embedder)
            assert mock_cls.called

    def test_calls_get_or_create_collection(self, mock_collection):
        config = ChromaDBConfig(
            persist_directory="/tmp/test_chroma",
            collection_name="my_collection",
            distance_metric="l2",
        )
        embedder = MagicMock()
        embedder.embed.return_value = []
        embedder.embed_query.return_value = []
        type(embedder).dimension = PropertyMock(return_value=128)

        with patch("src.knowledge.chroma_store.chromadb.PersistentClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_cls.return_value = mock_client
            ChromaVectorStore(config, embedder)
            mock_client.get_or_create_collection.assert_called_with(
                name="my_collection",
                metadata={"hnsw:space": "l2"},
            )

    def test_logs_document_count(self, mock_collection):
        config = ChromaDBConfig(persist_directory="/tmp/test_chroma")
        embedder = MagicMock()
        embedder.embed.return_value = []
        embedder.embed_query.return_value = []
        type(embedder).dimension = PropertyMock(return_value=128)

        with patch("src.knowledge.chroma_store.chromadb.PersistentClient") as mock_cls:
            mock_cls.return_value.get_or_create_collection.return_value = mock_collection
            ChromaVectorStore(config, embedder)
            assert mock_collection.count.called

    def test_creates_directory_when_missing(self, tmp_path):
        import os

        persist = str(tmp_path / "nonexistent" / "chroma")
        config = ChromaDBConfig(persist_directory=persist)
        embedder = MagicMock()
        embedder.embed.return_value = []
        embedder.embed_query.return_value = []
        type(embedder).dimension = PropertyMock(return_value=128)

        with patch("src.knowledge.chroma_store.chromadb.PersistentClient") as mock_cls:
            mock_cls.return_value.get_or_create_collection.return_value = MagicMock()
            ChromaVectorStore(config, embedder)
            assert os.path.isdir(persist)


# ============================================================
# TestAddDocuments
# ============================================================


class TestAddDocuments:
    """测试 add_documents() — 添加文档到向量库。"""

    def test_happy_path(self, store, mock_embedder, mock_collection):
        ids = store.add_documents(
            ["chunk1", "chunk2"],
            [{"k": "v1"}, {"k": "v2"}],
            ["id1", "id2"],
        )
        mock_embedder.embed.assert_called_once_with(["chunk1", "chunk2"])
        call_kwargs = mock_collection.add.call_args[1]
        assert call_kwargs["ids"] == ["id1", "id2"]
        assert call_kwargs["documents"] == ["chunk1", "chunk2"]
        assert call_kwargs["metadatas"] == [{"k": "v1"}, {"k": "v2"}]
        assert ids == ["id1", "id2"]

    def test_empty_chunks_returns_empty(self, store, mock_embedder, mock_collection):
        result = store.add_documents([], [])
        assert result == []
        mock_embedder.embed.assert_not_called()
        mock_collection.add.assert_not_called()

    def test_length_mismatch_raises(self, store):
        with pytest.raises(VectorStoreError, match="长度不一致"):
            store.add_documents(["a"], [{}, {}])

    def test_generates_uuids_when_ids_none(self, store, mock_collection):
        result = store.add_documents(["c1", "c2"], [{}, {}], ids=None)
        assert len(result) == 2
        for rid in result:
            uuid.UUID(rid)
        call_ids = mock_collection.add.call_args[1]["ids"]
        assert call_ids == result

    def test_uses_provided_ids(self, store, mock_collection):
        result = store.add_documents(["c1"], [{}], ids=["custom-id"])
        assert result == ["custom-id"]
        assert mock_collection.add.call_args[1]["ids"] == ["custom-id"]

    def test_calls_embedder_with_chunks(self, store, mock_embedder):
        chunks = ["text a", "text b", "text c"]
        store.add_documents(chunks, [{}, {}, {}])
        assert mock_embedder.embed.call_args[0][0] == chunks

    def test_embedder_failure_propagates(self, store, mock_embedder, mock_collection):
        mock_embedder.embed.side_effect = RuntimeError("embed failed")
        with pytest.raises(RuntimeError, match="embed failed"):
            store.add_documents(["c1"], [{}])
        mock_collection.add.assert_not_called()


# ============================================================
# TestSearch
# ============================================================


class TestSearch:
    """测试 search() — 语义检索。"""

    def test_happy_path(self, store, mock_embedder, mock_collection):
        results = store.search("test query", top_k=3)
        mock_embedder.embed_query.assert_called_once_with("test query")
        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["query_embeddings"] == [[0.5, 0.6]]
        assert call_kwargs["n_results"] == 3
        assert call_kwargs["where"] is None
        assert len(results) == 2

    def test_returns_search_result_objects(self, store):
        results = store.search("query")
        for r in results:
            assert isinstance(r, SearchResult)
        assert results[0].content == "doc text 1"
        assert results[0].metadata == {"source": "test1"}
        assert results[0].source_id == "id1"

    def test_score_calculation(self, store):
        results = store.search("query")
        assert results[0].score == pytest.approx(0.85)
        assert results[1].score == pytest.approx(0.65)

    def test_top_k_capped_by_count(self, store, mock_collection):
        mock_collection.count.return_value = 2
        store.search("query", top_k=10)
        assert mock_collection.query.call_args[1]["n_results"] == 2

    def test_with_where_filter(self, store, mock_collection):
        store.search("query", where={"source": "pdf"})
        assert mock_collection.query.call_args[1]["where"] == {"source": "pdf"}

    def test_empty_collection_returns_empty(self, store):
        store._collection.count.return_value = 0
        store._collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        results = store.search("query")
        assert results == []

    def test_missing_documents_uses_empty_string(self, store):
        store._collection.count.return_value = 2
        store._collection.query.return_value = {
            "ids": [["id1"]],
            "metadatas": [[{"k": "v"}]],
            "distances": [[0.1]],
        }
        results = store.search("query")
        assert results[0].content == ""


# ============================================================
# TestDeleteCollection
# ============================================================


class TestDeleteCollection:
    """测试 delete_collection() — 删除并重建集合。"""

    def test_calls_client_delete(self, store):
        store.delete_collection()
        store._client.delete_collection.assert_called_once_with("course_content")

    def test_recreates_collection(self, store):
        store.delete_collection()
        store._client.get_or_create_collection.assert_called_with(
            name="course_content",
            metadata={"hnsw:space": "cosine"},
        )

    def test_new_collection_stored(self, store):
        old_collection = store._collection
        new_mock = MagicMock()
        store._client.get_or_create_collection.return_value = new_mock
        store.delete_collection()
        assert store._collection is new_mock
        assert store._collection is not old_collection


# ============================================================
# TestCount
# ============================================================


class TestCount:
    """测试 count() — 文档计数。"""

    def test_delegates_to_collection(self, store, mock_collection):
        mock_collection.count.return_value = 42
        assert store.count() == 42

    def test_returns_zero_for_empty(self, store, mock_collection):
        mock_collection.count.return_value = 0
        assert store.count() == 0


# ============================================================
# TestUpdateDocuments
# ============================================================


class TestUpdateDocuments:
    """测试 update_documents() — 更新已有文档。"""

    def test_happy_path(self, store, mock_embedder, mock_collection):
        store.update_documents(
            ["id1", "id2"],
            ["new text 1", "new text 2"],
            [{"k": "v1"}, {"k": "v2"}],
        )
        mock_embedder.embed.assert_called_once_with(["new text 1", "new text 2"])
        call_kwargs = mock_collection.update.call_args[1]
        assert call_kwargs["ids"] == ["id1", "id2"]
        assert call_kwargs["documents"] == ["new text 1", "new text 2"]
        assert call_kwargs["metadatas"] == [{"k": "v1"}, {"k": "v2"}]

    def test_empty_ids_returns_early(self, store, mock_embedder, mock_collection):
        store.update_documents([], [], [])
        mock_embedder.embed.assert_not_called()
        mock_collection.update.assert_not_called()

    def test_length_mismatch_ids_vs_texts(self, store):
        with pytest.raises(VectorStoreError, match="长度不一致"):
            store.update_documents(["id1"], ["t1", "t2"], [{"k": "v"}, {"k": "v"}])

    def test_length_mismatch_ids_vs_metadatas(self, store):
        with pytest.raises(VectorStoreError, match="长度不一致"):
            store.update_documents(["id1", "id2"], ["t1", "t2"], [{"k": "v"}])

    def test_embedder_failure_propagates(self, store, mock_embedder, mock_collection):
        mock_embedder.embed.side_effect = RuntimeError("embed fail")
        with pytest.raises(RuntimeError, match="embed fail"):
            store.update_documents(["id1"], ["new text"], [{"k": "v"}])
        mock_collection.update.assert_not_called()

    def test_multiple_documents(self, store, mock_embedder, mock_collection):
        ids = ["id_a", "id_b", "id_c"]
        texts = ["text a", "text b", "text c"]
        metas = [{"i": 1}, {"i": 2}, {"i": 3}]
        store.update_documents(ids, texts, metas)
        mock_embedder.embed.assert_called_once_with(texts)
        call_kwargs = mock_collection.update.call_args[1]
        assert len(call_kwargs["ids"]) == 3
        assert len(call_kwargs["documents"]) == 3
        assert len(call_kwargs["metadatas"]) == 3


# ============================================================
# TestDeleteById
# ============================================================


class TestDeleteById:
    """测试 delete_by_id() — 按 ID 删除文档。"""

    def test_happy_path(self, store, mock_collection):
        store.delete_by_id(["id1", "id2"])
        mock_collection.delete.assert_called_once_with(ids=["id1", "id2"])

    def test_empty_list_returns_early(self, store, mock_collection):
        store.delete_by_id([])
        mock_collection.delete.assert_not_called()

    def test_collection_error_propagates(self, store, mock_collection):
        mock_collection.delete.side_effect = RuntimeError("delete failed")
        with pytest.raises(RuntimeError, match="delete failed"):
            store.delete_by_id(["id1"])
