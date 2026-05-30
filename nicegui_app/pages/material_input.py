"""资料录入页面 — 语音转文字 + 课件解析 + 书本导入。

NiceGUI 迁移 — 替代 pages/1_资料录入.py。
"""

import asyncio
from pathlib import Path

from nicegui import ui

from src.i18n import t

from ..components.sidebar import _ensure_services, render_sidebar
from ..components.theme import inject_theme
from ..state import get_cache, set_cache, set_user

# ====================================================================
# ASR Tab — 语音转文字
# ====================================================================


def _build_asr_tab(cm, course: str, config, transcripts_dir) -> None:
    """构建语音转文字标签页。"""
    ui.label(t("page1.upload_audio")).classes("text-h6")

    uploaded_files_ref: list = []

    def on_upload(e):
        try:
            for f in e.files if hasattr(e, "files") else [e.file] if hasattr(e, "file") else []:
                uploaded_files_ref.append(f)
            ui.notify(t("page1.uploaded_count", count=len(uploaded_files_ref)), type="info")
        except Exception as exc:
            ui.notify(f"上传处理失败: {exc}", type="negative")

    ui.upload(
        on_upload=on_upload,
        on_rejected=lambda: ui.notify("文件被拒绝（可能超过大小限制或格式不支持）", type="warning"),
        multiple=True,
        max_file_size=200 * 1024 * 1024,
        label=t("page1.upload_audio_hint"),
    ).props("accept=.mp3,.wav,.m4a,.flac,.ogg").classes("w-full")

    async def on_transcribe():
        if not uploaded_files_ref:
            ui.notify("请先上传文件", type="warning")
            return

        from src.asr.funasr_asr import get_asr_model

        results: list = []
        total = len(uploaded_files_ref)

        # Load model
        status_label = ui.label(t("page1.loading_model")).classes("text-info")
        asr = await asyncio.to_thread(get_asr_model, config.asr)
        status_label.set_content(t("page1.model_ready"))

        audio_dir = cm.sub_dir(course, "audio")
        transcript_dir_local = cm.sub_dir(course, "transcripts")

        for idx, uf in enumerate(uploaded_files_ref, 1):
            file_name = uf.name
            status_label.set_content(t("page1.transcribing", idx=idx, total=total, name=file_name))
            try:
                audio_path = audio_dir / file_name
                audio_path.write_bytes(uf.read())

                result = await asyncio.to_thread(asr.transcribe, audio_path)
                results.append({"name": file_name, "result": result})

                output_path = transcript_dir_local / f"{audio_path.stem}_transcript.txt"
                asr.save_transcript(result, output_path)

                ui.notify(
                    t(
                        "page1.transcribe_done",
                        idx=idx,
                        total=total,
                        name=file_name,
                        chars=len(result.full_text),
                        mins=f"{result.duration_seconds / 60:.1f}",
                    ),
                    type="positive",
                )
            except Exception as exc:
                ui.notify(
                    t(
                        "page1.transcribe_fail",
                        idx=idx,
                        total=total,
                        name=file_name,
                        error=str(exc),
                    ),
                    type="negative",
                )
                results.append({"name": file_name, "result": None, "error": str(exc)})

        set_cache("asr_results", results)

        all_text = "\n\n".join(r["result"].full_text for r in results if r["result"])
        if all_text:
            state = cm.load_state(course)
            state.transcript_text = all_text
            state.transcript_meta = {"file_count": len(results)}
            cm.save_state(course, state)

        # Auto-summary + AI correction
        success_auto = [r for r in results if r["result"]]
        if success_auto:
            full_asr_text = "\n\n".join(r["result"].full_text for r in success_auto)

            status_label.set_content("生成摘要中...")
            try:
                from src.llm.factory import get_llm

                llm = get_llm(config.llm)
                summary_prompt = (
                    "请用一句话（不超过50字）概括以下课堂录音的主要内容：\n\n"
                    + full_asr_text[:2000]
                )
                summary_resp = await asyncio.to_thread(
                    llm.chat, [{"role": "user", "content": summary_prompt}]
                )
                summary_text = summary_resp.content
                set_cache("asr_summary", summary_text)

                for r in success_auto:
                    sf = transcript_dir_local / f"{Path(r['name']).stem}_summary.txt"
                    sf.write_text(summary_text, encoding="utf-8")
                status_label.set_content("摘要生成完成")
            except Exception as exc:
                status_label.set_content(f"摘要生成失败: {exc}")

            # AI correction if parsed docs exist
            parsed_dir = cm.sub_dir(course, "parsed_docs")
            if parsed_dir.exists() and list(parsed_dir.glob("*.md")):
                reference_parts = []
                for md_file in sorted(parsed_dir.glob("*.md")):
                    text = md_file.read_text(encoding="utf-8")
                    reference_parts.append(f"### {md_file.stem}\n\n{text[:3000]}")
                reference_text = "\n\n".join(reference_parts)

                status_label.set_content("正在修正转录文本...")
                try:
                    correction_prompt = (
                        "你是一位专业的课堂内容编辑。请根据以下材料修正语音识别转录文本中的错误。\n\n"
                        f"## 参考材料（课件/课本内容）\n\n{reference_text}\n\n"
                        f"## 转录文本（需修正）\n\n{full_asr_text[:6000]}\n\n"
                        "## 修正要求\n\n"
                        "1. 保持原始语义不变，只修正识别错误\n"
                        "2. 结合参考材料中的术语和概念，纠正音近字、错别字\n"
                        "3. 修正专有名词的识别错误\n"
                        "4. 数学公式使用 LaTeX 格式\n"
                        "5. 根据语义补充标点符号和段落分隔\n"
                        "6. 删除无意义的口头禅和重复词语\n\n"
                        "直接输出修正后的完整文本，不要输出修正说明。"
                    )
                    correction_resp = await asyncio.to_thread(
                        llm.chat, [{"role": "user", "content": correction_prompt}]
                    )
                    set_cache("asr_corrected", correction_resp.content)
                    status_label.set_content("转录修正完成")
                except Exception as exc:
                    status_label.set_content(f"修正失败: {exc}")

        status_label.set_content("完成 ✓")
        ui.navigate.reload()

    ui.button(t("page1.start_transcribe"), on_click=on_transcribe, color="primary").classes(
        "q-mt-md"
    )

    def on_clear():
        set_cache("asr_results", [])
        ui.navigate.reload()

    ui.button(t("page1.clear_results"), on_click=on_clear).classes("q-ml-sm q-mt-md")

    # Display existing transcripts
    _render_existing_transcripts(cm, course, transcripts_dir)


def _render_existing_transcripts(cm, course: str, transcripts_dir) -> None:
    """显示已有转录结果。"""
    asr_results = get_cache("asr_results", [])
    if not asr_results:
        existing = list(transcripts_dir.glob("*_transcript.txt"))
        if existing:
            ui.separator()
            ui.label(t("page1.existing_transcripts", count=len(existing))).classes("text-caption")
            for txt_file in sorted(existing):
                with ui.row().classes("w-full items-center"):
                    with ui.column().classes("flex-1"):
                        display_name = txt_file.stem.replace("_transcript", "")
                        summary_file = transcripts_dir / f"{display_name}_summary.txt"
                        if summary_file.exists():
                            ui.label(display_name).classes("text-caption")
                            ui.label(summary_file.read_text(encoding="utf-8")[:100]).classes(
                                "text-caption text-grey"
                            )
                        else:
                            ui.label(display_name).classes("text-caption")

                    def _make_delete(tf, sf):
                        def handler():
                            audio_name = tf.stem.replace("_transcript", "")
                            audio_dir = transcripts_dir.parent / "audio"
                            for ext in [".mp3", ".wav", ".m4a", ".flac", ".ogg"]:
                                af = audio_dir / (audio_name + ext)
                                if af.exists():
                                    af.unlink()
                            tf.unlink()
                            if sf.exists():
                                sf.unlink()
                            ui.navigate.reload()

                        return handler

                    sf = transcripts_dir / f"{txt_file.stem.replace('_transcript', '')}_summary.txt"
                    ui.button("删除", on_click=_make_delete(txt_file, sf)).props(
                        "flat dense"
                    ).classes("q-ml-auto")


# ====================================================================
# Parser Tab — 课件解析
# ====================================================================


def _build_parser_tab(cm, course: str, config, parsed_dir) -> None:
    """构建课件解析标签页。"""
    ui.label(t("page1.upload_docs")).classes("text-h6")

    uploaded_docs_ref: list = []

    def on_upload(e):
        try:
            for f in e.files if hasattr(e, "files") else [e.file] if hasattr(e, "file") else []:
                uploaded_docs_ref.append(f)
            ui.notify(t("page1.uploaded_count", count=len(uploaded_docs_ref)), type="info")
        except Exception as exc:
            ui.notify(f"上传处理失败: {exc}", type="negative")

    ui.upload(
        on_upload=on_upload,
        on_rejected=lambda: ui.notify("文件被拒绝（可能超过大小限制或格式不支持）", type="warning"),
        multiple=True,
        max_file_size=200 * 1024 * 1024,
        label=t("page1.upload_docs_hint"),
    ).props("accept=.pdf,.pptx,.ppt").classes("w-full")

    # Options
    enable_formula = ui.checkbox(t("page1.enable_formula"), value=True)
    enable_table = ui.checkbox(t("page1.enable_table"), value=True)

    async def on_parse():
        if not uploaded_docs_ref:
            ui.notify("请先上传文件", type="warning")
            return

        set_cache("parsed_results", [])
        from src.parser.mineru_parser import get_parser

        courseware_dir = cm.sub_dir(course, "courseware")
        parsed_output_dir = cm.sub_dir(course, "parsed_docs")

        file_paths = []
        for uf in uploaded_docs_ref:
            fp = courseware_dir / uf.name
            fp.write_bytes(uf.read())
            file_paths.append(fp)

        parser_config = config.parser
        parser_config.enable_formula_recognition = enable_formula.value
        parser_config.enable_table_recognition = enable_table.value
        parser = get_parser(parser_config)

        results = []
        progress = ui.linear_progress(0).classes("w-full")
        status = ui.label(t("page1.preparing_parse")).classes("text-caption")

        for i, fp in enumerate(file_paths):
            progress.value = i / len(file_paths)
            status.set_content(t("page1.parsing", name=fp.name, idx=i + 1, total=len(file_paths)))
            try:
                result = await asyncio.to_thread(parser.parse, fp, parsed_output_dir)
                results.append(result)
                ui.notify(
                    t(
                        "page1.parse_done",
                        name=fp.name,
                        formulas=result.formulas_count,
                        tables=result.tables_count,
                        images=len(result.images),
                    ),
                    type="positive",
                )
            except Exception as e:
                ui.notify(f"{fp.name}: {e}", type="negative")

        progress.value = 1.0
        status.set_content(t("page1.parse_complete"))
        set_cache("parsed_results", results)

        state = cm.load_state(course)
        state.parsed_doc_paths = [str(r.markdown_file) for r in results if r.markdown_file]
        cm.save_state(course, state)
        ui.navigate.reload()

    ui.button(t("page1.start_parse"), on_click=on_parse, color="primary").classes("q-mt-md")

    def on_clear():
        set_cache("parsed_results", [])
        ui.navigate.reload()

    ui.button(t("page1.clear_all"), on_click=on_clear).classes("q-ml-sm q-mt-md")

    # Show existing parsed docs
    _render_existing_docs(cm, course, parsed_dir)


def _render_existing_docs(cm, course: str, parsed_dir) -> None:
    """显示已有解析结果。"""
    parsed_results = get_cache("parsed_results")
    if not parsed_results:
        existing = list(parsed_dir.rglob("*.md"))
        if existing:
            ui.separator()
            ui.label(t("page1.existing_docs", count=len(existing))).classes("text-caption")
            for md_file in sorted(existing):
                with ui.row().classes("w-full items-center"):
                    display = (
                        f"{md_file.parent.name}/{md_file.name}"
                        if md_file.parent != parsed_dir
                        else md_file.name
                    )
                    ui.label(display).classes("text-caption flex-1")

                    def _make_del(fp):
                        def handler():
                            fp.unlink()
                            for src_dir, exts in [
                                ("courseware", [".pdf", ".pptx", ".ppt"]),
                                ("books", [".epub", ".pdf", ".pptx", ".ppt"]),
                            ]:
                                for ext in exts:
                                    c = cm.sub_dir(course, src_dir) / (fp.stem + ext)
                                    if c.exists():
                                        c.unlink()
                            ui.navigate.reload()

                        return handler

                    ui.button("删除", on_click=_make_del(md_file)).props("flat dense")


# ====================================================================
# Book Tab — EPUB 书本导入
# ====================================================================


def _build_book_tab(cm, course: str, config, parsed_dir) -> None:
    """构建书本导入标签页。"""
    ui.label(t("page1.upload_book")).classes("text-h6")

    uploaded_books_ref: list = []

    def on_upload(e):
        try:
            for f in e.files if hasattr(e, "files") else [e.file] if hasattr(e, "file") else []:
                uploaded_books_ref.append(f)
            ui.notify(t("page1.book_uploaded_count", count=len(uploaded_books_ref)), type="info")
        except Exception as exc:
            ui.notify(f"上传处理失败: {exc}", type="negative")

    ui.upload(
        on_upload=on_upload,
        on_rejected=lambda: ui.notify("文件被拒绝（可能超过大小限制或格式不支持）", type="warning"),
        multiple=True,
        max_file_size=200 * 1024 * 1024,
        label=t("page1.upload_book_hint"),
    ).props("accept=.epub").classes("w-full")

    async def on_import():
        if not uploaded_books_ref:
            ui.notify("请先上传文件", type="warning")
            return

        set_cache("book_results", [])
        from src.parser.epub_parser import get_epub_parser

        book_dir = cm.sub_dir(course, "books")
        parsed_output_dir = cm.sub_dir(course, "parsed_docs")

        file_paths = []
        for uf in uploaded_books_ref:
            fp = book_dir / uf.name
            fp.write_bytes(uf.read())
            file_paths.append(fp)

        parser = get_epub_parser()
        results = []
        progress = ui.linear_progress(0).classes("w-full")
        status = ui.label(t("page1.preparing_parse")).classes("text-caption")

        for i, fp in enumerate(file_paths):
            progress.value = i / len(file_paths)
            status.set_content(
                t("page1.book_importing", name=fp.name, idx=i + 1, total=len(file_paths))
            )
            try:
                result = await asyncio.to_thread(parser.parse, fp, parsed_output_dir)
                results.append(result)
                ui.notify(
                    t(
                        "page1.book_import_done",
                        name=fp.name,
                        chapters=result.metadata.get("chapter_count", 0),
                    ),
                    type="positive",
                )
            except Exception as e:
                ui.notify(f"{fp.name}: {e}", type="negative")

        progress.value = 1.0
        status.set_content(t("page1.book_import_complete"))
        set_cache("book_results", results)

        state = cm.load_state(course)
        state.parsed_doc_paths = list(
            set(state.parsed_doc_paths) | {str(r.markdown_file) for r in results if r.markdown_file}
        )
        cm.save_state(course, state)
        ui.navigate.reload()

    ui.button(t("page1.book_import"), on_click=on_import, color="primary").classes("q-mt-md")

    def on_clear():
        set_cache("book_results", [])
        ui.navigate.reload()

    ui.button(t("page1.clear_all"), on_click=on_clear).classes("q-ml-sm q-mt-md")


# ====================================================================
# Page
# ====================================================================


@ui.page("/input/{course_name}")
async def material_input_page(course_name: str):
    """资料录入页面。"""
    await ui.context.client.connected()
    inject_theme()
    render_sidebar()

    _ensure_services()
    cm = get_cache("course_manager")
    config = get_cache("app_config")
    set_user("current_course", course_name)

    # Overview stats
    stats = cm.get_review_stats(course_name)
    if stats["audio_files"] or stats["courseware_files"] or stats["transcripts"]:
        with ui.expansion(t("page1.overview"), value=False).classes("w-full"):
            with ui.row().classes("w-full gap-4"):
                with ui.card().classes("flex-1"):
                    ui.label(str(stats["audio_files"])).classes("text-h4")
                    ui.label(t("page1.audio_files")).classes("text-caption")
                with ui.card().classes("flex-1"):
                    ui.label(str(stats["transcripts"])).classes("text-h4")
                    ui.label(t("page1.transcripts")).classes("text-caption")
                with ui.card().classes("flex-1"):
                    ui.label(str(stats["courseware_files"])).classes("text-h4")
                    ui.label(t("page1.courseware_files")).classes("text-caption")
                with ui.card().classes("flex-1"):
                    ui.label(str(stats["review_materials"])).classes("text-h4")
                    ui.label(t("page1.generated_materials")).classes("text-caption")

    transcripts_dir = cm.sub_dir(course_name, "transcripts")
    parsed_dir = cm.sub_dir(course_name, "parsed_docs")

    # Three tabs
    with ui.tabs() as tabs:
        tab_asr = ui.tab(t("page1.tab_asr"))
        tab_parser = ui.tab(t("page1.tab_parser"))
        tab_book = ui.tab(t("page1.tab_book"))

    with ui.tab_panels(tabs, value=tab_asr).classes("w-full"):
        with ui.tab_panel(tab_asr):
            _build_asr_tab(cm, course_name, config, transcripts_dir)
        with ui.tab_panel(tab_parser):
            _build_parser_tab(cm, course_name, config, parsed_dir)
        with ui.tab_panel(tab_book):
            _build_book_tab(cm, course_name, config, parsed_dir)
