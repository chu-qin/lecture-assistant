"""FastAPI 应用工厂 + CORS + 静态文件挂载。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    app = FastAPI(title="Lecture Assistant API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 路由
    from .courses import router as courses_router
    from .materials import router as materials_router
    from .generate import router as generate_router
    from .chat import router as chat_router
    from .asr_routes import router as asr_router
    from .parser_routes import router as parser_router

    app.include_router(courses_router)
    app.include_router(materials_router)
    app.include_router(generate_router)
    app.include_router(chat_router)
    app.include_router(asr_router)
    app.include_router(parser_router)

    # Assets 静态文件 (review.html 等)
    _assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"
    _assets_dir.mkdir(exist_ok=True)
    app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    # 生产模式：serve 前端静态文件
    _frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if _frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

    return app


app = create_app()
