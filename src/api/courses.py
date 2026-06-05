"""课程 CRUD 路由。"""

from fastapi import APIRouter, HTTPException

from .deps import get_cm

router = APIRouter(prefix="/api")


@router.get("/courses")
async def list_courses():
    """返回课程列表，含每门课的统计信息。"""
    cm = get_cm()
    courses = cm.list_courses()
    result = []
    for name in courses:
        stats = cm.get_review_stats(name)
        result.append({
            "name": name,
            "audio_files": stats["audio_files"],
            "courseware_files": stats["courseware_files"],
            "transcripts": stats["transcripts"],
            "review_materials": stats["review_materials"],
            "kb_ready": stats["vector_store_ready"],
        })
    return {"courses": result}


@router.post("/courses")
async def create_course(body: dict):
    """创建新课程。"""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="课程名不能为空")
    cm = get_cm()
    if name in cm.list_courses():
        raise HTTPException(status_code=409, detail=f"课程已存在: {name}")
    cm.create_course(name)
    return {"success": True, "name": name}


@router.delete("/courses/{course_id}")
async def delete_course(course_id: str):
    """删除课程。"""
    cm = get_cm()
    if course_id not in cm.list_courses():
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")
    cm.delete_course(course_id)
    return {"success": True}
