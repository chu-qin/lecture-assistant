"""NiceGUI 应用入口 — 替代 Streamlit run.py。"""

import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from nicegui import ui  # noqa: E402

# 强制注册 Mermaid ESM 模块（markdown extras=['mermaid'] 需要，否则动态 import 失败）
from nicegui.elements.mermaid import Mermaid as _Mermaid  # noqa: E402, F401

import nicegui_app.pages.material_input  # noqa: E402, F401

# 导入页面模块以触发 @ui.page 路由注册
import nicegui_app.pages.review_qa  # noqa: E402, F401
from nicegui_app.components.sidebar import render_sidebar  # noqa: E402
from nicegui_app.components.theme import inject_theme  # noqa: E402

# 在 ui.run() 之前注入主题（确保脚本包含在初始 HTML 中，能被浏览器执行）
inject_theme()


@ui.page("/")
async def home():
    """首页 — 课程概览 + 快速导航。"""
    await ui.context.client.connected()
    from nicegui_app.state import get_cache, get_user

    render_sidebar()

    cm = get_cache("course_manager")
    current = get_user("current_course", "")

    with ui.column().classes("w-full items-center q-pa-xl"):
        ui.label("课堂助手 — Lecture Assistant").classes("text-h3 q-mb-md")

        if current and cm:
            stats = cm.get_review_stats(current)
            ui.label(f"当前课程: {current}").classes("text-h5 q-mb-lg")

            with ui.row().classes("gap-4 q-mb-lg"):
                with ui.card().classes("text-center q-pa-md"):
                    ui.label(str(stats["audio_files"])).classes("text-h4")
                    ui.label("音频文件").classes("text-caption")
                with ui.card().classes("text-center q-pa-md"):
                    ui.label(str(stats["transcripts"])).classes("text-h4")
                    ui.label("转录").classes("text-caption")
                with ui.card().classes("text-center q-pa-md"):
                    ui.label(str(stats["courseware_files"])).classes("text-h4")
                    ui.label("课件").classes("text-caption")
                with ui.card().classes("text-center q-pa-md"):
                    ui.label(str(stats["review_materials"])).classes("text-h4")
                    ui.label("复习资料").classes("text-caption")

            with ui.row().classes("gap-4"):
                ui.button("资料录入", on_click=lambda: ui.navigate.to(f"/input/{current}"))
                ui.button(
                    "复习与问答",
                    on_click=lambda: ui.navigate.to(f"/review/{current}"),
                    color="primary",
                )
        else:
            ui.label("选择左侧课程开始使用").classes("text-subtitle1 text-grey")


# Storage secret 从环境变量或默认值读取
_storage_secret = os.environ.get("NICEGUI_STORAGE_SECRET", "lecture-assistant-secret")

ui.run(
    title="课堂助手 - Lecture Assistant",
    storage_secret=_storage_secret,
    reload=True,
    port=8501,
    favicon="📖",
)
