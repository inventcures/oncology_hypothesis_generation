import httpx
import asyncio
import os
from typing import List, Dict, Optional

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"

# API Key for higher rate limits (100 requests/sec vs 100 requests/5min)
S2_API_KEY = os.getenv("S2_API_KEY", "")


class LiteratureAgent:
    """
    Literature search agent using Semantic Scholar API.

    Features:
    - Full-text semantic search across 200M+ papers
    - Citation metrics and impact analysis
    - Open access PDF detection
    - TLDR summaries via AI
    """

    def __init__(self):
        self.headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}

        self.client = httpx.AsyncClient(timeout=30.0, headers=self.headers)

    async def search_papers(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Searches Semantic Scholar for relevant papers.

        Args:
            query: Natural language search query
            limit: Maximum number of papers to return

        Returns:
            List of formatted paper dictionaries
        """
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,abstract,authors,year,citationCount,venue,url,tldr,openAccessPdf,externalIds,fieldsOfStudy,publicationTypes",
        }

        try:
            resp = await self.client.get(SEMANTIC_SCHOLAR_API_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                papers = self._format_papers(data.get("data", []))

                # Sort by citation count (most cited first)
                papers.sort(key=lambda x: x.get("citations", 0), reverse=True)
                return papers
            else:
                print(f"SS Search Error: {resp.status_code} - {resp.text}")
                return []
        except Exception as e:
            print(f"Literature Search Exception: {e}")
            return []

    async def get_paper_details(self, paper_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific paper.

        Args:
            paper_id: Semantic Scholar paper ID or DOI
        """
        fields = "title,abstract,authors,year,citationCount,venue,url,tldr,openAccessPdf,references,citations,externalIds"

        try:
            resp = await self.client.get(
                f"{SEMANTIC_SCHOLAR_PAPER_URL}/{paper_id}", params={"fields": fields}
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Paper details error: {e}")

        return None

    async def get_citations(self, paper_id: str, limit: int = 10) -> List[Dict]:
        """
        Get papers that cite a given paper.
        """
        try:
            resp = await self.client.get(
                f"{SEMANTIC_SCHOLAR_PAPER_URL}/{paper_id}/citations",
                params={
                    "fields": "title,authors,year,citationCount,venue",
                    "limit": limit,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return [c.get("citingPaper", {}) for c in data.get("data", [])]
        except Exception as e:
            print(f"Citations error: {e}")

        return []

    async def get_references(self, paper_id: str, limit: int = 10) -> List[Dict]:
        """
        Get papers referenced by a given paper.
        """
        try:
            resp = await self.client.get(
                f"{SEMANTIC_SCHOLAR_PAPER_URL}/{paper_id}/references",
                params={
                    "fields": "title,authors,year,citationCount,venue",
                    "limit": limit,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return [r.get("citedPaper", {}) for r in data.get("data", [])]
        except Exception as e:
            print(f"References error: {e}")

        return []

    async def search_by_author(self, author_name: str, limit: int = 10) -> List[Dict]:
        """
        Search for papers by a specific author.
        """
        # Use author search endpoint
        try:
            resp = await self.client.get(
                "https://api.semanticscholar.org/graph/v1/author/search",
                params={"query": author_name, "limit": 1},
            )
            if resp.status_code == 200:
                data = resp.json()
                authors = data.get("data", [])
                if authors:
                    author_id = authors[0].get("authorId")
                    # Get author's papers
                    papers_resp = await self.client.get(
                        f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers",
                        params={
                            "fields": "title,abstract,authors,year,citationCount,venue,url",
                            "limit": limit,
                        },
                    )
                    if papers_resp.status_code == 200:
                        papers_data = papers_resp.json()
                        return self._format_papers(papers_data.get("data", []))
        except Exception as e:
            print(f"Author search error: {e}")

        return []

    def _format_papers(self, raw_papers: List[Dict]) -> List[Dict]:
        """Format raw API response into clean paper objects."""
        formatted = []
        for p in raw_papers:
            if not p:
                continue

            authors = [a.get("name", "") for a in p.get("authors", [])[:3]]
            if len(p.get("authors", [])) > 3:
                authors.append("et al.")

            # Get best available abstract
            abstract = p.get("abstract")
            if not abstract:
                tldr = p.get("tldr")
                if tldr and isinstance(tldr, dict):
                    abstract = tldr.get("text", "No abstract available.")
                else:
                    abstract = "No abstract available."

            # Get PDF URL (prefer open access)
            pdf_info = p.get("openAccessPdf")
            pdf_url = None
            if pdf_info and isinstance(pdf_info, dict):
                pdf_url = pdf_info.get("url")

            url = (
                pdf_url
                or p.get("url")
                or f"https://www.semanticscholar.org/paper/{p.get('paperId')}"
            )

            # Get external IDs
            external_ids = p.get("externalIds", {}) or {}
            doi = external_ids.get("DOI")
            pmid = external_ids.get("PubMed")

            formatted.append(
                {
                    "id": p.get("paperId"),
                    "title": p.get("title", "Unknown Title"),
                    "abstract": abstract,
                    "authors": ", ".join(authors) if authors else "Unknown",
                    "year": p.get("year"),
                    "citations": p.get("citationCount", 0),
                    "journal": p.get("venue") or "Preprint/Unknown",
                    "url": url,
                    "pdf_url": pdf_url,
                    "doi": doi,
                    "pmid": pmid,
                    "fields": p.get("fieldsOfStudy", []),
                    "publication_types": p.get("publicationTypes", []),
                    "source": "Semantic Scholar",
                }
            )
        return formatted


# Test standalone
if __name__ == "__main__":

    async def test():
        agent = LiteratureAgent()

        print("Testing paper search...")
        papers = await agent.search_papers(
            "KRAS G12C resistance mechanisms lung cancer", limit=5
        )
        print(f"Found {len(papers)} papers")
        for p in papers:
            print(f"- [{p['citations']} cites] {p['title']} ({p['year']})")
            if p.get("doi"):
                print(f"  DOI: {p['doi']}")

        if papers:
            print("\nTesting citations for first paper...")
            citations = await agent.get_citations(papers[0]["id"], limit=3)
            print(f"Found {len(citations)} citing papers")

    asyncio.run(test())
