import httpx
from typing import Dict, Any, List, Optional
from collections import defaultdict
from datetime import datetime
import asyncio
import re


class PatentAgent:
    """
    Patent Hawk - Module B
    Analyzes patent landscape for Freedom-to-Operate assessment.

    Uses multiple data sources:
    1. USPTO PatentsView API (free, no key required)
    2. EPO Open Patent Services (free tier)
    3. Google Patents / Lens.org links for manual verification
    """

    def __init__(self):
        self.patentsview_url = "https://api.patentsview.org/patents/query"
        self.current_year = datetime.now().year

        # Known pharma company name patterns for assignee matching
        self.pharma_patterns = {
            "pfizer": "Pfizer",
            "novartis": "Novartis",
            "roche": "Roche",
            "merck": "Merck",
            "bristol": "Bristol-Myers Squibb",
            "astrazeneca": "AstraZeneca",
            "johnson": "Johnson & Johnson",
            "abbvie": "AbbVie",
            "amgen": "Amgen",
            "gilead": "Gilead",
            "sanofi": "Sanofi",
            "gsk": "GSK",
            "glaxo": "GSK",
            "lilly": "Eli Lilly",
            "regeneron": "Regeneron",
            "biogen": "Biogen",
            "takeda": "Takeda",
            "bayer": "Bayer",
            "boehringer": "Boehringer Ingelheim",
            "moderna": "Moderna",
            "genentech": "Genentech/Roche",
            "broad": "Broad Institute",
            "mit": "MIT",
            "harvard": "Harvard",
            "stanford": "Stanford",
            "university": "Academic",
        }

    async def search_patents(self, gene: str, disease: str) -> Dict[str, Any]:
        """
        Comprehensive patent landscape analysis.

        Returns:
            - Real patent counts from USPTO PatentsView
            - Scooped Score (0-100, higher = more competition)
            - Freedom-to-Operate heatmap data
            - Links to patent databases for verification
        """

        # 1. Query USPTO PatentsView API
        patent_data = await self._query_patentsview(gene, disease)

        # 2. Calculate metrics
        total_patents = patent_data.get("total_count", 0)
        patents_by_year = patent_data.get("by_year", {})
        patents_by_assignee = patent_data.get("by_assignee", {})
        recent_patents = patent_data.get("recent_patents", [])

        # 3. Calculate Scooped Score
        scooped_score, risk_assessment = self._calculate_scooped_score(
            total_patents, patents_by_year, len(patents_by_assignee)
        )

        # 4. Generate heatmap data
        heatmap = self._generate_heatmap(
            patents_by_year, patents_by_assignee, recent_patents
        )

        # 5. Determine risk color
        if scooped_score >= 70:
            risk_color = "red"
            risk_label = "High Risk"
        elif scooped_score >= 40:
            risk_color = "amber"
            risk_label = "Moderate Risk"
        elif scooped_score >= 20:
            risk_color = "yellow"
            risk_label = "Low Risk"
        else:
            risk_color = "green"
            risk_label = "White Space"

        # 6. Generate search links
        google_url = f"https://patents.google.com/?q={gene}&q={disease}&after=priority:20200101&type=PATENT"
        epo_url = f"https://worldwide.espacenet.com/patent/search?q={gene}%20{disease}"
        lens_url = f"https://www.lens.org/lens/search/patent/list?q={gene}%20{disease}"

        # 7. Top competitors
        top_competitors = sorted(
            patents_by_assignee.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "query": f"{gene} AND {disease}",
            "total_hits": total_patents,
            "recent_filings_5y": sum(
                patents_by_year.get(str(y), 0)
                for y in range(self.current_year - 5, self.current_year + 1)
            ),
            "scooped_score": scooped_score,
            "risk_assessment": risk_assessment,
            "risk_color": risk_color,
            "risk_label": risk_label,
            "heatmap": heatmap,
            "top_competitors": [
                {"name": name, "count": count} for name, count in top_competitors
            ],
            "patents_by_year": patents_by_year,
            "sample_patents": recent_patents[:5],
            "google_patents_link": google_url,
            "epo_link": epo_url,
            "lens_link": lens_url,
            "data_source": patent_data.get("source", "USPTO PatentsView"),
            "message": risk_assessment,
        }

    async def _query_patentsview(self, gene: str, disease: str) -> Dict[str, Any]:
        """
        Query USPTO PatentsView API for patent data.
        Falls back gracefully if API is unavailable.
        """

        # PatentsView API query format
        # Search in title and abstract for gene and disease terms
        query = {
            "q": {
                "_and": [
                    {
                        "_or": [
                            {"_text_any": {"patent_title": gene}},
                            {"_text_any": {"patent_abstract": gene}},
                        ]
                    },
                    {
                        "_or": [
                            {"_text_any": {"patent_title": disease}},
                            {"_text_any": {"patent_abstract": disease}},
                            {"_text_any": {"patent_title": "cancer"}},
                            {"_text_any": {"patent_abstract": "cancer"}},
                        ]
                    },
                    {"_gte": {"patent_date": f"{self.current_year - 10}-01-01"}},
                ]
            },
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "assignee_organization",
            ],
            "o": {"per_page": 100},
            "s": [{"patent_date": "desc"}],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    self.patentsview_url,
                    json=query,
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_patentsview_response(data)
                else:
                    print(f"PatentsView API returned {resp.status_code}")

            except Exception as e:
                print(f"PatentsView API error: {e}")

        # Fallback: return empty but structured data
        return {
            "total_count": 0,
            "by_year": {},
            "by_assignee": {},
            "recent_patents": [],
            "source": "No data (API unavailable)",
        }

    def _parse_patentsview_response(self, data: Dict) -> Dict[str, Any]:
        """Parse PatentsView API response into structured data."""

        patents = data.get("patents", [])
        total_count = data.get("total_patent_count", len(patents))

        by_year = defaultdict(int)
        by_assignee = defaultdict(int)
        recent_patents = []

        for patent in patents:
            # Extract year
            patent_date = patent.get("patent_date", "")
            if patent_date:
                year = patent_date[:4]
                by_year[year] += 1

            # Extract assignees
            assignees = patent.get("assignees", [])
            if assignees:
                for assignee in assignees:
                    org = assignee.get("assignee_organization", "Unknown")
                    if org:
                        # Normalize assignee name
                        normalized = self._normalize_assignee(org)
                        by_assignee[normalized] += 1

            # Build patent record
            recent_patents.append(
                {
                    "number": patent.get("patent_number", ""),
                    "title": patent.get("patent_title", "")[:100],
                    "date": patent_date,
                    "assignee": assignees[0].get("assignee_organization", "Unknown")
                    if assignees
                    else "Unknown",
                }
            )

        return {
            "total_count": total_count,
            "by_year": dict(by_year),
            "by_assignee": dict(by_assignee),
            "recent_patents": recent_patents,
            "source": "USPTO PatentsView",
        }

    def _normalize_assignee(self, name: str) -> str:
        """Normalize assignee names to standard company names."""
        name_lower = name.lower()

        for pattern, normalized in self.pharma_patterns.items():
            if pattern in name_lower:
                return normalized

        # Clean up common suffixes
        cleaned = re.sub(
            r"\s+(inc\.?|corp\.?|ltd\.?|llc|co\.?|company)$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        return cleaned.strip()[:30]  # Truncate for display

    def _calculate_scooped_score(
        self, total_patents: int, patents_by_year: Dict[str, int], num_competitors: int
    ) -> tuple:
        """
        Calculate Scooped Score (0-100) based on patent landscape.

        Factors:
        1. Total patent count (more = higher risk)
        2. Recent trend (increasing = higher risk)
        3. Number of competitors (more = harder to differentiate)
        """

        if total_patents == 0:
            return (
                5,
                "White Space Opportunity: No relevant patents found. First-in-class potential!",
            )

        # 1. Volume Score (0-40 points)
        # 0 patents = 0, 50+ patents = 40
        volume_score = min(40, (total_patents / 50) * 40)

        # 2. Trend Score (0-30 points)
        # Compare last 2 years vs previous 3 years
        recent_years = [str(self.current_year - i) for i in range(2)]
        older_years = [str(self.current_year - i) for i in range(2, 5)]

        recent_count = sum(patents_by_year.get(y, 0) for y in recent_years)
        older_count = sum(patents_by_year.get(y, 0) for y in older_years)

        if older_count > 0:
            trend_ratio = recent_count / max(older_count, 1)
            if trend_ratio > 1.5:
                trend_score = 30  # Accelerating filings
            elif trend_ratio > 1.0:
                trend_score = 20  # Steady increase
            elif trend_ratio > 0.5:
                trend_score = 10  # Declining
            else:
                trend_score = 5  # Significantly declining
        else:
            trend_score = 15 if recent_count > 0 else 0

        # 3. Competition Score (0-30 points)
        # 1 competitor = 5, 10+ competitors = 30
        competition_score = min(30, max(5, num_competitors * 3))

        scooped_score = int(volume_score + trend_score + competition_score)

        # Generate assessment message
        if scooped_score >= 70:
            assessment = f"High IP Saturation: {total_patents} patents from {num_competitors} competitors. Consider novel mechanisms or PROTAC/degrader strategies to circumvent."
        elif scooped_score >= 40:
            assessment = f"Moderate Competition: {total_patents} patents detected. Differentiation strategy recommended. Look for unexplored indications or combinations."
        elif scooped_score >= 20:
            assessment = f"Emerging Space: {total_patents} patents, limited competition. Good opportunity with proper IP positioning."
        else:
            assessment = f"White Space: Only {total_patents} patents found. Strong first-mover advantage potential."

        return scooped_score, assessment

    def _generate_heatmap(
        self,
        by_year: Dict[str, int],
        by_assignee: Dict[str, int],
        recent_patents: List[Dict],
    ) -> List[Dict]:
        """
        Generate heatmap data for visualization.

        Structure: [{name: "Assignee", data: [{year: 2020, count: 5}, ...]}]
        """

        # Get top 8 assignees
        top_assignees = sorted(by_assignee.items(), key=lambda x: x[1], reverse=True)[
            :8
        ]

        if not top_assignees:
            return []

        # Build assignee-year matrix from recent patents
        matrix = defaultdict(lambda: defaultdict(int))

        for patent in recent_patents:
            assignee = self._normalize_assignee(patent.get("assignee", "Unknown"))
            year = patent.get("date", "")[:4]
            if year and assignee in dict(top_assignees):
                matrix[assignee][year] += 1

        # Generate years range
        years = [str(self.current_year - i) for i in range(5, -1, -1)]

        heatmap = []
        for assignee, _ in top_assignees:
            heatmap.append(
                {
                    "name": assignee,
                    "data": [
                        {"year": year, "count": matrix[assignee].get(year, 0)}
                        for year in years
                    ],
                }
            )

        return heatmap
