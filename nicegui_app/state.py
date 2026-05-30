"""NiceGUI 状态管理 — 替代 Streamlit st.session_state。

分层存储策略：
- app.storage.user: 轻量持久化键（current_course, language 等），JSON 序列化，跨页面/重启存活
- app.storage.tab: 重对象缓存（CourseManager, VectorStore 等），仅当前标签页内存
"""

from typing import Any

from nicegui import app

# ---- User 级持久化键（扁平存储，每个键独立 JSON 序列化）----

_USER_DEFAULTS: dict[str, Any] = {
    "current_course": "",
    "language": "zh",
    "active_section": "workspace",
    "selected_material": None,
}


def _ensure_user_defaults() -> None:
    """确保所有用户键已初始化。"""
    for key, default in _USER_DEFAULTS.items():
        if key not in app.storage.user:
            app.storage.user[key] = default


def get_user(key: str, default: Any = None) -> Any:
    """读取用户持久化状态。"""
    _ensure_user_defaults()
    return app.storage.user.get(key, default)


def set_user(key: str, value: Any) -> None:
    """写入用户持久化状态。"""
    _ensure_user_defaults()
    app.storage.user[key] = value


# ---- Tab 级内存缓存（重对象）----


def get_tab_cache() -> dict:
    """获取标签页内存缓存。"""
    if "cache" not in app.storage.tab:
        app.storage.tab["cache"] = {}
    return app.storage.tab["cache"]


def get_cache(key: str, default: Any = None) -> Any:
    """从 tab 缓存读取。"""
    return get_tab_cache().get(key, default)


def set_cache(key: str, value: Any) -> None:
    """写入 tab 缓存。"""
    get_tab_cache()[key] = value


def reset_course_state() -> None:
    """切换课程时重置内存状态。"""
    cache = get_tab_cache()
    for key in (
        "asr_results",
        "asr_summary",
        "asr_corrected",
        "asr_corrected_confirmed",
        "parsed_results",
        "book_results",
        "review_material",
        "review_materials",
        "vector_store",
        "vector_store_ready",
        "chunker",
        "embedder",
        "chat_history",
    ):
        cache.pop(key, None)
    set_user("selected_material", None)
    set_user("active_section", "workspace")
