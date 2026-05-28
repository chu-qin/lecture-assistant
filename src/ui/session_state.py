"""Streamlit session_state 管理工具。"""

from typing import Any

import streamlit as st


def init_session_state() -> None:
    """初始化所有 session_state 键（仅在首次调用时设置默认值）。"""
    defaults: dict[str, Any] = {
        "app_config": None,
        "course_manager": None,
        "current_course": "",
        "asr_results": [],  # 多文件转录结果列表
        "parsed_results": [],  # 课件解析结果列表
        "book_results": [],  # EPUB 书本导入结果列表
        "review_material": None,  # 当前会话生成的复习资料文本
        "review_materials": [],  # 从磁盘加载的资料元信息列表
        "selected_material": None,  # 侧边栏选中的资料文件名
        "active_section": "workspace",  # 当前课程板块: "input" | "workspace"
        "vector_store": None,
        "vector_store_ready": False,
        "chunker": None,
        "embedder": None,
        "chat_history": [],
        "qa_processing": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_state(key: str, default: Any = None) -> Any:
    """安全获取 session_state 值。"""
    return st.session_state.get(key, default)


def set_state(key: str, value: Any) -> None:
    """设置 session_state 值。"""
    st.session_state[key] = value


def reset_course_state() -> None:
    """切换课程时重置内存中的流水线状态（持久化数据保留在文件中）。"""
    st.session_state.asr_results = []
    st.session_state.parsed_results = []
    st.session_state.book_results = []
    st.session_state.review_material = None
    st.session_state.review_materials = []
    st.session_state.selected_material = None
    st.session_state.active_section = "workspace"
    st.session_state.vector_store = None
    st.session_state.vector_store_ready = False
    st.session_state.chunker = None
    st.session_state.embedder = None
    st.session_state.chat_history = []
