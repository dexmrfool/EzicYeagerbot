from typing import List, Dict


class SourceFormatter:
    """Formats and summarizes search results for the Butler AI."""

    @staticmethod
    def format_for_prompt(results: List[Dict[str, str]]) -> str:
        if not results:
            return "No real-time web search results found."

        formatted_lines = ["\n[Real-time Web Search Results]:"]
        for idx, item in enumerate(results, 1):
            title = item.get("title", f"Source {idx}").strip()
            snippet = item.get("snippet", "").strip()
            formatted_lines.append(f"{idx}. {title}: {snippet}")

        formatted_lines.append("\nGround your answer strictly on the above facts. If information is absent or conflicting, acknowledge that the update could not be verified rather than guessing.")
        return "\n".join(formatted_lines)


source_formatter = SourceFormatter()
