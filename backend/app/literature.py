import httpx
import asyncio
from typing import List, Dict, Optional

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class LiteratureAgent:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def search_papers(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Searches Semantic Scholar for relevant papers.
        """
        # Exclude generic terms to improve relevance if needed,
        # but SS is usually good with natural language.
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,abstract,authors,year,citationCount,venue,url,tldr,openAccessPdf",
        }

        try:
            resp = await self.client.get(SEMANTIC_SCHOLAR_API_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return self._format_papers(data.get("data", []))
            else:
                print(f"SS Search Error: {resp.status_code} - {resp.text}")
                return []
        except Exception as e:
            print(f"Literature Search Exception: {e}")
            return []

    def _format_papers(self, raw_papers: List[Dict]) -> List[Dict]:
        formatted = []
        for p in raw_papers:
            authors = [a["name"] for a in p.get("authors", [])[:3]]  # Top 3 authors
            if len(p.get("authors", [])) > 3:
                authors.append("et al.")

            formatted.append(
                {
                    "id": p.get("paperId"),
                    "title": p.get("title"),
                    "abstract": p.get("abstract")
                    or p.get("tldr", {}).get("text", "No abstract available."),
                    "authors": ", ".join(authors),
                    "year": p.get("year"),
                    "citations": p.get("citationCount", 0),
                    "journal": p.get("venue") or "Preprint/Unknown",
                    "url": p.get("openAccessPdf", {}).get("url") or p.get("url"),
                    "source": "Semantic Scholar",
                }
            )
        return formatted


# Test standalone
if __name__ == "__main__":

    async def test():
        agent = LiteratureAgent()
        papers = await agent.search_papers("KRAS G12C resistance mechanisms")
        print(f"Found {len(papers)} papers")
        for p in papers:
            print(f"- {p['title']} ({p['year']})")

    asyncio.run(test())
