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

st.subheader(t("nav.input"))
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
    with st.expander(t("page1.overview"), expanded=False, icon=":material/bar_chart:"):
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
            t("page1.start_transcribe"), type="primary", use_container_width=True,
            icon=":material/mic:",
        )
        clear_btn = col2.button(t("page1.clear_results"), use_container_width=True, icon=":material/clear_all:")

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

            # 全自动摘要 + AI 纠错
            success_auto = [r for r in results if r["result"]]
            if success_auto:
                full_asr_text = "\n\n".join(r["result"].full_text for r in success_auto)

                with st.status("正在生成摘要...") as status:
                    try:
                        from src.llm.factory import get_llm

                        llm = get_llm(config.llm)
                        summary_prompt = (
                            "请用一句话（不超过50字）概括以下课堂录音的主要内容：\n\n"
                            + full_asr_text[:2000]
                        )
                        summary_resp = llm.chat([{"role": "user", "content": summary_prompt}])
                        summary_text = summary_resp.content
                        set_state("asr_summary", summary_text)
                        # 持久化摘要到文件（每个文件一份）
                        transcript_dir = cm.sub_dir(current, "transcripts")
                        for r in success_auto:
                            sf = transcript_dir / f"{Path(r['name']).stem}_summary.txt"
                            sf.write_text(summary_text, encoding="utf-8")
                        status.update(label="摘要生成完成", state="complete")
                    except Exception as exc:
                        status.update(label=f"摘要生成失败: {exc}", state="error")

                parsed_dir = cm.sub_dir(current, "parsed_docs")
                if parsed_dir.exists() and list(parsed_dir.glob("*.md")):
                    reference_parts = []
                    for md_file in sorted(parsed_dir.glob("*.md")):
                        text = md_file.read_text(encoding="utf-8")
                        reference_parts.append(f"### {md_file.stem}\n\n{text[:3000]}")
                    reference_text = "\n\n".join(reference_parts)

                    with st.status("正在结合课件内容修正转录文本...") as status:
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
                            correction_resp = llm.chat(
                                [{"role": "user", "content": correction_prompt}]
                            )
                            set_state("asr_corrected", correction_resp.content)
                            status.update(label="转录修正完成", state="complete")
                        except Exception as exc:
                            status.update(label=f"修正失败: {exc}", state="error")

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
                col_name, col_del = st.columns([5, 1])
                display_name = txt_file.stem.replace("_transcript", "")
                # 读取对应摘要
                summary_file = transcripts_dir / f"{display_name}_summary.txt"
                if summary_file.exists():
                    summary_text = summary_file.read_text(encoding="utf-8")
                    col_name.caption(f"  {display_name}")
                    col_name.caption(f"    {summary_text}")
                else:
                    col_name.caption(f"  {display_name}")
                if col_del.button("删除", key=f"del_tx_{txt_file.stem}", icon=":material/delete:"):
                    # 删除对应的音频文件、转录文件和摘要
                    audio_name = txt_file.stem.replace("_transcript", "")
                    for ext in [".mp3", ".wav", ".m4a", ".flac", ".ogg"]:
                        audio_file = transcripts_dir.parent / "audio" / (audio_name + ext)
                        if audio_file.exists():
                            audio_file.unlink()
                    txt_file.unlink()
                    if summary_file.exists():
                        summary_file.unlink()
                    st.rerun()

    if asr_results:
        st.divider()
        st.subheader(t("page1.transcript_results"))

        success_results = [r for r in asr_results if r["result"]]
        total_chars = sum(len(r["result"].full_text) for r in success_results)
        total_segments = sum(len(r["result"].segments) for r in success_results)
        total_duration = sum(r["result"].duration_seconds for r in success_results)

        info_cols = st.columns(4)
        info_cols[0].metric(t("page1.file_count"), f"{len(success_results)}/{len(asr_results)}")
        info_cols[1].metric(t("page1.total_chars"), total_chars)
        info_cols[2].metric(t("page1.total_segments"), total_segments)
        info_cols[3].metric(t("page1.total_duration"), f"{total_duration / 60:.1f} min")

        tab_names = [f"{'OK' if r['result'] else 'FAIL'} {r['name'][:20]}" for r in asr_results]
        tabs = st.tabs(tab_names)
        for tab, r in zip(tabs, asr_results):
            with tab:
                if r["result"]:
                    res = r["result"]
                    sub_cols = st.columns(3)
                    sub_cols[0].metric(t("page1.chars"), len(res.full_text))
                    sub_cols[1].metric(t("page1.segments"), len(res.segments))
                    sub_cols[2].metric(t("page1.duration"), f"{res.duration_seconds / 60:.1f} min")

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
                        icon=":material/download:",
                    )
                else:
                    st.error(t("page1.parse_fail", error=r.get("error", t("common.unknown_error"))))

        # AI 修正结果显示
        corrected = get_state("asr_corrected", "")
        if corrected and success_results:
            full_asr_text = "\n\n".join(
                f"## {r['name']}\n\n{r['result'].full_text}" for r in success_results if r["result"]
            )
            with st.expander("查看 AI 修正结果", expanded=True, icon=":material/compare:"):
                col_orig, col_corr = st.columns(2)
                with col_orig:
                    st.caption("原始转录")
                    st.text_area(
                        "原始",
                        value=full_asr_text[:3000],
                        height=400,
                        key="corr_orig",
                        label_visibility="collapsed",
                    )
                    if st.button("放弃修正", use_container_width=True, icon=":material/cancel:"):
                        set_state("asr_corrected", "")
                        st.rerun()
                with col_corr:
                    st.caption("修正后")
                    st.text_area(
                        "修正",
                        value=corrected[:3000],
                        height=400,
                        key="corr_corr",
                        label_visibility="collapsed",
                    )
                    if st.button(
                        "确认修正，更新知识库文本", type="primary", use_container_width=True,
                        icon=":material/check_circle:",
                    ):
                        state = cm.load_state(current)
                        state.transcript_text = corrected
                        cm.save_state(current, state)
                        tx_dir = cm.sub_dir(current, "transcripts")
                        corrected_path = tx_dir / "_transcript_corrected.txt"
                        corrected_path.write_text(corrected, encoding="utf-8")
                        set_state("asr_corrected_confirmed", True)
                        st.success("已更新，知识库将使用修正后的文本")
                        st.rerun()

        # 检查是否已确认修正
        if get_state("asr_corrected_confirmed", False):
            st.success("转录文本已修正 ✓")

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

        with st.expander(t("page1.parse_options"), icon=":material/tune:"):
            enable_formula = st.checkbox(t("page1.enable_formula"), value=True)
            enable_table = st.checkbox(t("page1.enable_table"), value=True)
            parse_method = st.selectbox(t("page1.parse_method"), ["auto", "txt", "ocr"], index=0)

        col1, col2, _ = st.columns([1, 1, 4])
        start_btn = col1.button(t("page1.start_parse"), type="primary", use_container_width=True,
                                  icon=":material/description:")
        clear_btn = col2.button(t("page1.clear_all"), use_container_width=True, icon=":material/clear_all:")

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
                col_info, col_del = st.columns([5, 1])
                display = (
                    f"  {md_file.parent.name}/{md_file.name}"
                    if md_file.parent != parsed_dir
                    else f"  {md_file.name}"
                )
                col_info.caption(display)
                if col_del.button("删除", key=f"del_doc_{md_file.stem}", icon=":material/delete:"):
                    md_file.unlink()
                    # 尝试删除对应的源文件
                    for src_dir in ["courseware", "books"]:
                        src_path = cm.sub_dir(current, src_dir) / (md_file.stem + ".*")
                        for ext in [".pdf", ".pptx", ".ppt", ".epub"]:
                            candidate = cm.sub_dir(current, src_dir) / (md_file.stem + ext)
                            if candidate.exists():
                                candidate.unlink()
                    st.rerun()

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
                    with st.expander(t("page1.markdown_preview"), expanded=True, icon=":material/preview:"):
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
                        icon=":material/download:",
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
        start_btn = col1.button(t("page1.book_import"), type="primary", use_container_width=True,
                                  icon=":material/import_contacts:")
        clear_btn = col2.button(t("page1.clear_all"), use_container_width=True, key="book_clear",
                                 icon=":material/clear_all:")

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
                col_info, col_del = st.columns([5, 1])
                col_info.caption(f"  {md_file.name}")
                if col_del.button("删除", key=f"del_book_{md_file.stem}", icon=":material/delete:"):
                    md_file.unlink()
                    # 尝试删除对应的源文件
                    for src_dir in ["books", "courseware"]:
                        for ext in [".epub", ".pdf", ".pptx", ".ppt"]:
                            candidate = cm.sub_dir(current, src_dir) / (md_file.stem + ext)
                            if candidate.exists():
                                candidate.unlink()
                    st.rerun()

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
                    info_cols[2].metric(t("page1.book_chapters"), meta.get("chapter_count", 0))

                    with st.expander(t("page1.book_preview"), expanded=False, icon=":material/preview:"):
                        preview = result.markdown_content[:5000]
                        if len(result.markdown_content) > 5000:
                            preview += f"\n\n{t('page1.content_truncated')}"
                        st.markdown(preview)

                    if result.images:
                        st.caption(t("page1.book_images", count=len(result.images)))
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
                        icon=":material/download:",
                    )
                elif result.metadata.get("error"):
                    st.error(t("page1.book_import_fail", error=result.metadata["error"]))
