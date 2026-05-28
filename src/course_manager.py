"""课程管理器：多课程隔离、状态持久化、历史记录。"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CourseState:
    """一门课程的完整持久化状态。"""

    transcript_text: str | None = None
    transcript_meta: dict | None = None
    parsed_doc_paths: list[str] = field(default_factory=list)
    merged_content_path: str | None = None
    review_material_path: str | None = None
    vector_store_ready: bool = False
    last_modified: str = ""


@dataclass
class ReviewMaterialMeta:
    """一份复习资料的元信息。"""

    filename: str
    material_type: str
    display_name: str
    created_at: str
    char_count: int
    word_count: int
    is_active: bool = True


class CourseManager:
    """管理多门课程的数据隔离和持久化。

    目录结构:
        data/courses/{course_name}/
            ├── audio/
            ├── courseware/
            ├── transcripts/
            ├── parsed_docs/
            ├── merged/
            ├── review_materials/
            ├── chroma_db/
            ├── chat_history.json
            └── state.json
    """

    INDEX_FILE = "course_index.json"
    STATE_FILE = "state.json"
    CHAT_FILE = "chat_history.json"

    SUBDIRS = [
        "audio",
        "courseware",
        "transcripts",
        "parsed_docs",
        "merged",
        "review_materials",
        "chroma_db",
    ]

    def __init__(self, data_root: str):
        self._root = Path(data_root)
        self._courses_dir = self._root / "courses"
        self._courses_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._courses_dir / self.INDEX_FILE

    # ---- course index ----

    def list_courses(self) -> list[str]:
        """获取所有课程名称列表（按创建时间排序）。"""
        index = self._load_index()
        return index.get("courses", [])

    def create_course(self, name: str) -> str:
        """创建新课程，返回课程名。"""
        name = name.strip()
        if not name:
            raise ValueError("课程名不能为空")
        index = self._load_index()
        if name in index.get("courses", []):
            logger.info("课程 '%s' 已存在", name)
            return name
        index.setdefault("courses", []).append(name)
        index.setdefault("created_at", {})[name] = datetime.now().isoformat()
        self._save_index(index)

        course_dir = self._course_dir(name)
        for sub in self.SUBDIRS:
            (course_dir / sub).mkdir(parents=True, exist_ok=True)

        self.save_state(name, CourseState(last_modified=datetime.now().isoformat()))
        logger.info("课程创建完成: %s", name)
        return name

    def delete_course(self, name: str) -> None:
        """删除课程及其所有数据。"""
        import shutil

        course_dir = self._course_dir(name)
        if course_dir.exists():
            shutil.rmtree(course_dir)
        index = self._load_index()
        if name in index.get("courses", []):
            index["courses"].remove(name)
        if name in index.get("created_at", {}):
            del index["created_at"][name]
        self._save_index(index)
        logger.info("课程已删除: %s", name)

    # ---- state persistence ----

    def load_state(self, course_name: str) -> CourseState:
        """加载课程状态。"""
        path = self._course_dir(course_name) / self.STATE_FILE
        if not path.exists():
            return CourseState()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return CourseState(**data)
        except Exception:
            logger.warning("加载课程状态失败: %s", path, exc_info=True)
            return CourseState()

    def save_state(self, course_name: str, state: CourseState) -> None:
        """保存课程状态。"""
        state.last_modified = datetime.now().isoformat()
        path = self._course_dir(course_name) / self.STATE_FILE
        path.write_text(
            json.dumps(state.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- chat history ----

    def load_chat_history(self, course_name: str) -> list[dict]:
        """加载聊天历史。"""
        path = self._course_dir(course_name) / self.CHAT_FILE
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("加载聊天历史失败: %s", path, exc_info=True)
            return []

    def save_chat_history(self, course_name: str, history: list[dict]) -> None:
        """保存聊天历史。"""
        path = self._course_dir(course_name) / self.CHAT_FILE
        path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- review materials ----

    REVIEW_INDEX_FILE = "_index.json"

    def save_review_material(
        self, course_name: str, material_type: str, content: str, display_name: str | None = None
    ) -> Path:
        """保存一份复习资料，返回文件路径。"""
        import re

        review_dir = self.sub_dir(course_name, "review_materials")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_type = re.sub(r"[^a-zA-Z0-9一-鿿]", "", material_type)
        filename = f"review_{safe_type}_{ts}.md"
        file_path = review_dir / filename
        file_path.write_text(content, encoding="utf-8")

        char_count = len(content)
        word_count = len(re.sub(r"\s+", "", content))

        meta = ReviewMaterialMeta(
            filename=filename,
            material_type=material_type,
            display_name=display_name or material_type,
            created_at=datetime.now().isoformat(),
            char_count=char_count,
            word_count=word_count,
        )
        self._add_to_review_index(course_name, meta)
        logger.info("复习资料已保存: %s/%s", course_name, filename)
        return file_path

    def list_review_materials(self, course_name: str) -> list[ReviewMaterialMeta]:
        """列出课程下所有已保存的复习资料。"""
        index = self._load_review_index(course_name)
        result = []
        for item in index:
            try:
                result.append(ReviewMaterialMeta(**item))
            except Exception:
                logger.warning("加载复习资料元数据失败: %s", item, exc_info=True)
        # 对已在索引中被标记但文件被手动删除的做一次清理
        review_dir = self.sub_dir(course_name, "review_materials")
        existing_files = {p.name for p in review_dir.glob("review_*.md")}
        filtered = [m for m in result if m.filename in existing_files]
        if len(filtered) != len(result):
            self._save_review_index(course_name, [m.__dict__ for m in filtered])
        return sorted(filtered, key=lambda m: m.created_at, reverse=True)

    def load_review_material(self, course_name: str, filename: str) -> str | None:
        """加载指定复习资料的内容。"""
        file_path = self.sub_dir(course_name, "review_materials") / filename
        if not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    def delete_review_material(self, course_name: str, filename: str) -> bool:
        """删除一份复习资料（文件 + 索引条目）。"""
        file_path = self.sub_dir(course_name, "review_materials") / filename
        deleted = False
        if file_path.exists():
            file_path.unlink()
            deleted = True
        index = self._load_review_index(course_name)
        index = [item for item in index if item.get("filename") != filename]
        self._save_review_index(course_name, index)
        return deleted

    def get_review_stats(self, course_name: str) -> dict:
        """课程资料完成统计。"""

        audio_dir = self.sub_dir(course_name, "audio")
        courseware_dir = self.sub_dir(course_name, "courseware")
        transcripts_dir = self.sub_dir(course_name, "transcripts")
        review_dir = self.sub_dir(course_name, "review_materials")

        audio_count = len(list(audio_dir.glob("*")))
        courseware_count = len(list(courseware_dir.glob("*")))
        transcript_count = len(list(transcripts_dir.glob("*.txt")))
        review_count = len(list(review_dir.glob("review_*.md")))

        state = self.load_state(course_name)

        return {
            "audio_files": audio_count,
            "courseware_files": courseware_count,
            "transcripts": transcript_count,
            "review_materials": review_count,
            "vector_store_ready": state.vector_store_ready,
        }

    # ---- internal: review index ----

    def _review_index_path(self, course_name: str) -> Path:
        return self.sub_dir(course_name, "review_materials") / self.REVIEW_INDEX_FILE

    def _load_review_index(self, course_name: str) -> list[dict]:
        path = self._review_index_path(course_name)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("加载复习资料索引失败: %s", path, exc_info=True)
            return []

    def _save_review_index(self, course_name: str, index: list[dict]) -> None:
        path = self._review_index_path(course_name)
        path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _add_to_review_index(self, course_name: str, meta: ReviewMaterialMeta) -> None:
        index = self._load_review_index(course_name)
        index.append(meta.__dict__)
        self._save_review_index(course_name, index)

    # ---- paths ----

    def course_dir(self, course_name: str) -> Path:
        """课程根目录。"""
        d = self._course_dir(course_name)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def sub_dir(self, course_name: str, sub: str) -> Path:
        """课程子目录（audio, transcripts 等）。"""
        d = self._course_dir(course_name) / sub
        d.mkdir(parents=True, exist_ok=True)
        return d

    def chroma_dir(self, course_name: str) -> Path:
        """课程 ChromaDB 目录。"""
        return self.sub_dir(course_name, "chroma_db")

    @staticmethod
    def sanitize_collection_name(name: str) -> str:
        """将中文课程名转为 ChromaDB 兼容的 ASCII 名（拼音或哈希）。"""

        # 如果已经是纯 ASCII 且符合规则，直接使用
        if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,}$", name):
            return f"course_{name}"
        # 否则用哈希值
        safe = "c_" + hashlib.md5(name.encode()).hexdigest()[:12]
        return safe

    # ---- internal helpers ----

    def _course_dir(self, name: str) -> Path:
        safe = self._safe_name(name)
        return self._courses_dir / safe

    @staticmethod
    def _safe_name(name: str) -> str:
        return "".join(c for c in name if c.isalnum() or c in "._- ()（）")

    def _load_index(self) -> dict[str, Any]:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("加载课程索引失败: %s", self._index_path, exc_info=True)
        return {"courses": [], "created_at": {}}

    def _save_index(self, index: dict) -> None:
        self._index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
