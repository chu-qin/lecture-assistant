"""课程工作台: 资料录入 — 语音转文字 + 课件解析"""

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="资料录入", page_icon="", layout="wide")

import sys  # noqa: E402

_project_root = Path(__file__).resolve().parent.parent  # noqa: E402
if str(_project_root) not in sys.path:  # noqa: E402
    sys.path.insert(0, str(_project_root))  # noqa: E402

from src.i18n import t  # noqa: E402
from src.ui.session_state import get_state, init_session_state, set_state  # noqa: E402
from src.ui.sidebar import render_sidebar  # noqa: E402

init_session_state()
render_sidebar()

st.title(t("nav.input"))
st.caption(t("page1.caption"))

# ---- 课程检查 ----
current = get_state("current_course", "")
if not current:
    st.warning(t("common.no_course"))
    st.stop()

cm = get_state("course_manager")
config = get_state("app_config")

# ====================================================================
# 已有材料概览
# ====================================================================
stats = cm.get_review_stats(current)
if stats["audio_files"] or stats["courseware_files"] or stats["transcripts"]:
    with st.expander(t("page1.overview"), expanded=False):
        cols = st.columns(4)
        cols[0].metric(t("page1.audio_files"), stats["audio_files"])
        cols[1].metric(t("page1.transcripts"), stats["transcripts"])
        cols[2].metric(t("page1.courseware_files"), stats["courseware_files"])
        cols[3].metric(t("page1.generated_materials"), stats["review_materials"])

# ====================================================================
# 两个 Tab
# ====================================================================
tab_asr, tab_parser, tab_book = st.tabs(
    [t("page1.tab_asr"), t("page1.tab_parser"), t("page1.tab_book")]
)

# ---- Tab 1: 语音转文字 ----
with tab_asr:
    st.subheader(t("page1.upload_audio"))
    uploaded_files = st.file_uploader(
        t("page1.upload_audio_hint"),
        type=["mp3", "wav", "m4a", "flac", "ogg"],
        accept_multiple_files=True,
        key="asr_uploader",
    )

    if uploaded_files:
        for uf in uploaded_files:
            file_size_mb = len(uf.getvalue()) / (1024 * 1024)
            st.caption(f"{uf.name} ({file_size_mb:.1f} MB)")

        col1, col2, _ = st.columns([1, 1, 4])
        start_btn = col1.button(
            t("page1.start_transcribe"), type="primary", use_container_width=True
        )
        clear_btn = col2.button(t("page1.clear_results"), use_container_width=True)

        if clear_btn:
            set_state("asr_results", [])
            st.rerun()

        if start_btn:
            from src.asr.funasr_asr import get_asr_model

            results: list = []
            total = len(uploaded_files)

            with st.status(t("page1.loading_model")) as model_status:
                asr = get_asr_model(config.asr)
                model_status.update(label=t("page1.model_ready"), state="running")

            for idx, uf in enumerate(uploaded_files, 1):
                with st.status(
                    t("page1.transcribing", idx=idx, total=total, name=uf.name),
                    expanded=True,
                ) as status:
                    try:
                        audio_dir = cm.sub_dir(current, "audio")
                        audio_path = audio_dir / uf.name
                        audio_path.write_bytes(uf.getvalue())

                        result = asr.transcribe(audio_path)
                        results.append({"name": uf.name, "result": result})

                        transcript_dir = cm.sub_dir(current, "transcripts")
                        output_path = transcript_dir / f"{audio_path.stem}_transcript.txt"
                        asr.save_transcript(result, output_path)

                        status.update(
                            label=t(
                                "page1.transcribe_done",
                                idx=idx,
                                total=total,
                                name=uf.name,
                                chars=len(result.full_text),
                                mins=f"{result.duration_seconds / 60:.1f}",
                            ),
                            state="complete",
                        )
                    except Exception as e:
                        status.update(
                            label=t(
                                "page1.transcribe_fail",
                                idx=idx,
                                total=total,
                                name=uf.name,
                                error=str(e),
                            ),
                            state="error",
                        )
                        results.append({"name": uf.name, "result": None, "error": str(e)})

            set_state("asr_results", results)

            all_text = "\n\n".join(r["result"].full_text for r in results if r["result"])
            if all_text:
                state = cm.load_state(current)
                state.transcript_text = all_text
                state.transcript_meta = {"file_count": len(results)}
                cm.save_state(current, state)

    # 显示已有转录结果
    asr_results = get_state("asr_results", [])
    if not asr_results:
        # 从磁盘加载已有转录
        transcripts_dir = cm.sub_dir(current, "transcripts")
        existing = list(transcripts_dir.glob("*_transcript.txt"))
        if existing:
            st.divider()
            st.caption(t("page1.existing_transcripts", count=len(existing)))
            for txt_file in sorted(existing):
                st.caption(f"  {txt_file.stem.replace('_transcript', '')}")

    if asr_results:
        st.divider()
        st.subheader(t("page1.transcript_results"))

        success_results = [r for r in asr_results if r["result"]]
        total_chars = sum(len(r["result"].full_text) for r in success_results)
        total_segments = sum(len(r["result"].segments) for r in success_results)
        total_duration = sum(r["result"].duration_seconds for r in success_results)

        info_cols = st.columns(4)
        info_cols[0].metric(
            t("page1.file_count"), f"{len(success_results)}/{len(asr_results)}"
        )
        info_cols[1].metric(t("page1.total_chars"), total_chars)
        info_cols[2].metric(t("page1.total_segments"), total_segments)
        info_cols[3].metric(t("page1.total_duration"), f"{total_duration / 60:.1f} min")

        tab_names = [
            f"{'OK' if r['result'] else 'FAIL'} {r['name'][:20]}" for r in asr_results
        ]
        tabs = st.tabs(tab_names)
        for tab, r in zip(tabs, asr_results):
            with tab:
                if r["result"]:
                    res = r["result"]
                    sub_cols = st.columns(3)
                    sub_cols[0].metric(t("page1.chars"), len(res.full_text))
                    sub_cols[1].metric(t("page1.segments"), len(res.segments))
                    sub_cols[2].metric(
                        t("page1.duration"), f"{res.duration_seconds / 60:.1f} min"
                    )

                    st.text_area(
                        t("page1.transcript_text"),
                        value=res.full_text,
                        height=300,
                        key=f"transcript_{r['name']}",
                    )
                    st.download_button(
                        t("page1.download_txt"),
                        data=res.full_text.encode("utf-8-sig"),
                        file_name=f"{Path(r['name']).stem}_transcript.txt",
                        mime="text/plain",
                        key=f"dl_{r['name']}",
                    )
                else:
                    st.error(
                        t("page1.parse_fail", error=r.get("error", t("common.unknown_error")))
                    )

# ---- Tab 2: 课件解析 ----
with tab_parser:
    st.subheader(t("page1.upload_docs"))
    uploaded_docs = st.file_uploader(
        t("page1.upload_docs_hint"),
        type=["pdf", "pptx", "ppt"],
        accept_multiple_files=True,
        key="parser_uploader",
    )

    if uploaded_docs:
        st.info(t("page1.uploaded_count", count=len(uploaded_docs)))

        with st.expander(t("page1.parse_options")):
            enable_formula = st.checkbox(t("page1.enable_formula"), value=True)
            enable_table = st.checkbox(t("page1.enable_table"), value=True)
            parse_method = st.selectbox(t("page1.parse_method"), ["auto", "txt", "ocr"], index=0)

        col1, col2, _ = st.columns([1, 1, 4])
        start_btn = col1.button(
            t("page1.start_parse"), type="primary", use_container_width=True
        )
        clear_btn = col2.button(t("page1.clear_all"), use_container_width=True)

        if clear_btn:
            set_state("parsed_results", [])
            st.rerun()

        if start_btn:
            set_state("parsed_results", [])

            from src.parser.mineru_parser import get_parser

            courseware_dir = cm.sub_dir(current, "courseware")
            parsed_output_dir = cm.sub_dir(current, "parsed_docs")

            file_paths = []
            for uf in uploaded_docs:
                fp = courseware_dir / uf.name
                fp.write_bytes(uf.getvalue())
                file_paths.append(fp)

            parser_config = config.parser
            parser_config.enable_formula_recognition = enable_formula
            parser_config.enable_table_recognition = enable_table
            parser_config.method = parse_method  # type: ignore[assignment]
            parser = get_parser(parser_config)

            results = []
            progress_bar = st.progress(0, text=t("page1.preparing_parse"))

            for i, fp in enumerate(file_paths):
                progress_bar.progress(
                    (i) / len(file_paths),
                    text=t("page1.parsing", name=fp.name, idx=i + 1, total=len(file_paths)),
                )
                try:
                    result = parser.parse(fp, parsed_output_dir)
                    results.append(result)
                    st.success(
                        t(
                            "page1.parse_done",
                            name=fp.name,
                            formulas=result.formulas_count,
                            tables=result.tables_count,
                            images=len(result.images),
                        )
                    )
                except Exception as e:
                    st.error(f"{fp.name}: {e}")

            progress_bar.progress(1.0, text=t("page1.parse_complete"))
            set_state("parsed_results", results)

            state = cm.load_state(current)
            state.parsed_doc_paths = [str(r.markdown_file) for r in results if r.markdown_file]
            cm.save_state(current, state)

    # 显示已有解析结果
    parsed_results = get_state("parsed_results")
    if not parsed_results:
        parsed_dir = cm.sub_dir(current, "parsed_docs")
        existing_md = list(parsed_dir.rglob("*.md"))
        if existing_md:
            st.divider()
            st.caption(t("page1.existing_docs", count=len(existing_md)))
            for md_file in sorted(existing_md):
                st.caption(f"  {md_file.parent.name}/{md_file.name}")

    if parsed_results:
        st.divider()
        st.subheader(t("page1.parse_results"))

        file_names = [
            r.metadata.get("source_file", t("page1.file_fallback", idx=i + 1))
            for i, r in enumerate(parsed_results)
        ]
        tabs = st.tabs(file_names)

        for tab, result in zip(tabs, parsed_results):
            with tab:
                if result.markdown_content:
                    with st.expander(t("page1.markdown_preview"), expanded=True):
                        preview = result.markdown_content[:5000]
                        if len(result.markdown_content) > 5000:
                            preview += f"\n\n{t('page1.content_truncated')}"
                        st.markdown(preview)

                    col_a, col_b = st.columns(2)
                    col_a.metric(t("page1.formulas_count"), result.formulas_count)
                    col_b.metric(t("page1.tables_count"), result.tables_count)

                    st.caption(t("page1.images_count", count=len(result.images)))
                    if result.images:
                        img_cols = st.columns(min(len(result.images), 4))
                        for j, img_path in enumerate(result.images[:8]):
                            try:
                                img_cols[j % 4].image(
                                    str(img_path),
                                    caption=img_path.name,
                                    use_container_width=True,
                                )
                            except Exception:
                                pass

                    file_name = result.metadata.get("source_file", "parsed")
                    st.download_button(
                        t("page1.download_md", name=file_name),
                        data=result.markdown_content.encode("utf-8"),
                        file_name=f"{file_name}.md",
                        mime="text/markdown",
                    )
                elif result.metadata.get("error"):
                    st.error(t("page1.parse_fail", error=result.metadata["error"]))

# ---- Tab 3: 书本导入 ----
with tab_book:
    st.subheader(t("page1.upload_book"))
    uploaded_books = st.file_uploader(
        t("page1.upload_book_hint"),
        type=["epub"],
        accept_multiple_files=True,
        key="book_uploader",
    )

    if uploaded_books:
        st.info(t("page1.book_uploaded_count", count=len(uploaded_books)))

        col1, col2, _ = st.columns([1, 1, 4])
        start_btn = col1.button(
            t("page1.book_import"), type="primary", use_container_width=True
        )
        clear_btn = col2.button(t("page1.clear_all"), use_container_width=True, key="book_clear")

        if clear_btn:
            set_state("book_results", [])
            st.rerun()

        if start_btn:
            set_state("book_results", [])

            from src.parser.epub_parser import get_epub_parser

            book_dir = cm.sub_dir(current, "books")
            parsed_output_dir = cm.sub_dir(current, "parsed_docs")

            file_paths = []
            for uf in uploaded_books:
                fp = book_dir / uf.name
                fp.write_bytes(uf.getvalue())
                file_paths.append(fp)

            parser = get_epub_parser()
            results = []
            progress_bar = st.progress(0, text=t("page1.preparing_parse"))

            for i, fp in enumerate(file_paths):
                progress_bar.progress(
                    (i) / len(file_paths),
                    text=t(
                        "page1.book_importing",
                        name=fp.name,
                        idx=i + 1,
                        total=len(file_paths),
                    ),
                )
                try:
                    result = parser.parse(fp, parsed_output_dir)
                    results.append(result)
                    st.success(
                        t(
                            "page1.book_import_done",
                            name=fp.name,
                            chapters=result.metadata.get("chapter_count", 0),
                        )
                    )
                except Exception as e:
                    st.error(f"{fp.name}: {e}")

            progress_bar.progress(1.0, text=t("page1.book_import_complete"))
            set_state("book_results", results)

            state = cm.load_state(current)
            state.parsed_doc_paths = list(
                set(state.parsed_doc_paths)
                | {str(r.markdown_file) for r in results if r.markdown_file}
            )
            cm.save_state(current, state)

    # 显示已有导入结果
    book_results = get_state("book_results", [])
    if not book_results:
        parsed_dir = cm.sub_dir(current, "parsed_docs")
        existing_md = list(parsed_dir.glob("*.md"))
        if existing_md:
            st.divider()
            st.caption(t("page1.book_existing", count=len(existing_md)))
            for md_file in sorted(existing_md):
                st.caption(f"  {md_file.name}")

    if book_results:
        st.divider()
        st.subheader(t("page1.book_results"))

        book_names = [
            r.metadata.get("title", t("page1.file_fallback", idx=i + 1))
            for i, r in enumerate(book_results)
        ]
        tabs = st.tabs(book_names)

        for tab, result in zip(tabs, book_results):
            with tab:
                if result.markdown_content:
                    meta = result.metadata
                    info_cols = st.columns(3)
                    info_cols[0].metric(
                        t("page1.book_title"), meta.get("title", t("common.unknown"))
                    )
                    info_cols[1].metric(
                        t("page1.book_author"), meta.get("author", t("common.unknown"))
                    )
                    info_cols[2].metric(
                        t("page1.book_chapters"), meta.get("chapter_count", 0)
                    )

                    with st.expander(t("page1.book_preview"), expanded=False):
                        preview = result.markdown_content[:5000]
                        if len(result.markdown_content) > 5000:
                            preview += f"\n\n{t('page1.content_truncated')}"
                        st.markdown(preview)

                    if result.images:
                        st.caption(
                            t("page1.book_images", count=len(result.images))
                        )
                        img_cols = st.columns(min(len(result.images), 4))
                        for j, img_path in enumerate(result.images[:8]):
                            try:
                                img_cols[j % 4].image(
                                    str(img_path),
                                    caption=img_path.name,
                                    use_container_width=True,
                                )
                            except Exception:
                                pass

                    file_name = meta.get("title", "book")
                    st.download_button(
                        t("page1.book_download", name=file_name),
                        data=result.markdown_content.encode("utf-8"),
                        file_name=f"{file_name}.md",
                        mime="text/markdown",
                        key=f"dl_book_{file_name}",
                    )
                elif result.metadata.get("error"):
                    st.error(
                        t("page1.book_import_fail", error=result.metadata["error"])
                    )
