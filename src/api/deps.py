"""FastAPI 共享依赖 — 配置、CourseManager 单例。"""

from src.config import get_config
from src.course_manager import CourseManager

_config = get_config()
_cm = CourseManager(_config.project.data_dir)


def get_cm() -> CourseManager:
    return _cm


def get_config_obj():
    return _config
