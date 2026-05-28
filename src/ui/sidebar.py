"""两级侧边栏：课程选择（L1）+ 课程板块导航（L2）。"""

import sys
from pathlib import Path

import streamlit as st

from src.i18n import t

from .session_state import get_state, reset_course_state, set_state
from .theme import inject_theme_css

# st.switch_page 路径相对于主脚本所在目录。当直接运行 pages/*.py
# 时主脚本就在 pages/ 内，不需要 pages/ 前缀。
_main_dir = Path(sys.argv[0]).resolve().parent
_PAGE_PREFIX = "" if _main_dir.name == "pages" else "pages/"


def _ensure_services() -> None:
    """确保 core services（config、course_manager）已初始化。"""
    cm = get_state("course_manager")
    if cm is not None:
        return

    config = get_state("app_config")
    if config is None:
        from src.config import get_config

        config = get_config()
        set_state("app_config", config)

    from src.course_manager import CourseManager

    cm = CourseManager(config.project.data_dir)
    set_state("course_manager", cm)


def render_sidebar() -> None:
    """渲染两级菜单侧边栏。"""

    with st.sidebar:
        inject_theme_css()
        _ensure_services()
        cm = get_state("course_manager")
        current = get_state("current_course", "")

        # ============================================================
        # L1: 课程列表
        # ============================================================
        st.markdown(f"#### {t('sidebar.course_list')}")

        courses = cm.list_courses() if cm else []

        if courses:
            for course in courses:
                is_current = course == current

                if is_current:
                    _render_current_course(cm, course)
                else:
                    label = f"{course}"
                    if st.button(
                        label,
                        key=f"course_btn_{course}",
                        use_container_width=True,
                        type="secondary",
                    ):
                        set_state("current_course", course)
                        reset_course_state()
                        _load_course_data(cm, course)
                        st.rerun()
        else:
            st.caption(t("sidebar.no_courses"))

        st.divider()

        # ============================================================
        # 新建课程
        # ============================================================
        new_course_label = f"+ {t('sidebar.new_course')}"
        with st.expander(new_course_label, expanded=not courses):
            with st.form("create_course_form", clear_on_submit=True):
                new_name = st.text_input(
                    t("sidebar.course_name"),
                    placeholder=t("sidebar.course_name_placeholder"),
                    key="new_course_input",
                    label_visibility="collapsed",
                )
                if st.form_submit_button(
                    t("sidebar.create_course"), type="primary", use_container_width=True
                ):
                    if new_name.strip():
                        created = cm.create_course(new_name.strip())
                        set_state("current_course", created)
                        reset_course_state()
                        st.rerun()

            if courses:
                delete_target = st.selectbox(
                    t("sidebar.delete_course"),
                    [""] + courses,
                    key="delete_course_selector",
                    label_visibility="collapsed",
                    placeholder=t("sidebar.delete_course_placeholder"),
                )
                if delete_target and st.button(
                    t("sidebar.confirm_delete"), use_container_width=True
                ):
                    cm.delete_course(delete_target)
                    if current == delete_target:
                        set_state("current_course", "")
                        reset_course_state()
                    st.rerun()

        if not current or not cm:
            return

        # ============================================================
        # 课程状态
        # ============================================================
        st.markdown(f"#### {t('sidebar.course_status')}")
        stats = cm.get_review_stats(current)
        st.caption(
            t(
                "sidebar.stats_line1",
                audio=stats["audio_files"],
                courseware=stats["courseware_files"],
                transcripts=stats["transcripts"],
            )
        )
        status_text = (
            t("status.ready") if stats["vector_store_ready"] else t("status.not_built")
        )
        st.caption(
            t("sidebar.stats_line2", count=stats["review_materials"], status=status_text)
        )


def _render_current_course(cm, course: str) -> None:
    """渲染当前课程的展开二级菜单。"""
    expander_label = t("sidebar.current_course_label", course=course)
    with st.expander(expander_label, expanded=True):
        # L2: 板块导航
        active = get_state("active_section", "workspace")

        col_input, col_workspace = st.columns(2)
        with col_input:
            if st.button(
                t("nav.input"),
                key="nav_input",
                use_container_width=True,
                type="primary" if active == "input" else "secondary",
            ):
                set_state("active_section", "input")
                st.switch_page(f"{_PAGE_PREFIX}1_资料录入.py")
        with col_workspace:
            if st.button(
                t("nav.workspace"),
                key="nav_workspace",
                use_container_width=True,
                type="primary" if active == "workspace" else "secondary",
            ):
                set_state("active_section", "workspace")
                st.switch_page(f"{_PAGE_PREFIX}2_复习与问答.py")

        st.markdown(
            f'<p style="color:#B0AEA6;font-size:0.8rem;margin:0.5rem 0 0.25rem 0;">'
            f"{t('sidebar.saved_materials')}</p>",
            unsafe_allow_html=True,
        )

        # 从磁盘加载已保存资料列表
        materials = cm.list_review_materials(course)
        set_state("review_materials", [m.__dict__ for m in materials])

        if materials:
            for m in materials:
                type_short = _material_type_short(m.material_type)
                label = f"{m.display_name}  [{type_short}]"
                if st.button(
                    label,
                    key=f"mat_{course}_{m.filename}",
                    use_container_width=True,
                ):
                    set_state("selected_material", m.filename)
                    set_state("active_section", "workspace")
                    st.switch_page(f"{_PAGE_PREFIX}2_复习与问答.py")
        else:
            st.caption(f"  {t('sidebar.no_materials')}")


def _load_course_data(cm, course_name: str) -> None:
    """从持久化文件加载课程数据到 session_state。"""
    chat = cm.load_chat_history(course_name)
    set_state("chat_history", chat)
    set_state("vector_store_ready", cm.load_state(course_name).vector_store_ready)
    set_state("vector_store", None)
    # 预加载 review materials 列表
    materials = cm.list_review_materials(course_name)
    set_state("review_materials", [m.__dict__ for m in materials])


def _material_type_short(material_type: str) -> str:
    """将资料类型映射为缩写（已 i18n）。"""
    type_to_key = {
        "复习提纲": "material.review_outline_short",
        "详细笔记": "material.detailed_notes_short",
        "知识结构图": "material.knowledge_map_short",
        "自测题库": "material.quiz_bank_short",
    }
    key = type_to_key.get(material_type)
    if key:
        return t(key)
    return material_type[:4]
