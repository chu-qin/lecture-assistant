"""LLM output section splitting utilities.

Extracted from review_api.py and pages/2_复习与问答.py to eliminate duplication.
"""

import re

_CN_NUMS = "一二三四五六七八九十"
_CN_SECTION_MAP = {"一": "复习提纲", "二": "详细笔记", "三": "知识结构图", "四": "自测题库"}


def split_by_sections(full_output: str, generate_types: list[str]) -> list[tuple[str, str]]:
    """按 ## N、section 标题拆分 LLM 输出，返回 [(type_name, content), ...]。

    只保留 generate_types 中已勾选的类型，按原始顺序返回。
    """
    pattern = r"\n(?=## [" + _CN_NUMS + r"]、)"
    raw_parts = re.split(pattern, full_output)

    result: list[tuple[str, str]] = []
    seen_types: set[str] = set()
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"## ([" + _CN_NUMS + r"])、", part)
        if not m:
            if result:
                name, content = result[0]
                result[0] = (name, content + "\n\n" + part)
            continue
        cn = m.group(1)
        type_name = _CN_SECTION_MAP.get(cn)
        if (
            type_name
            and type_name not in seen_types
            and any(type_name in gt for gt in generate_types)
        ):
            seen_types.add(type_name)
            result.append((type_name, part))

    return result
