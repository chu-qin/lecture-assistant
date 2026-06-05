"""课件解析 + EPUB 导入路由 — multipart 上传 + SSE 进度。"""

import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse

from .deps import get_cm, get_config_obj

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_SUPPORTED_PARSE_EXTENSIONS = {".pdf", ".pptx", ".ppt"}
_SUPPORTED_EPUB_EXTENSIONS = {".epub"}


@router.post("/courses/{course_id}/parse")
async def parse_docs(
    course_id: str,
    files: list[UploadFile] = File(...),
    options: str = Form("{}"),
):
    """上传课件文件并解析（SSE 流式进度）。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    opts = json.loads(options) if options else {}
    enable_formula = opts.get("enable_formula", True)
    enable_table = opts.get("enable_table", True)

    async def event_stream():
        config = get_config_obj()
        courseware_dir = cm.sub_dir(course_id, "courseware")
        parsed_dir = cm.sub_dir(course_id, "parsed_docs")
        courseware_dir.mkdir(parents=True, exist_ok=True)
        parsed_dir.mkdir(parents=True, exist_ok=True)

        # 保存上传的文件
        saved_files = []
        for f in files:
            ext = Path(f.filename).suffix.lower() if f.filename else ""
            if ext not in _SUPPORTED_PARSE_EXTENSIONS:
                yield f"data: {json.dumps({'type': 'error', 'file': f.filename, 'message': f'不支持的格式: {ext}'})}\n\n"
                continue
            file_path = courseware_dir / f.filename
            content = await f.read()
            file_path.write_bytes(content)
            saved_files.append((file_path, f.filename, ext))
            yield f"data: {json.dumps({'type': 'status', 'phase': 'saved', 'file': f.filename})}\n\n"

        if not saved_files:
            yield f"data: {json.dumps({'type': 'error', 'message': '没有可解析的文件'})}\n\n"
            return

        results = []
        for idx, (fpath, fname, ext) in enumerate(saved_files):
            yield f"data: {json.dumps({'type': 'status', 'phase': 'parsing', 'file': fname, 'index': idx + 1, 'total': len(saved_files)})}\n\n"

            try:
                if ext in (".pptx", ".ppt"):
                    # PPT 文件使用 python-pptx 直接提取文本
                    from src.parser.ppt_extractor import extract_text as ppt_extract

                    text = ppt_extract(fpath)
                    doc_out_dir = parsed_dir / fpath.stem
                    doc_out_dir.mkdir(parents=True, exist_ok=True)
                    md_path = doc_out_dir / f"{fpath.stem}.md"
                    md_path.write_text(text, encoding="utf-8")

                    yield f"data: {json.dumps({'type': 'result', 'file': fname, 'markdown': text[:500] + ('...' if len(text) > 500 else ''), 'formulas': 0, 'tables': 0, 'images': 0})}\n\n"
                    results.append({"file": fname, "success": True})
                else:
                    # PDF 文件使用 MinerU
                    from src.parser.mineru_parser import get_parser

                    parser = get_parser(config.parser)
                    doc_out_dir = parsed_dir / fpath.stem
                    doc_out_dir.mkdir(parents=True, exist_ok=True)

                    result = parser.parse(fpath, doc_out_dir)
                    yield f"data: {json.dumps({'type': 'result', 'file': fname, 'markdown': result.markdown[:500] + ('...' if len(result.markdown) > 500 else ''), 'formulas': result.formula_count, 'tables': result.table_count, 'images': result.image_count})}\n\n"
                    results.append({"file": fname, "success": True})
            except Exception as e:
                logger.exception("Parsing failed for %s", fname)
                yield f"data: {json.dumps({'type': 'error', 'file': fname, 'message': str(e)})}\n\n"
                results.append({"file": fname, "success": False})

        yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/courses/{course_id}/import-epub")
async def import_epub(
    course_id: str,
    files: list[UploadFile] = File(...),
):
    """上传并导入 EPUB 电子书（SSE 流式进度）。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    async def event_stream():
        books_dir = cm.sub_dir(course_id, "books")
        parsed_dir = cm.sub_dir(course_id, "parsed_docs")
        books_dir.mkdir(parents=True, exist_ok=True)
        parsed_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for f in files:
            ext = Path(f.filename).suffix.lower() if f.filename else ""
            if ext not in _SUPPORTED_EPUB_EXTENSIONS:
                yield f"data: {json.dumps({'type': 'error', 'file': f.filename, 'message': f'不支持的格式: {ext}'})}\n\n"
                continue

            yield f"data: {json.dumps({'type': 'status', 'phase': 'importing', 'file': f.filename})}\n\n"

            try:
                file_path = books_dir / f.filename
                content = await f.read()
                file_path.write_bytes(content)

                from src.parser.epub_parser import get_epub_parser

                parser = get_epub_parser()
                doc_out_dir = parsed_dir / file_path.stem
                doc_out_dir.mkdir(parents=True, exist_ok=True)

                result = parser.parse(file_path, doc_out_dir)
                yield f"data: {json.dumps({'type': 'result', 'file': f.filename, 'markdown': result.markdown[:500] + ('...' if len(result.markdown) > 500 else ''), 'metadata': getattr(result, 'metadata', {})})}\n\n"
                results.append({"file": f.filename, "success": True})
            except Exception as e:
                logger.exception("EPUB import failed for %s", f.filename)
                yield f"data: {json.dumps({'type': 'error', 'file': f.filename, 'message': str(e)})}\n\n"
                results.append({"file": f.filename, "success": False})

        yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
