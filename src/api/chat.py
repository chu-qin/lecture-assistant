"""SSE 流式 RAG 问答 + 知识库管理 — 从 review_api.py 提取。"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .deps import get_cm, get_config_obj
from src.llm.factory import get_llm
from src.llm.latex_utils import normalize_latex

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/courses/{course_id}/chat")
async def chat(course_id: str, request: Request):
    """SSE 流式 RAG 问答。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    body = await request.json()
    message: str = body.get("message", "")
    history: list[dict] = body.get("history", [])

    if not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    state = cm.load_state(course_id)
    if not state.vector_store_ready:
        raise HTTPException(status_code=400, detail="知识库未构建，请先生成或导入复习资料。")

    async def event_stream():
        try:
            from src.knowledge.chroma_store import ChromaVectorStore
            from src.knowledge.embedder import get_embedder

            config = get_config_obj()
            embedder = get_embedder(config.embedding)

            chroma_config = config.chromadb
            chroma_config.persist_directory = str(cm.chroma_dir(course_id))
            chroma_config.collection_name = cm.sanitize_collection_name(course_id)
            store = ChromaVectorStore(chroma_config, embedder)

            raw_filter = {"source_type": {"$in": ["transcript", "courseware"]}}
            review_filter = {"source_type": "review"}

            raw_results = store.search(message, top_k=5, where=raw_filter)
            review_results = store.search(message, top_k=3, where=review_filter)
            all_results = raw_results + review_results

            source_label_map = {
                "transcript": "课堂录音",
                "courseware": "课件",
                "review": "复习资料",
            }
            context_parts = []
            sources = []
            for r in all_results:
                source_type = r.metadata.get("source_type", "未知")
                source_label = source_label_map.get(source_type, source_type)
                context_parts.append(
                    f"[来源类型: {source_label}"
                    f" | 文件: {r.metadata.get('source_file', '未知')}]\n{r.content}"
                )
                sources.append({
                    "source_file": r.metadata.get("source_file", "未知"),
                    "source_type": source_type,
                    "score": round(r.score, 4),
                    "content": r.content,
                })

            context = "\n\n---\n\n".join(context_parts)

            # 联网搜索
            try:
                from src.search.web_search import search_web

                web_results = search_web(message, max_results=3)
                if web_results:
                    web_parts = []
                    for wr in web_results:
                        web_parts.append(
                            f"[网络搜索 | {wr['title']} | {wr['href']}]\n{wr['body']}"
                        )
                    web_context = "\n\n---\n\n".join(web_parts)
                    context = context + "\n\n## 网络搜索结果（仅供参考，非课程材料）\n\n" + web_context
            except Exception:
                pass

            llm = get_llm(config.llm)
            system_prompt = llm.load_prompt("qa_system.txt", context=context)

            messages = [{"role": "system", "content": system_prompt}]
            for h in history[-10:]:
                if h.get("role") != "system":
                    messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            full_response = ""
            stream = llm.stream_chat(messages)
            for chunk in stream:
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'content': normalize_latex(full_response), 'sources': sources})}\n\n"

        except Exception as e:
            logger.exception("Chat failed for course %s", course_id)
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


# ---- 知识库管理 ----

@router.post("/courses/{course_id}/build-kb")
async def build_kb(course_id: str):
    """构建/重建知识库（SSE 进度）。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    async def event_stream():
        try:
            from src.knowledge.chroma_store import ChromaVectorStore
            from src.knowledge.embedder import get_embedder
            from src.knowledge.chunker import MarkdownChunker

            config = get_config_obj()
            embedder = get_embedder(config.embedding)

            chroma_config = config.chromadb
            chroma_config.persist_directory = str(cm.chroma_dir(course_id))
            chroma_config.collection_name = cm.sanitize_collection_name(course_id)
            store = ChromaVectorStore(chroma_config, embedder)

            yield f"data: {json.dumps({'type': 'status', 'phase': 'clearing', 'message': '正在清空旧知识库...'})}\n\n"
            store.delete_collection()

            # 扫描源材料
            from .materials import _scan_sources
            transcripts, docs = _scan_sources(course_id)

            yield f"data: {json.dumps({'type': 'status', 'phase': 'chunking', 'message': f'正在分块...（转录 {len(transcripts)} 份 + 课件 {len(docs)} 份）'})}\n\n"

            chunker = MarkdownChunker()
            all_chunks = []

            # 转录分块
            for t in transcripts:
                chunks = chunker.chunk_text(t["text"], {"source_type": "transcript", "source_file": t["name"]})
                all_chunks.extend(chunks)

            # 课件分块
            for d in docs:
                chunks = chunker.chunk_text(d["text"], {"source_type": "courseware", "source_file": d["name"]})
                all_chunks.extend(chunks)

            # 复习资料分块
            review_materials = cm.list_review_materials(course_id)
            for m in review_materials:
                content = cm.load_review_material(course_id, m.filename)
                if content:
                    chunks = chunker.chunk_text(content, {"source_type": "review", "source_file": m.display_name})
                    all_chunks.extend(chunks)

            yield f"data: {json.dumps({'type': 'status', 'phase': 'embedding', 'message': f'正在向量化 {len(all_chunks)} 个文本块...', 'total': len(all_chunks)})}\n\n"

            if all_chunks:
                for i in range(0, len(all_chunks), 50):
                    batch = all_chunks[i:i + 50]
                    texts = [c.text for c in batch]
                    metadatas = [c.metadata for c in batch]
                    ids = [str(uuid.uuid4()) for _ in batch]
                    store.add_documents(texts, metadatas, ids)
                    progress = min(100, round((i + len(batch)) / len(all_chunks) * 100))
                    yield f"data: {json.dumps({'type': 'status', 'phase': 'embedding', 'message': f'向量化中... {progress}%', 'progress': progress})}\n\n"

            # 更新状态
            state = cm.load_state(course_id)
            state.vector_store_ready = True
            cm.save_state(course_id, state)

            yield f"data: {json.dumps({'type': 'done', 'doc_count': len(all_chunks)})}\n\n"

        except Exception as e:
            logger.exception("KB build failed for course %s", course_id)
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


@router.get("/courses/{course_id}/kb-status")
async def kb_status(course_id: str):
    """查询知识库状态。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    state = cm.load_state(course_id)
    return {"ready": state.vector_store_ready, "doc_count": getattr(state, 'doc_count', 0) if state.vector_store_ready else 0}


@router.delete("/courses/{course_id}/kb")
async def clear_kb(course_id: str):
    """清空知识库。"""
    import shutil
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    chroma_dir = cm.chroma_dir(course_id)
    if chroma_dir.exists():
        shutil.rmtree(str(chroma_dir))
    chroma_dir.mkdir(parents=True, exist_ok=True)

    state = cm.load_state(course_id)
    state.vector_store_ready = False
    cm.save_state(course_id, state)

    return {"success": True}
