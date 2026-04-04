# =============================================================================
# FFIA — Web Search Tool (W2)
# Allows the ReAct agent to look up current oil prices, Thai fuel news, etc.
# Default: DuckDuckGo (no API key). Upgrade: set TAVILY_API_KEY in .env.
# =============================================================================

# Step 1: Imports
import os
from dotenv import load_dotenv
from langchain.tools import Tool

load_dotenv()


# Step 2: Build the search function — auto-upgrades to Tavily if key is present
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


_search_func = _build_search_func()


# Step 3: Wrap in LangChain Tool for the ReAct agent
search_tool = Tool(
    name="WebSearch",
    func=_search_func,
    description=(
        "Use this tool to search for real-time information about Bangkok oil prices, "
        "Thai diesel/gasohol fuel costs, restaurant industry news in Thailand, "
        "or any current events affecting food costs. "
        "Input should be a focused English search query. "
        "Example: 'Bangkok diesel price today THB' or 'Thailand cooking oil cost 2024'"
    ),
)


# Step 4: Standalone test block
if __name__ == "__main__":
    print("Testing Web Search tool...")
    result = search_tool.func("Bangkok diesel price today Thailand")
    print(result)
