"""
Web search and source processing package.
"""
from bot.web.search import search_engine, WebSearchEngine
from bot.web.sources import source_formatter, SourceFormatter

__all__ = ["search_engine", "WebSearchEngine", "source_formatter", "SourceFormatter"]
