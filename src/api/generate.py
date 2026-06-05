"""SSE 流式生成复习资料 — 从 review_api.py 提取。"""

import json
import logging
import re
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .deps import get_cm, get_config_obj
from .materials import _scan_sources
from src.llm.factory import get_llm
from src.llm.prompts import build_generation_prompt
from src.llm.latex_utils import normalize_latex
from src.llm.section_split import split_by_sections
from src.merger.content_merger import ContentMerger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/courses/{course_id}/generate")
async def generate_material(course_id: str, request: Request):
    """SSE 流式生成复习资料。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    body = await request.json()
    material_types: list[str] = body.get("material_types", ["复习提纲（核心概念 + 重点/难点标注 + 公式定理）"])
    custom_extra: str = body.get("custom_extra", "")

    transcripts, docs = _scan_sources(course_id)

    if not transcripts and not docs:
        raise HTTPException(status_code=400, detail="该课程没有任何源材料，请先上传课堂录音或课件。")

    async def event_stream():
        try:
            merger = ContentMerger()
            merged = merger.merge(
                transcript="\n\n".join(t["text"] for t in transcripts) if transcripts else None,
                parsed_docs=[d["text"] for d in docs] if docs else None,
            )

            merged_dir = cm.sub_dir(course_id, "merged")
            merged_dir.mkdir(parents=True, exist_ok=True)
            merged_file = merged_dir / "merged_content.md"
            merger.to_markdown(merged, merged_file)

            config = get_config_obj()
            llm = get_llm(config.llm)
            prompt = build_generation_prompt(merged.content, material_types, custom_extra)

            full_output = ""
            max_passes = 3

            for pass_num in range(1, max_passes + 1):
                if pass_num == 1:
                    yield f"data: {json.dumps({'type': 'status', 'message': '正在生成...'})}\n\n"
                    current_messages = [{"role": "user", "content": prompt}]
                else:
                    yield f"data: {json.dumps({'type': 'status', 'message': f'内容较长，正在续写（第{pass_num}轮）...'})}\n\n"
                    current_messages = [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": full_output},
                        {
                            "role": "user",
                            "content": (
                                "你的输出因长度限制被截断，请从最后一个被截断的字/词/公式处继续。\n\n"
                                "规则：\n"
                                "1. 不要重复已经写过的任何内容，直接从断点接着写\n"
                                "2. 保持和上文完全一致的 Markdown 层级结构\n"
                                "3. 不要添加任何问候语、祝福语、总结语或开场白\n"
                                "4. 如果上一个字或公式被截断，先补全它\n"
                                "5. 所有要求的部分都生成完毕后，回复「[生成完毕]」"
                            ),
                        },
                    ]

                pass_content = ""
                stream = llm.stream_chat(current_messages, temperature=0.3, max_tokens=None)
                for chunk in stream:
                    pass_content += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                full_output += pass_content

                if len(pass_content) < 1500:
                    break
                if "[生成完毕]" in pass_content:
                    full_output = full_output.replace("[生成完毕]", "")
                    break

            # 清理尾部
            _closing_patterns = [
                r"\n*祝[^\n]{0,30}考试[^\n]{0,20}(?:顺利|成功)[^\n]*[！!。.]?",
                r"\n*希望[^\n]{0,30}(?:帮助|有用|顺利)[^\n]*[！!。.]?",
                r"\n*好的，?我们继续[^\n]*\n*",
            ]
            for pat in _closing_patterns:
                full_output = re.sub(pat, "", full_output)

            full_output = normalize_latex(full_output)

            sections = split_by_sections(full_output, material_types)
            saved_materials = []
            for type_name, content in sections:
                file_path = cm.save_review_material(course_id, type_name, content)
                saved_materials.append({"material_type": type_name, "display_name": type_name, "file": str(file_path)})
                if len(sections) > 1:
                    time.sleep(0.05)

            if not saved_materials:
                primary_type = material_types[0]
                for kw in ["复习提纲", "详细笔记", "知识结构图", "自测题库"]:
                    if kw in primary_type:
                        primary_type = kw
                        break
                file_path = cm.save_review_material(course_id, primary_type, full_output)
                saved_materials.append({"material_type": primary_type, "display_name": primary_type, "file": str(file_path)})

            yield f"data: {json.dumps({'type': 'done', 'materials': saved_materials, 'total_chars': len(full_output)})}\n\n"

        except Exception as e:
            logger.exception("Generation failed for course %s", course_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
