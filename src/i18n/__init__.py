"""i18n 国际化 — 轻量 JSON 方案，不依赖 gettext。"""

import json
from pathlib import Path

import streamlit as st

_LOCALE_DIR = Path(__file__).resolve().parent
_cache: dict[str, dict[str, str]] = {}


def _load(lang: str) -> dict[str, str]:
    """加载语言文件，带内存缓存。"""
    if lang in _cache:
        return _cache[lang]
    fp = _LOCALE_DIR / f"{lang}.json"
    if not fp.exists():
        fp = _LOCALE_DIR / "zh.json"
    with open(fp, encoding="utf-8") as f:
        _cache[lang] = json.load(f)
    return _cache[lang]


def t(key: str, **kwargs: object) -> str:
    """获取翻译文本，支持 ``{param}`` 格式化占位符。"""
    lang = get_language()
    translations = _load(lang)
    text = translations.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def set_language(lang: str) -> None:
    """切换语言（写入 session_state）。"""
    st.session_state["language"] = lang


def get_language() -> str:
    """获取当前语言，默认 zh。"""
    return st.session_state.get("language", "zh")


def get_available_languages() -> dict[str, str]:
    """返回可用语言 {code: native_name}。"""
    return {"zh": "中文", "en": "English"}
