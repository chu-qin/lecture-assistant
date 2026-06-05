"""复习与问答 API — FastAPI 路由（向后兼容包装）。

所有业务逻辑已迁移至:
  - src/llm/latex_utils.py   — LaTeX 扫描器
  - src/llm/prompts.py        — Prompt 构建
  - src/llm/section_split.py  — LLM 输出拆分
  - src/api/courses.py        — 课程 CRUD
  - src/api/materials.py      — 资料管理（含 _scan_sources）
  - src/api/generate.py       — SSE 生成
  - src/api/chat.py           — SSE 问答 + 知识库管理
  - src/api/asr_routes.py     — ASR 转录
  - src/api/parser_routes.py  — 课件解析 + EPUB 导入
  - src/api/server.py         — App 工厂

本文件保留以下向后兼容的公开符号，供 Streamlit 页面导入:
  - app（从 server.py 导入，含所有路由）
  - _normalize_latex, _scan_math_delimiters（从 latex_utils 导入）
  - _build_type_sections, _build_generation_prompt（从 prompts 导入）
  - _split_by_sections, _CN_NUMS, _CN_SECTION_MAP
"""

import logging

from src.api.server import app
from src.llm.latex_utils import normalize_latex as _normalize_latex
from src.llm.latex_utils import scan_math_delimiters as _scan_math_delimiters
from src.llm.prompts import build_type_sections as _build_type_sections
from src.llm.prompts import build_generation_prompt as _build_generation_prompt
from src.llm.section_split import split_by_sections as _split_by_sections

_CN_NUMS = "一二三四五六七八九十"
_CN_SECTION_MAP = {"一": "复习提纲", "二": "详细笔记", "三": "知识结构图", "四": "自测题库"}

logger = logging.getLogger(__name__)
