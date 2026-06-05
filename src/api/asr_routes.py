"""ASR 转录路由 — multipart 上传 + SSE 进度。"""

import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse

from .deps import get_cm, get_config_obj
from src.asr.funasr_asr import get_asr_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/courses/{course_id}/transcribe")
async def transcribe(
    course_id: str,
    files: list[UploadFile] = File(...),
):
    """上传音频文件并转录（SSE 流式进度）。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    async def event_stream():
        config = get_config_obj()
        audio_dir = cm.sub_dir(course_id, "audio")
        transcripts_dir = cm.sub_dir(course_id, "transcripts")
        audio_dir.mkdir(parents=True, exist_ok=True)
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        # 保存上传的文件
        saved_files = []
        for f in files:
            file_path = audio_dir / (f.filename or f"audio_{len(saved_files)}.m4a")
            content = await f.read()
            file_path.write_bytes(content)
            saved_files.append(file_path)
            yield f"data: {json.dumps({'type': 'status', 'phase': 'saved', 'file': str(file_path.name), 'message': f'已保存: {file_path.name}'})}\n\n"

        if not saved_files:
            yield f"data: {json.dumps({'type': 'error', 'message': '没有上传文件'})}\n\n"
            return

        # 加载模型
        yield f"data: {json.dumps({'type': 'status', 'phase': 'loading_model', 'message': '正在加载 ASR 模型...'})}\n\n"
        try:
            asr = get_asr_model(config.asr)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'ASR 模型加载失败: {e}'})}\n\n"
            return

        # 逐文件转录
        results = []
        for idx, fpath in enumerate(saved_files):
            yield f"data: {json.dumps({'type': 'status', 'phase': 'transcribing', 'file': fpath.name, 'index': idx + 1, 'total': len(saved_files)})}\n\n"
            try:
                result = asr.transcribe(str(fpath))
                # 保存转录文本
                stem = fpath.stem
                txt_path = transcripts_dir / f"{stem}_transcript.txt"
                txt_path.write_text(result.text, encoding="utf-8")
                # 保存 JSON（含分段信息）
                json_path = transcripts_dir / f"{stem}_transcript.json"
                segments_data = [{"start": seg.start, "end": seg.end, "text": seg.text}
                                 for seg in result.segments] if result.segments else []
                json_path.write_text(json.dumps({
                    "text": result.text,
                    "segments": segments_data,
                    "duration_sec": result.duration_sec,
                }, ensure_ascii=False, indent=2), encoding="utf-8")

                yield f"data: {json.dumps({'type': 'result', 'file': fpath.name, 'text': result.text[:500] + ('...' if len(result.text) > 500 else ''), 'segments': len(result.segments) if result.segments else 0, 'duration_sec': result.duration_sec})}\n\n"
                results.append({"file": fpath.name, "text": result.text, "success": True})
            except Exception as e:
                logger.exception("ASR failed for %s", fpath.name)
                yield f"data: {json.dumps({'type': 'error', 'file': fpath.name, 'message': str(e)})}\n\n"
                results.append({"file": fpath.name, "text": "", "success": False})

        # 自动摘要（针对第一个成功的结果）
        if results and any(r["success"] for r in results):
            try:
                from src.llm.factory import get_llm

                yield f"data: {json.dumps({'type': 'status', 'phase': 'summarizing', 'message': '正在生成摘要...'})}\n\n"
                llm = get_llm(config.llm)
                summary_prompt = llm.load_prompt("summary_system.txt")
                first_text = next(r["text"] for r in results if r["success"])
                msgs = [
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": f"请为以下课堂录音内容生成摘要：\n\n{first_text[:4000]}"},
                ]
                summary = llm.chat(msgs, temperature=0.3, max_tokens=500)
                yield f"data: {json.dumps({'type': 'summary', 'text': summary})}\n\n"

                # 保存摘要
                stem = Path(results[0]["file"]).stem
                (transcripts_dir / f"{stem}_summary.txt").write_text(summary, encoding="utf-8")
            except Exception as e:
                logger.warning("Summary generation failed: %s", e)

        # 自动 AI 修正（如有课件则自动执行）
        try:
            parsed_dir = cm.sub_dir(course_id, "parsed_docs")
            parsed_files = list(parsed_dir.rglob("*.md"))
            if parsed_files:
                yield f"data: {json.dumps({'type': 'status', 'phase': 'correcting', 'message': '检测到课件，正在自动修正转录...'})}\n\n"
                from src.llm.factory import get_llm
                llm = get_llm(config.llm)

                for i, r in enumerate(results):
                    if not r["success"]:
                        continue
                    # 读取课件内容（取第一个或匹配的）
                    courseware_text = ""
                    for pf in parsed_files[:3]:
                        courseware_text += pf.read_text(encoding="utf-8")[:3000] + "\n\n"

                    original = r["text"][:6000]
                    correction_prompt = (
                        "你是一个语音转录校对专家。请根据课件内容修正以下语音转录中的专有名词、公式、术语错误。\n\n"
                        "规则：\n"
                        "1. 只修正明显的识别错误（专有名词、人名、公式符号等）\n"
                        "2. 不要改变原有语序和表达方式\n"
                        "3. 修正后的文本保持与原文大致相同的长度\n"
                        "4. 直接返回修正后的文本，不要添加任何解释\n\n"
                        f"## 课件参考内容\n\n{courseware_text}\n\n"
                        f"## 转录原文\n\n{original}\n\n"
                        "## 修正后的文本"
                    )
                    corrected = llm.chat(
                        [{"role": "user", "content": correction_prompt}],
                        temperature=0.2, max_tokens=4000
                    )

                    stem = Path(r["file"]).stem
                    (transcripts_dir / f"{stem}_corrected.txt").write_text(corrected, encoding="utf-8")

                    yield f"data: {json.dumps({'type': 'correction', 'file': r['file'], 'original': original[:500] + '...', 'corrected': corrected[:500] + '...', 'stem': stem})}\n\n"
        except Exception as e:
            logger.warning("AI correction failed: %s", e)

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


@router.post("/courses/{course_id}/transcripts/confirm-correction")
async def confirm_correction(course_id: str, body: dict):
    """确认或放弃 AI 修正。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    action = body.get("action", "discard")
    stem = body.get("stem", "")
    transcripts_dir = cm.sub_dir(course_id, "transcripts")

    if action == "confirm":
        corrected_file = transcripts_dir / f"{stem}_corrected.txt"
        original_file = transcripts_dir / f"{stem}_transcript.txt"
        if corrected_file.exists():
            corrected_text = corrected_file.read_text(encoding="utf-8")
            original_file.write_text(corrected_text, encoding="utf-8")
            corrected_file.unlink()
    elif action == "discard":
        corrected_file = transcripts_dir / f"{stem}_corrected.txt"
        if corrected_file.exists():
            corrected_file.unlink()

    return {"success": True}
