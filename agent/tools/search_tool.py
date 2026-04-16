# =============================================================================
# FFIA — Web Search Tool (W2)
# Allows the ReAct agent to look up current oil prices, Thai fuel news, etc.
# Default: DuckDuckGo (no API key). Upgrade: set TAVILY_API_KEY in .env.
# =============================================================================

# Step 1: Imports
import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()


SAFE_SEARCH_FALLBACK = (
    "No trustworthy external web source was found for this request. "
    "Do not cite or surface any web search results. "
    "Continue with PostgreSQL or the appropriate FFIA internal tool when available. "
    "If no internal source can answer it, tell the user clearly that no trustworthy external source was found "
    "and continue with the safest internal explanation or clarification."
)

SEARCH_BLOCKED_FALLBACK = (
    "Web search is disabled for this request. "
    "Do not cite or surface any web search results. "
    "Use PostgreSQL or the appropriate FFIA internal tool instead. "
    "If the request needs an ingredient price that FFIA does not already have, ask the user for their actual purchase price."
)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "bangkok", "cost", "costs", "current",
    "event", "events", "for", "from", "general", "in", "info", "information",
    "latest", "market", "news", "of", "on", "price", "prices", "restaurant",
    "restaurants", "thailand", "thai", "the", "today", "trend", "trends", "what",
}
_ALLOWED_RESULT_DOMAINS = {
    "siammakro.co.th",
    "makro.pro",
    "moc.go.th",
    "dit.go.th",
    "lotuss.com",
    "bigc.co.th",
}
_BLOCKED_QUERY_RULES = [
    (
        re.compile(
            r"(ingredient|ingredients|food price|food prices|seafood|meat|vegetable|"
            r"วัตถุดิบ|ราคาอาหาร|ราคาวัตถุดิบ|ราคาผัก|ราคาเนื้อ|ราคาทะเล)",
            re.IGNORECASE,
        ),
        "ingredient pricing belongs to internal data or user-provided actual purchase prices",
    ),
    (
        re.compile(
            r"(cost calculation|costing|calculate cost|cogs|ต้นทุน|คำนวณต้นทุน|food cost)",
            re.IGNORECASE,
        ),
        "cost calculations must stay on internal FFIA logic",
    ),
    (
        re.compile(
            r"(margin analysis|profitability|gross margin|net margin|repric|"
            r"วิเคราะห์กำไร|มาร์จิ้น|กำไรขั้นต้น|กำไรสุทธิ)",
            re.IGNORECASE,
        ),
        "margin analysis must stay on internal FFIA logic",
    ),
    (
        re.compile(
            r"(postgres|sql|database|invoice|platform fee|restaurant_channel_mix|"
            r"platform_fee|business rule|promo|promotion viability|diesel|fuel|oil price|"
            r"invoice_items|restaurant profile|โปรไฟล์ร้าน|ฐานข้อมูล|ใบแจ้งหนี้|ค่าน้ำมัน|ค่าน้ำมันดีเซล)",
            re.IGNORECASE,
        ),
        "this request should use PostgreSQL or an existing FFIA tool",
    ),
]


# Step 2: Build the search backend — auto-upgrades to Tavily if key is present
def _build_search_func():
    """Return the best available search backend."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        # Step 2a: Tavily path (structured results, better quality)
        from langchain_community.tools.tavily_search import TavilySearchResults
        tavily = TavilySearchResults(max_results=5, api_key=tavily_key)
        return tavily.invoke
    else:
        # Step 2b: DuckDuckGo path (free, no API key required) with structured list output
        from langchain_community.tools import DuckDuckGoSearchResults
        ddg = DuckDuckGoSearchResults(num_results=5, output_format="list")
        return ddg.invoke

# Step 2b: Lazy singleton — backend is built only on first search, not at import time
_search_func = None


def _normalize_text(value) -> str:
    """Flatten any result payload to lowercase text for relevance checks."""
    if isinstance(value, dict):
        return " ".join(_normalize_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_normalize_text(item) for item in value)
    return str(value)


def _query_tokens(query: str) -> set[str]:
    """Return meaningful tokens from the query for relevance matching."""
    tokens = {
        token
        for token in re.findall(r"[a-zA-Z0-9ก-๙]{3,}", query.lower())
        if token not in _STOPWORDS
    }
    return tokens


def _augment_query_for_allowed_domains(query: str) -> str:
    """Bias the search backend toward the approved source domains only."""
    domain_filters = " OR ".join(
        f"site:{domain}" for domain in sorted(_ALLOWED_RESULT_DOMAINS)
    )
    return f"{query} ({domain_filters})"


def _is_blocked_query(query: str) -> bool:
    """Block search usage for requests that must use internal tools or logic."""
    normalized_query = query.strip()
    return any(pattern.search(normalized_query) for pattern, _ in _BLOCKED_QUERY_RULES)


def _extract_result_url(result: dict) -> str:
    """Extract the best available URL field from a result payload."""
    return str(result.get("url") or result.get("link") or "").strip()


def _is_allowed_result_domain(url: str) -> bool:
    """Allow only Makro, Ministry of Commerce, Lotus's, and Big C domains."""
    if not url:
        return False

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in _ALLOWED_RESULT_DOMAINS
    )


def _looks_trustworthy_result(query: str, result: dict) -> bool:
    """Return True only for results that are relevant and free of obvious junk."""
    combined_text = _normalize_text(result).lower()
    if not combined_text.strip():
        return False
    if not _is_allowed_result_domain(_extract_result_url(result)):
        return False

    query_terms = _query_tokens(query)
    if not query_terms:
        return False

    matches = sum(1 for token in query_terms if token in combined_text)
    minimum_matches = 1 if len(query_terms) <= 2 else 2
    return matches >= minimum_matches


def _filter_search_results(query: str, raw_results) -> list[dict]:
    """Keep only trustworthy and relevant web results."""
    candidate_results = raw_results if isinstance(raw_results, list) else [raw_results]
    safe_results = []
    for item in candidate_results:
        normalized_item = item if isinstance(item, dict) else {"snippet": str(item)}
        if _looks_trustworthy_result(query, normalized_item):
            safe_results.append(normalized_item)
    return safe_results


def _format_safe_results(results: list[dict]) -> str:
    """Format filtered search results into a compact tool observation."""
    formatted_results = []
    for index, result in enumerate(results[:3], start=1):
        title = str(
            result.get("title")
            or result.get("snippet")
            or result.get("content")
            or result.get("body")
            or "Untitled result"
        ).strip()
        link = _extract_result_url(result)
        snippet = str(
            result.get("content")
            or result.get("snippet")
            or result.get("body")
            or ""
        ).strip()
        parts = [f"{index}. {title}"]
        if link:
            parts.append(f"URL: {link}")
        if snippet and snippet != title:
            parts.append(f"Snippet: {snippet}")
        formatted_results.append("\n".join(parts))
    return "Trusted web search results:\n" + "\n\n".join(formatted_results)


# Step 3: Define tool using @tool decorator (LangChain 1.x compatible)
@tool
def search_tool(query: str) -> str:
    """Search for real-time information about Bangkok oil prices, Thai diesel or
    gasohol fuel costs, restaurant industry news in Thailand, or current events
    affecting food costs. Input should be a focused English search query.
    Example: 'Bangkok diesel price today THB'
    """
    if _is_blocked_query(query):
        return SEARCH_BLOCKED_FALLBACK

    # Step 3a: Initialize search backend on first call (lazy — avoids import-time cost)
    global _search_func
    if _search_func is None:
        _search_func = _build_search_func()

    try:
        raw_results = _search_func(_augment_query_for_allowed_domains(query))
    except Exception:
        return SAFE_SEARCH_FALLBACK

    safe_results = _filter_search_results(query, raw_results)
    if not safe_results:
        return SAFE_SEARCH_FALLBACK

    return _format_safe_results(safe_results)


# Step 4: Standalone test block
if __name__ == "__main__":
    print("Testing Web Search tool...")
    result = search_tool.invoke("Bangkok diesel price today Thailand")
    print(result)
