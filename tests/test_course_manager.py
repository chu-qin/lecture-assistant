"""测试 CourseManager — 多课程隔离、状态持久化、复习资料管理。"""

import json
import time
from pathlib import Path

import pytest

from src.course_manager import CourseManager, CourseState, ReviewMaterialMeta

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def cm(tmp_path) -> CourseManager:
    """返回指向临时目录的 CourseManager。"""
    return CourseManager(str(tmp_path))


@pytest.fixture
def course(cm) -> str:
    """创建并返回一个测试课程名。"""
    return cm.create_course("测试课程")


# ============================================================
# TestListCourses
# ============================================================


class TestListCourses:
    """测试 list_courses() — 课程列表查询。"""

    def test_empty_when_no_courses(self, cm):
        assert cm.list_courses() == []

    def test_returns_created_courses_in_order(self, cm):
        cm.create_course("课程A")
        cm.create_course("课程B")
        assert cm.list_courses() == ["课程A", "课程B"]

    def test_corrupt_index_returns_empty(self, cm):
        index_path = cm._index_path
        index_path.write_text("not valid json{{{", encoding="utf-8")
        assert cm.list_courses() == []


# ============================================================
# TestCreateCourse
# ============================================================


class TestCreateCourse:
    """测试 create_course() — 课程创建。"""

    def test_creates_directories_and_state(self, cm):
        name = cm.create_course("新课程")
        course_dir = cm.course_dir(name)
        for sub in CourseManager.SUBDIRS:
            assert (course_dir / sub).is_dir()
        state_path = course_dir / "state.json"
        assert state_path.exists()
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        assert "last_modified" in state_data
        assert state_data["vector_store_ready"] is False

    def test_empty_name_raises_value_error(self, cm):
        with pytest.raises(ValueError):
            cm.create_course("")

    def test_whitespace_only_raises(self, cm):
        with pytest.raises(ValueError):
            cm.create_course("   ")

    def test_duplicate_returns_existing_idempotent(self, cm):
        first = cm.create_course("重复课程")
        second = cm.create_course("重复课程")
        assert first == second == "重复课程"
        assert cm.list_courses() == ["重复课程"]

    def test_chinese_name_works(self, cm):
        name = cm.create_course("机器学习")
        assert name == "机器学习"
        assert cm.course_dir("机器学习").exists()

    def test_index_updated(self, cm):
        cm.create_course("索引测试")
        index = cm._load_index()
        assert "索引测试" in index["courses"]
        assert "索引测试" in index["created_at"]

    def test_returns_course_name(self, cm):
        result = cm.create_course("返回值测试")
        assert result == "返回值测试"

    def test_persistence_across_instances(self, cm, tmp_path):
        cm.create_course("跨实例测试")
        cm2 = CourseManager(str(tmp_path))
        assert "跨实例测试" in cm2.list_courses()


# ============================================================
# TestDeleteCourse
# ============================================================


class TestDeleteCourse:
    """测试 delete_course() — 课程删除。"""

    def test_deletes_directory_and_cleans_index(self, cm, course):
        course_dir = cm.course_dir(course)
        assert course_dir.exists()
        cm.delete_course(course)
        assert not course_dir.exists()
        assert course not in cm.list_courses()

    def test_nonexistent_course_no_error(self, cm):
        cm.delete_course("不存在的课程")

    def test_cleans_created_at_entry(self, cm, course):
        cm.delete_course(course)
        index = cm._load_index()
        assert course not in index.get("created_at", {})

    def test_recreatable_after_delete(self, cm, course):
        cm.delete_course(course)
        new_name = cm.create_course(course)
        assert new_name == course
        assert cm.list_courses() == [course]


# ============================================================
# TestStatePersistence
# ============================================================


class TestStatePersistence:
    """测试 load_state / save_state — 课程状态持久化。"""

    def test_load_returns_defaults_when_no_file(self, cm):
        state = cm.load_state("nosuch")
        assert state.transcript_text is None
        assert state.transcript_meta is None
        assert state.parsed_doc_paths == []
        assert state.merged_content_path is None
        assert state.review_material_path is None
        assert state.vector_store_ready is False
        assert state.last_modified == ""

    def test_save_and_load_roundtrip(self, cm, course):
        state = CourseState(transcript_text="hello world")
        cm.save_state(course, state)
        loaded = cm.load_state(course)
        assert loaded.transcript_text == "hello world"

    def test_load_corrupt_json_returns_defaults(self, cm, course):
        state_path = cm.course_dir(course) / "state.json"
        state_path.write_text("corrupt{{{", encoding="utf-8")
        loaded = cm.load_state(course)
        assert loaded.transcript_text is None

    def test_save_updates_last_modified(self, cm, course):
        state = CourseState()
        cm.save_state(course, state)
        first_ts = cm.load_state(course).last_modified
        assert first_ts != ""
        time.sleep(0.01)
        cm.save_state(course, state)
        second_ts = cm.load_state(course).last_modified
        assert second_ts != first_ts

    def test_roundtrip_all_fields(self, cm, course):
        state = CourseState(
            transcript_text="转录文本",
            transcript_meta={"duration": 3600},
            parsed_doc_paths=["/path/doc1", "/path/doc2"],
            merged_content_path="/path/merged.md",
            review_material_path="/path/review.md",
            vector_store_ready=True,
        )
        cm.save_state(course, state)
        loaded = cm.load_state(course)
        assert loaded.transcript_text == "转录文本"
        assert loaded.transcript_meta == {"duration": 3600}
        assert loaded.parsed_doc_paths == ["/path/doc1", "/path/doc2"]
        assert loaded.merged_content_path == "/path/merged.md"
        assert loaded.review_material_path == "/path/review.md"
        assert loaded.vector_store_ready is True


# ============================================================
# TestChatHistory
# ============================================================


class TestChatHistory:
    """测试 load_chat_history / save_chat_history — 聊天历史。"""

    def test_load_empty_when_no_file(self, cm, course):
        assert cm.load_chat_history(course) == []

    def test_save_and_load_roundtrip(self, cm, course):
        history = [
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
            {"role": "user", "content": "问题2"},
        ]
        cm.save_chat_history(course, history)
        loaded = cm.load_chat_history(course)
        assert loaded == history

    def test_load_corrupt_json_returns_empty(self, cm, course):
        chat_path = cm.course_dir(course) / "chat_history.json"
        chat_path.write_text("bad json {{{", encoding="utf-8")
        assert cm.load_chat_history(course) == []

    def test_save_overwrites(self, cm, course):
        cm.save_chat_history(course, [{"old": True}])
        cm.save_chat_history(course, [{"new": True}])
        loaded = cm.load_chat_history(course)
        assert loaded == [{"new": True}]


# ============================================================
# TestReviewMaterialSave
# ============================================================


class TestReviewMaterialSave:
    """测试 save_review_material() — 复习资料保存。"""

    def test_returns_path_and_writes_file(self, cm, course):
        content = "# 复习提纲\n\n重要知识点。"
        path = cm.save_review_material(course, "复习提纲", content)
        assert isinstance(path, Path)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == content

    def test_saves_to_review_materials_subdir(self, cm, course):
        path = cm.save_review_material(course, "笔记", "内容")
        review_dir = cm.sub_dir(course, "review_materials")
        assert review_dir in path.parents

    def test_filename_pattern(self, cm, course):
        path = cm.save_review_material(course, "复习提纲", "内容")
        import re

        assert re.match(r"review_复习提纲_\d{8}_\d{6}\.md", path.name)

    def test_custom_display_name(self, cm, course):
        cm.save_review_material(course, "笔记", "内容", display_name="自定义名称")
        materials = cm.list_review_materials(course)
        assert materials[0].display_name == "自定义名称"

    def test_default_display_name_equals_type(self, cm, course):
        cm.save_review_material(course, "详细笔记", "内容")
        materials = cm.list_review_materials(course)
        assert materials[0].display_name == "详细笔记"

    def test_special_chars_stripped_from_filename(self, cm, course):
        path = cm.save_review_material(course, "知识/点&总结", "内容")
        import re

        assert not re.search(r"[/&]", path.name)
        materials = cm.list_review_materials(course)
        assert materials[0].material_type == "知识/点&总结"

    def test_char_and_word_count(self, cm, course):
        content = "hello  world\n测试"
        cm.save_review_material(course, "测试", content)
        materials = cm.list_review_materials(course)
        assert materials[0].char_count == len(content)
        assert materials[0].word_count == len("helloworld测试")


# ============================================================
# TestReviewMaterialList
# ============================================================


class TestReviewMaterialList:
    """测试 list_review_materials() — 复习资料列表。"""

    def test_empty_when_no_materials(self, cm, course):
        assert cm.list_review_materials(course) == []

    def test_sorted_by_created_at_desc(self, cm, course):
        cm.save_review_material(course, "第一种", "内容A")
        time.sleep(0.02)
        cm.save_review_material(course, "第二种", "内容B")
        materials = cm.list_review_materials(course)
        assert len(materials) == 2
        assert materials[0].created_at > materials[1].created_at

    def test_corrupt_entry_skipped(self, cm, course):
        cm.save_review_material(course, "有效", "内容")
        index_path = cm._review_index_path(course)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index.append({"bad": "entry"})
        index_path.write_text(json.dumps(index), encoding="utf-8")
        materials = cm.list_review_materials(course)
        assert len(materials) == 1

    def test_auto_cleans_stale_entries(self, cm, course):
        path = cm.save_review_material(course, "笔记", "内容")
        path.unlink()
        materials = cm.list_review_materials(course)
        assert len(materials) == 0


# ============================================================
# TestReviewMaterialCRUD
# ============================================================


class TestReviewMaterialCRUD:
    """测试 load / delete review material — 复习资料读写删。"""

    def test_load_returns_content(self, cm, course):
        content = "## 加载测试\n正文内容。"
        path = cm.save_review_material(course, "测试类型", content)
        loaded = cm.load_review_material(course, path.name)
        assert loaded == content

    def test_load_nonexistent_returns_none(self, cm, course):
        assert cm.load_review_material(course, "nonexistent.md") is None

    def test_delete_returns_true_and_cleans(self, cm, course):
        path = cm.save_review_material(course, "待删除", "内容")
        result = cm.delete_review_material(course, path.name)
        assert result is True
        assert not path.exists()
        assert cm.list_review_materials(course) == []

    def test_delete_nonexistent_returns_false(self, cm, course):
        result = cm.delete_review_material(course, "ghost.md")
        assert result is False

    def test_delete_only_removes_target(self, cm, course):
        path1 = cm.save_review_material(course, "保留", "内容1")
        path2 = cm.save_review_material(course, "删除", "内容2")
        cm.delete_review_material(course, path2.name)
        assert path1.exists()
        assert not path2.exists()
        materials = cm.list_review_materials(course)
        assert len(materials) == 1
        assert materials[0].filename == path1.name


# ============================================================
# TestGetReviewStats
# ============================================================


class TestGetReviewStats:
    """测试 get_review_stats() — 课程资料统计。"""

    def test_returns_all_keys(self, cm, course):
        stats = cm.get_review_stats(course)
        assert "audio_files" in stats
        assert "courseware_files" in stats
        assert "transcripts" in stats
        assert "review_materials" in stats
        assert "vector_store_ready" in stats

    def test_counts_files_correctly(self, cm, course):
        audio_dir = cm.sub_dir(course, "audio")
        (audio_dir / "recording.wav").write_text("")
        (audio_dir / "recording2.mp3").write_text("")

        courseware_dir = cm.sub_dir(course, "courseware")
        (courseware_dir / "slides.pptx").write_text("")

        transcripts_dir = cm.sub_dir(course, "transcripts")
        (transcripts_dir / "lecture1.txt").write_text("transcript")
        (transcripts_dir / "notes.md").touch()

        cm.save_review_material(course, "笔记", "内容A")
        cm.save_review_material(course, "提纲", "内容B")
        cm.save_review_material(course, "题库", "内容C")

        state = CourseState(vector_store_ready=True)
        cm.save_state(course, state)

        stats = cm.get_review_stats(course)
        assert stats["audio_files"] == 2
        assert stats["courseware_files"] == 1
        assert stats["transcripts"] == 1
        assert stats["review_materials"] == 3
        assert stats["vector_store_ready"] is True

    def test_empty_course_all_zeroes(self, cm, course):
        stats = cm.get_review_stats(course)
        assert stats["audio_files"] == 0
        assert stats["courseware_files"] == 0
        assert stats["transcripts"] == 0
        assert stats["review_materials"] == 0
        assert stats["vector_store_ready"] is False


# ============================================================
# TestPathHelpers
# ============================================================


class TestPathHelpers:
    """测试 course_dir / sub_dir / chroma_dir / sanitize_collection_name。"""

    def test_course_dir_creates_and_exists(self, cm):
        path = cm.course_dir("某课程")
        assert isinstance(path, Path)
        assert path.exists()

    def test_sub_dir_creates_nested(self, cm):
        path = cm.sub_dir("某课程", "audio")
        assert path.exists()
        assert path.name == "audio"

    def test_chroma_dir_returns_correct_path(self, cm):
        path = cm.chroma_dir("某课程")
        assert path.name == "chroma_db"
        assert path.exists()

    def test_sanitize_ascii_valid(self):
        result = CourseManager.sanitize_collection_name("MyCourse")
        assert result == "course_MyCourse"

    def test_sanitize_chinese_uses_hash(self):
        result = CourseManager.sanitize_collection_name("机器学习")
        assert result.startswith("c_")
        assert len(result) == 2 + 12

    def test_sanitize_space_uses_hash(self):
        result = CourseManager.sanitize_collection_name("my course")
        assert result.startswith("c_")

    def test_sanitize_short_name_uses_hash(self):
        result = CourseManager.sanitize_collection_name("ab")
        assert result.startswith("c_")

    def test_sanitize_special_chars_uses_hash(self):
        result = CourseManager.sanitize_collection_name("a/b:c")
        assert result.startswith("c_")


# ============================================================
# TestSafeName
# ============================================================


class TestSafeName:
    """测试 _safe_name — 课程名安全过滤。"""

    def test_preserves_allowed_chars(self):
        result = CourseManager._safe_name("abc_123-测试.(ok) （中文）")
        assert result == "abc_123-测试.(ok) （中文）"

    def test_filters_path_separators(self):
        result = CourseManager._safe_name("a/b\\c:d*e?f\"g<h>i|j")
        assert "/" not in result
        assert "\\" not in result
        assert ":" not in result
        assert "*" not in result
        assert "?" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result


# ============================================================
# TestDataClasses
# ============================================================


class TestDataClasses:
    """测试 CourseState / ReviewMaterialMeta 数据类默认值。"""

    def test_course_state_defaults(self):
        cs = CourseState()
        assert cs.transcript_text is None
        assert cs.transcript_meta is None
        assert cs.parsed_doc_paths == []
        assert cs.merged_content_path is None
        assert cs.review_material_path is None
        assert cs.vector_store_ready is False
        assert cs.last_modified == ""

    def test_review_material_meta_defaults(self):
        meta = ReviewMaterialMeta(
            filename="test.md",
            material_type="复习提纲",
            display_name="显示名",
            created_at="2025-01-01T00:00:00",
            char_count=100,
            word_count=80,
        )
        assert meta.filename == "test.md"
        assert meta.material_type == "复习提纲"
        assert meta.display_name == "显示名"
        assert meta.created_at == "2025-01-01T00:00:00"
        assert meta.char_count == 100
        assert meta.word_count == 80
        assert meta.is_active is True
