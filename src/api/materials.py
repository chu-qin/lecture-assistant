"""资料（转录/文档/素材）管理路由。"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from .deps import get_cm

router = APIRouter(prefix="/api")


def _scan_sources(course_name: str):
    """扫描课程下的转录文件和解析文档。"""
    cm = get_cm()
    transcripts: list[dict] = []
    docs: list[dict] = []
    seen_tx: set[str] = set()
    seen_doc: set[str] = set()

    transcripts_dir = cm.sub_dir(course_name, "transcripts")
    for txt_file in sorted(transcripts_dir.glob("*_transcript.txt")):
        name = txt_file.stem.replace("_transcript", "")
        if name not in seen_tx:
            try:
                text = txt_file.read_text(encoding="utf-8")
                if text.strip():
                    transcripts.append({"name": name, "text": text, "char_count": len(text)})
                    seen_tx.add(name)
            except Exception:
                pass

    for corrected_file in sorted(transcripts_dir.glob("*_corrected*.txt")):
        name = corrected_file.stem
        if name not in seen_tx:
            try:
                text = corrected_file.read_text(encoding="utf-8")
                if text.strip():
                    transcripts.append({"name": f"[AI修正] {name}", "text": text, "char_count": len(text)})
                    seen_tx.add(name)
            except Exception:
                pass

    parsed_dir = cm.sub_dir(course_name, "parsed_docs")
    for md_file in sorted(parsed_dir.rglob("*.md")):
        if md_file.is_file():
            doc_name = md_file.parent.name if md_file.parent != parsed_dir else md_file.stem
            if doc_name not in seen_doc:
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if text.strip():
                        docs.append({"name": doc_name, "text": text, "char_count": len(text)})
                        seen_doc.add(doc_name)
                except Exception:
                    pass

    return transcripts, docs


@router.get("/courses/{course_id}/transcripts")
async def list_transcripts(course_id: str):
    """列出转录文件。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    transcripts_dir = cm.sub_dir(course_id, "transcripts")
    result = []
    for txt_file in sorted(transcripts_dir.glob("*_transcript.txt")):
        name = txt_file.stem.replace("_transcript", "")
        has_correction = (transcripts_dir / f"{name}_corrected.txt").exists() or \
                         (transcripts_dir / "_transcript_corrected.txt").exists()
        result.append({
            "name": name,
            "char_count": len(txt_file.read_text(encoding="utf-8")) if txt_file.exists() else 0,
            "has_correction": has_correction,
        })
    return {"transcripts": result}


@router.get("/courses/{course_id}/documents")
async def list_documents(course_id: str):
    """列出解析文档。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    parsed_dir = cm.sub_dir(course_id, "parsed_docs")
    result = []
    for md_file in sorted(parsed_dir.rglob("*.md")):
        if md_file.is_file():
            doc_name = md_file.parent.name if md_file.parent != parsed_dir else md_file.stem
            result.append({
                "name": doc_name,
                "char_count": len(md_file.read_text(encoding="utf-8")),
            })
    return {"documents": result}


@router.delete("/courses/{course_id}/transcripts/{name}")
async def delete_transcript(course_id: str, name: str):
    """删除转录及其关联文件。"""
    import os
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    tx_dir = cm.sub_dir(course_id, "transcripts")
    patterns = [
        f"{name}_transcript.txt",
        f"{name}_transcript.json",
        f"{name}_summary.txt",
        f"{name}_corrected.txt",
    ]
    for p in patterns:
        f = tx_dir / p
        if f.exists():
            os.remove(str(f))
    return {"success": True}


@router.delete("/courses/{course_id}/documents/{name}")
async def delete_document(course_id: str, name: str):
    """删除文档及关联的图片目录。"""
    import shutil, os
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    parsed_dir = cm.sub_dir(course_id, "parsed_docs")
    # 删除 .md 文件
    md_file = parsed_dir / f"{name}.md"
    if md_file.exists():
        os.remove(str(md_file))
    # 删除子目录
    sub_dir = parsed_dir / name
    if sub_dir.exists():
        shutil.rmtree(str(sub_dir))
    # 删除图片目录
    img_dir = parsed_dir / f"{name}_images"
    if img_dir.exists():
        shutil.rmtree(str(img_dir))
    return {"success": True}


@router.get("/courses/{course_id}/transcripts/{name}/download")
async def download_transcript(course_id: str, name: str):
    """下载转录 TXT 文件。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    file_path = cm.sub_dir(course_id, "transcripts") / f"{name}_transcript.txt"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(file_path), media_type="text/plain",
                        filename=f"{name}_transcript.txt")


@router.get("/courses/{course_id}/documents/{name}/download")
async def download_document(course_id: str, name: str):
    """下载文档 MD 文件。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    parsed_dir = cm.sub_dir(course_id, "parsed_docs")
    file_path = parsed_dir / f"{name}.md"
    if not file_path.exists():
        # 尝试在子目录中查找
        sub_file = parsed_dir / name / f"{name}.md"
        if sub_file.exists():
            file_path = sub_file
        else:
            raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(file_path), media_type="text/markdown",
                        filename=f"{name}.md")


@router.get("/courses/{course_id}/images/{doc}/{file}")
async def serve_image(course_id: str, doc: str, file: str):
    """提供解析产出的图片（防目录遍历）。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    # 安全检查：防止 .. 路径遍历
    if ".." in doc or ".." in file:
        raise HTTPException(status_code=400, detail="非法路径")

    parsed_dir = cm.sub_dir(course_id, "parsed_docs")
    img_path = parsed_dir / f"{doc}_images" / file

    if not img_path.exists():
        # 也尝试在子目录中查找
        alt_path = parsed_dir / doc / "images" / file
        if alt_path.exists():
            img_path = alt_path
        else:
            raise HTTPException(status_code=404, detail="图片不存在")

    # 根据扩展名确定 media type
    ext = Path(file).suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    return FileResponse(str(img_path), media_type=media_types.get(ext, "application/octet-stream"))


@router.get("/courses/{course_id}/materials")
async def get_materials(course_id: str):
    """返回指定课程的所有已保存资料（含内容）。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    materials = cm.list_review_materials(course_id)
    result = []
    for m in materials:
        content = cm.load_review_material(course_id, m.filename)
        result.append({
            "filename": m.filename,
            "material_type": m.material_type,
            "display_name": m.display_name,
            "created_at": m.created_at,
            "char_count": m.char_count,
            "content": content or "",
        })
    return {"materials": result}


@router.get("/courses/{course_id}/sources")
async def get_sources(course_id: str):
    """返回课程的可用源材料（转录 + 课件）。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    transcripts, docs = _scan_sources(course_id)
    return {
        "transcripts": [{"name": t["name"], "char_count": t["char_count"]} for t in transcripts],
        "docs": [{"name": d["name"], "char_count": d["char_count"]} for d in docs],
    }


@router.delete("/courses/{course_id}/materials/{filename}")
async def delete_material(course_id: str, filename: str):
    """删除指定资料文件。"""
    import os
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    file_path = cm.sub_dir(course_id, "review_materials") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="资料不存在")
    os.remove(str(file_path))
    return {"success": True}


@router.get("/courses/{course_id}/materials/{filename}/download")
async def download_material(course_id: str, filename: str):
    """下载资料 MD 文件。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    file_path = cm.sub_dir(course_id, "review_materials") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="资料不存在")
    return FileResponse(str(file_path), media_type="text/markdown",
                        filename=filename)
