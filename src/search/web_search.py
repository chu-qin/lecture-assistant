"""DDGS 联网搜索，零 API Key，无配额限制。"""

from ddgs import DDGS


def search_web(query: str, max_results: int = 3) -> list[dict]:
    """搜索网络，返回 title/body/href 列表。失败时返回空列表。"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r["title"], "body": r["body"], "href": r["href"]} for r in results]
    except Exception:
        return []
