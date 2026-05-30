"""NiceGUI 侧边栏组件 — 课程列表 + 板块导航 + 语言切换。"""

from nicegui import ui

from src.course_manager import CourseManager
from src.i18n import get_available_languages, get_language, set_language, t

from ..state import get_cache, get_user, reset_course_state, set_cache, set_user


def _ensure_services() -> CourseManager | None:
    """确保 CourseManager 已初始化。"""
    cm = get_cache("course_manager")
    if cm is not None:
        return cm

    from src.config import get_config

    config = get_cache("app_config")
    if config is None:
        config = get_config()
        set_cache("app_config", config)

    cm = CourseManager(config.project.data_dir)
    set_cache("course_manager", cm)
    return cm


def render_sidebar() -> None:
    """在 ui.left_drawer 中渲染侧边栏。"""
    cm = _ensure_services()
    current = get_user("current_course", "")

    with ui.left_drawer(fixed=True, bordered=True).classes("p-2"):
        ui.label(t("sidebar.course_list")).classes("text-h6 q-mb-md")

        courses = cm.list_courses() if cm else []

        if courses:
            for course in courses:
                is_current = course == current
                color = "primary" if is_current else None
                ui.button(
                    course,
                    on_click=lambda _, c=course: _on_course_select(c),
                    color=color,
                ).props("flat align=left").classes("w-full")
        else:
            ui.label(t("sidebar.no_courses")).classes("text-caption")

        ui.separator()
        _render_course_form(cm, courses)

        if current and cm:
            _render_course_section(cm, current)


def _on_course_select(course: str) -> None:
    """切换课程。"""
    if get_user("current_course", "") == course:
        return
    set_user("current_course", course)
    reset_course_state()
    _load_course_data(course)
    ui.navigate.to(f"/review/{course}")


def _load_course_data(course_name: str) -> None:
    """从磁盘加载课程数据到 tab 缓存。"""
    cm = get_cache("course_manager")
    if not cm:
        return
    set_cache("chat_history", cm.load_chat_history(course_name))
    state = cm.load_state(course_name)
    set_cache("vector_store_ready", state.vector_store_ready)
    set_cache("vector_store", None)
    materials = cm.list_review_materials(course_name)
    set_cache("review_materials", [m.__dict__ for m in materials])


def _render_course_form(cm: CourseManager | None, courses: list[str]) -> None:
    """渲染新建/删除课程表单。"""
    new_name = ui.input(
        t("sidebar.course_name"), placeholder=t("sidebar.course_name_placeholder")
    ).classes("w-full")

    def create_course():
        if cm and new_name.value and new_name.value.strip():
            created = cm.create_course(new_name.value.strip())
            set_user("current_course", created)
            reset_course_state()
            new_name.value = ""
            ui.navigate.to(f"/review/{created}")

    ui.button(t("sidebar.create_course"), on_click=create_course, color="primary").classes("w-full")

    if courses:
        delete_target = ui.select(
            options=[""] + courses,
            label=t("sidebar.delete_course"),
        ).classes("w-full")

        def confirm_delete():
            if cm and delete_target.value:
                cm.delete_course(delete_target.value)
                if get_user("current_course", "") == delete_target.value:
                    set_user("current_course", "")
                    reset_course_state()
                delete_target.value = ""
                ui.navigate.reload()

        ui.button(t("sidebar.confirm_delete"), on_click=confirm_delete).classes("w-full")


def _render_course_section(cm: CourseManager, course: str) -> None:
    """渲染当前课程的板块导航和已保存资料。"""
    ui.separator()
    ui.label(t("sidebar.course_status")).classes("text-subtitle2")

    stats = cm.get_review_stats(course)
    ui.label(
        t(
            "sidebar.stats_line1",
            audio=stats["audio_files"],
            courseware=stats["courseware_files"],
            transcripts=stats["transcripts"],
        )
    ).classes("text-caption")

    status_text = t("status.ready") if stats["vector_store_ready"] else t("status.not_built")
    ui.label(t("sidebar.stats_line2", count=stats["review_materials"], status=status_text)).classes(
        "text-caption"
    )

    ui.separator()
    active = get_user("active_section", "workspace")

    with ui.row().classes("w-full gap-2"):
        ui.button(
            t("nav.input"),
            on_click=lambda: ui.navigate.to(f"/input/{course}"),
            color="primary" if active == "input" else None,
        ).props("flat").classes("flex-1")
        ui.button(
            t("nav.workspace"),
            on_click=lambda: ui.navigate.to(f"/review/{course}"),
            color="primary" if active == "workspace" else None,
        ).props("flat").classes("flex-1")

    ui.label(t("sidebar.saved_materials")).classes("text-caption q-mt-md")

    materials_meta = cm.list_review_materials(course)
    if materials_meta:
        for m in materials_meta:
            type_short = _material_type_short(m.material_type)
            label = f"{m.display_name}  [{type_short}]"

            def _make_handler(filename):
                def handler():
                    set_user("selected_material", filename)
                    set_user("active_section", "workspace")
                    ui.navigate.to(f"/review/{course}")

                return handler

            ui.button(label, on_click=_make_handler(m.filename)).props(
                "flat dense align=left"
            ).classes("w-full text-left")
    else:
        ui.label(f"  {t('sidebar.no_materials')}").classes("text-caption text-grey")

    ui.separator()
    available = get_available_languages()
    current_lang = get_language()

    def on_lang_change(e):
        set_language(e.value)
        set_user("language", e.value)

    ui.select(
        options=available,
        value=current_lang,
        label="Language",
        on_change=on_lang_change,
    ).classes("w-full")


def _material_type_short(material_type: str) -> str:
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
