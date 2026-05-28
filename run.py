"""Lecture Assistant 主入口"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="课堂助手 - Lecture Assistant",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.config import get_config  # noqa: E402
from src.course_manager import CourseManager  # noqa: E402
from src.i18n import t  # noqa: E402
from src.ui.session_state import get_state, init_session_state, set_state  # noqa: E402
from src.ui.theme import inject_theme_css  # noqa: E402

# ---- 初始化 ----
init_session_state()
inject_theme_css()

try:
    config = get_config()
    set_state("app_config", config)
except Exception as e:
    st.error(t("app.config_load_error", error=str(e)))
    st.info(t("app.config_load_hint"))
    st.stop()

cm = get_state("course_manager")
if cm is None:
    cm = CourseManager(config.project.data_dir)
    set_state("course_manager", cm)

# ---- 侧边栏 ----
from src.ui.sidebar import render_sidebar  # noqa: E402

render_sidebar()

# ---- 首页 ----
st.title(t("app.heading"))
st.caption(t("app.subtitle"))

st.divider()

current_course = get_state("current_course", "")
courses = cm.list_courses()

if not courses:
    st.info(t("app.welcome"))
    st.stop()

# 课程概览
st.subheader(t("app.my_courses"))

course_cols = st.columns(min(len(courses), 4))
for i, c_name in enumerate(courses):
    with course_cols[i % 4]:
        is_current = c_name == current_course
        stats = cm.get_review_stats(c_name)
        status_text = (
            t("status.ready") if stats["vector_store_ready"] else t("status.not_built")
        )
        marker = "> " if is_current else ""
        card_text = t(
            "app.course_card",
            marker=marker,
            name=c_name,
            audio=stats["audio_files"],
            courseware=stats["courseware_files"],
            count=stats["review_materials"],
            status=status_text,
        )
        st.markdown(card_text)

        if is_current:
            col_a, col_b = st.columns(2)
            col_a.page_link("pages/1_资料录入.py", label=t("nav.input"))
            col_b.page_link("pages/2_复习与问答.py", label=t("nav.workspace"))
        else:
            if st.button(t("app.enter_course"), key=f"enter_{c_name}", use_container_width=True):
                set_state("current_course", c_name)
                from src.ui.session_state import reset_course_state

                reset_course_state()
                from src.ui.sidebar import _load_course_data

                _load_course_data(cm, c_name)
                st.rerun()

st.divider()

with st.expander(t("app.about")):
    st.markdown(f"""
    | {t("app.about.component")} | {t("app.about.tech")} |
    |------|------|
    | {t("app.about.asr_engine")} | FunASR SenseVoiceSmall |
    | {t("app.about.doc_parser")} | MinerU magic-pdf |
    | {t("app.about.llm")} | DeepSeek API |
    | {t("app.about.vector_store")} | ChromaDB |
    | {t("app.about.embed_model")} | BAAI/bge-small-zh-v1.5 |
    | {t("app.about.data_dir")} | {config.project.data_dir}/courses/ |
    | {t("app.about.model_cache")} | {t("app.about.portable")} |
    """)
