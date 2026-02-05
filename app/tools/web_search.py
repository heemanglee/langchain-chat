"""Web search tool using DuckDuckGo."""

from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web for current information.

    Use this tool when you need to find up-to-date information
    from the internet, such as current events, weather, news, etc.

    Args:
        query: The search query string.

    Returns:
        Search results containing snippets, titles, and links.
    """
    search = DuckDuckGoSearchResults(num_results=5)
    result = search.invoke(query)
    return str(result)
