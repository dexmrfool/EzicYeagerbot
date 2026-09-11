import asyncio
import re
from typing import List, Dict, Optional
import aiohttp
from bot.config import settings
from bot.utils.logging import logger


class WebSearchEngine:
    """
    Asynchronous web search provider.
    Supports free zero-key DuckDuckGo search, and pluggable Tavily API.
    """
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

    async def search(self, query: str, max_results: int = 4) -> List[Dict[str, str]]:
        """Performs an async search and returns list of {title, snippet, url}."""
        if not query.strip():
            return []

        # If Tavily key is present and configured, use Tavily
        if settings.WEB_SEARCH_PROVIDER == "tavily" and settings.WEB_SEARCH_API_KEY:
            try:
                return await self._search_tavily(query, max_results)
            except Exception as e:
                logger.warning(f"Tavily search failed ({e}). Falling back to DuckDuckGo...")

        # Default: Free DuckDuckGo search
        try:
            return await self._search_duckduckgo(query, max_results)
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    async def _search_duckduckgo(self, query: str, max_results: int = 4) -> List[Dict[str, str]]:
        """Queries DuckDuckGo HTML Lite asynchronously."""
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query}
        results = []

        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout, headers=self.headers) as session:
            async with session.post(url, data=data) as resp:
                if resp.status != 200:
                    logger.warning(f"DuckDuckGo returned HTTP {resp.status}")
                    return []
                html = await resp.text()

        # Parse snippets using fast regex (no heavy external HTML parser needed)
        # Matches result blocks
        blocks = re.findall(r'<div class="result__body">.*?</div>\s*</div>', html, re.DOTALL)
        if not blocks:
            # Alternative DDG pattern
            blocks = re.findall(r'<a class="result__snippet".*?href="([^"]+)".*?>(.*?)</a>', html, re.DOTALL)

        for block in blocks[:max_results]:
            if isinstance(block, str):
                # Extract title
                title_match = re.search(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>.*?</a>|<a class="result__a"[^>]*>(.*?)</a>', block, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_match.group(2) if title_match and title_match.group(2) else "Search Result").strip()

                # Extract snippet
                snippet_match = re.search(r'<a class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""

                # Extract link
                url_match = re.search(r'href="(//duckduckgo\.com/l/\?uddg=([^"&]+)|https?://[^"]+)"', block)
                link = url_match.group(1) if url_match else ""

                if snippet:
                    results.append({"title": title, "snippet": snippet, "url": link})

        return results

    async def _search_tavily(self, query: str, max_results: int = 4) -> List[Dict[str, str]]:
        """Tavily search API integration."""
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": settings.WEB_SEARCH_API_KEY,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic"
        }
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_results = data.get("results", [])
                    return [
                        {
                            "title": r.get("title", ""),
                            "snippet": r.get("content", ""),
                            "url": r.get("url", "")
                        }
                        for r in raw_results
                    ]
        return []


search_engine = WebSearchEngine()
