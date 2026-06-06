"""LaTeX delimiter normalization and scanning.

Extracted from review_api.py and pages/2_复习与问答.py to eliminate duplication.
"""

import re

_HTML_RE = re.compile(r"<[^>]+>")


_MATH_RE = re.compile(r"\$\$([\s\S]*?)\$\$|\$([^$\n]+?)\$")


def _fix_latex_commands(text: str) -> str:
    """替换 KaTeX 不识别的 LaTeX 命令（仅在 $...$ 区域内）。"""

    def _fix(m: re.Match) -> str:
        inner = m.group(0)
        # Dotless i/j (text-mode only, invalid in KaTeX math mode)
        inner = re.sub(r"\\i\b", "i", inner)
        inner = re.sub(r"\\j\b", "j", inner)
        # Differential d — LLM often writes \d{x} or \d
        inner = re.sub(r"\\d\{([^}]*)\}", r"\\mathrm{d}\1", inner)
        inner = re.sub(r"\\d\b", r"\\mathrm{d}", inner)
        # Degree symbol
        inner = re.sub(r"\\degree\b", r"^{\\circ}", inner)
        # Old-style font commands → modern equivalents
        inner = re.sub(r"\\rm\{([^}]*)\}", r"\\mathrm{\1}", inner)
        inner = re.sub(r"\\bf\{([^}]*)\}", r"\\mathbf{\1}", inner)
        inner = re.sub(r"\\it\{([^}]*)\}", r"\\textit{\1}", inner)
        # Unsupported packages
        inner = re.sub(r"\\mathds\{([^}]*)\}", r"\\mathbb{\1}", inner)
        # \bm (bold math, from bm package) → \boldsymbol
        inner = re.sub(r"\\bm\{([^}]*)\}", r"\\boldsymbol{\1}", inner)
        # \xlongequal{text} → \overset{\text{text}}{=}
        inner = re.sub(
            r"\\xlongequal\{([^}]*)\}", r"\\overset{\\text{\1}}{=}", inner
        )
        # \xlongequal (bare) → =
        inner = re.sub(r"\\xlongequal\b", "=", inner)
        # \coloneqq → \mathrel{:=} (KaTeX 0.17 should support, fallback)
        inner = re.sub(r"\\coloneqq\b", r"\\mathrel{:=}", inner)
        # \eqcolon → \mathrel{=:}
        inner = re.sub(r"\\eqcolon\b", r"\\mathrel{=:}", inner)
        # Remove \notag / \nonumber (only meaningful in LaTeX align environments)
        inner = re.sub(r"\\notag\b", "", inner)
        inner = re.sub(r"\\nonumber\b", "", inner)
        # \intertext{...} → \text{...} (intertext only works in align)
        inner = re.sub(r"\\intertext\{", r"\\text{", inner)
        return inner

    return _MATH_RE.sub(_fix, text)


def normalize_latex(content: str) -> str:
    """标准化 LaTeX 分隔符，未配对的 $ 转义为 \\$ 避免 KaTeX 报错。"""
    content = re.sub(r"\\\(\s*", "$", content)
    content = re.sub(r"\s*\\\)", "$", content)
    content = re.sub(r"\\\[\s*", "$$", content)
    content = re.sub(r"\s*\\\]", "$$", content)
    content = re.sub(r"([一-鿿　-〿＀-￯])\$", r"\1 $", content)
    content = re.sub(r"\$([一-鿿　-〿＀-￯])", r"$ \1", content)
    content = scan_math_delimiters(content)
    return _fix_latex_commands(content)


def scan_math_delimiters(text: str) -> str:
    """逐字符扫描：匹配 $...$ 和 $$...$$，剥离内部 HTML，转义未闭合的 $。"""
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        if i + 1 < n and text[i : i + 2] == "$$":
            closer = text.find("$$", i + 2)
            if closer != -1:
                inner = _HTML_RE.sub("", text[i + 2 : closer])
                result.append("$$" + inner + "$$")
                i = closer + 2
            else:
                result.append("\\$\\$")
                i += 2
            continue

        if text[i] == "$":
            j = i + 1
            found = False
            while j < n:
                if text[j] == "$":
                    if j + 1 < n and text[j : j + 2] == "$$":
                        closer2 = text.find("$$", j + 2)
                        if closer2 != -1:
                            j = closer2 + 2
                        else:
                            j += 2
                        continue
                    inner = _HTML_RE.sub("", text[i + 1 : j])
                    result.append("$" + inner + "$")
                    i = j + 1
                    found = True
                    break
                j += 1

            if not found:
                result.append("\\$")
                i += 1
            continue

        result.append(text[i])
        i += 1

    return "".join(result)
