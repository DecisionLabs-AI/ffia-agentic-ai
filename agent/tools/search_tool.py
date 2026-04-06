# =============================================================================
# FFIA — Web Search Tool (W2)
# Allows the ReAct agent to look up current oil prices, Thai fuel news, etc.
# Default: DuckDuckGo (no API key). Upgrade: set TAVILY_API_KEY in .env.
# =============================================================================

# Step 1: Imports
import os
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()


# Step 2: Build the search backend — auto-upgrades to Tavily if key is present
def _build_search_func():
    """Return the best available search backend."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        # Step 2a: Tavily path (structured results, better quality)
        from langchain_community.tools.tavily_search import TavilySearchResults
        tavily = TavilySearchResults(max_results=5, api_key=tavily_key)
        return lambda query: str(tavily.invoke(query))
    else:
        # Step 2b: DuckDuckGo path (free, no API key required)
        from langchain_community.tools import DuckDuckGoSearchRun
        ddg = DuckDuckGoSearchRun()
        return ddg.run

# Step 2b: Lazy singleton — backend is built only on first search, not at import time
_search_func = None


# Step 3: Define tool using @tool decorator (LangChain 1.x compatible)
@tool
def search_tool(query: str) -> str:
    """Search for real-time information about Bangkok oil prices, Thai diesel or
    gasohol fuel costs, restaurant industry news in Thailand, or current events
    affecting food costs. Input should be a focused English search query.
    Example: 'Bangkok diesel price today THB'
    """
    # Step 3a: Initialize search backend on first call (lazy — avoids import-time cost)
    global _search_func
    if _search_func is None:
        _search_func = _build_search_func()
    return _search_func(query)


# Step 4: Standalone test block
if __name__ == "__main__":
    print("Testing Web Search tool...")
    result = search_tool.invoke("Bangkok diesel price today Thailand")
    print(result)
