import httpx
import logging
from typing import List, Dict, Optional, Any
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class ModelAgent:
    """
    Model Matchmaker - Module C
    Finds the best cell line models for experimental validation.

    Integrates:
    1. Cellosaurus API - Cell line metadata (tissue, disease, species)
    2. DepMap Portal API - Genomic features (mutations, expression, CRISPR)
    3. Problematic cell line database - Contamination/misidentification warnings
    """

    def __init__(self):
        self.cellosaurus_url = "https://api.cellosaurus.org/search/cell-line"
        self.depmap_base_url = "https://api.cellmodelpassports.sanger.ac.uk/api/v1"

        # Known problematic cell lines (contaminated, misidentified, or overused)
        self.problematic_lines = {
            "HELA": {
                "issue": "Notorious for cross-contamination",
                "severity": "high",
                "recommendation": "Verify identity before use",
            },
            "HEP-2": {
                "issue": "Actually HeLa cells (misidentified)",
                "severity": "critical",
                "recommendation": "Avoid - use authenticated hepatocyte lines",
            },
            "KB": {
                "issue": "HeLa derivative (misidentified)",
                "severity": "critical",
                "recommendation": "Avoid",
            },
            "CHANG LIVER": {
                "issue": "HeLa derivative (misidentified)",
                "severity": "critical",
                "recommendation": "Avoid",
            },
            "INT407": {
                "issue": "HeLa derivative",
                "severity": "critical",
                "recommendation": "Avoid",
            },
            "WISH": {
                "issue": "HeLa derivative",
                "severity": "critical",
                "recommendation": "Avoid",
            },
            "H1299": {
                "issue": "p53-null (may confound apoptosis studies)",
                "severity": "moderate",
                "recommendation": "Consider if studying p53-dependent pathways",
            },
            "U2OS": {
                "issue": "Abnormal p53 pathway",
                "severity": "low",
                "recommendation": "Acceptable for most studies",
            },
            "PC-3": {
                "issue": "Androgen-independent (not representative of early PCa)",
                "severity": "moderate",
                "recommendation": "Use for CRPC studies only",
            },
            "SAOS-2": {
                "issue": "p53-null, Rb-null",
                "severity": "moderate",
                "recommendation": "Use for osteosarcoma, not general cancer",
            },
        }

        # Tissue type mappings for query normalization
        self.tissue_mappings = {
            "lung": ["lung", "pulmonary", "bronchial", "bronchus", "NSCLC", "SCLC"],
            "breast": ["breast", "mammary"],
            "colon": ["colon", "colorectal", "intestine", "bowel", "CRC"],
            "pancreas": ["pancreas", "pancreatic", "PDAC"],
            "skin": ["skin", "melanoma", "cutaneous"],
            "blood": ["blood", "leukemia", "lymphoma", "myeloma", "hematopoietic"],
            "brain": ["brain", "glioma", "glioblastoma", "neuroblastoma", "CNS"],
            "liver": ["liver", "hepatic", "hepatocellular", "HCC"],
            "prostate": ["prostate", "prostatic"],
            "ovary": ["ovary", "ovarian"],
            "kidney": ["kidney", "renal", "RCC"],
        }

        # Common cancer mutations
        self.common_mutations = {
            "KRAS": ["G12C", "G12D", "G12V", "G13D", "Q61H"],
            "BRAF": ["V600E", "V600K"],
            "EGFR": ["L858R", "T790M", "C797S", "exon19del"],
            "TP53": ["R175H", "R248Q", "R273H", "R282W"],
            "PIK3CA": ["E545K", "H1047R"],
            "NRAS": ["Q61R", "Q61K"],
        }

    async def find_models(
        self,
        tissue: str,
        mutation: Optional[str] = None,
        exclude_problematic: bool = True,
    ) -> Dict[str, Any]:
        """
        Find optimal cell line models for experimental validation.

        Args:
            tissue: Target tissue type (e.g., "lung", "breast")
            mutation: Optional mutation to filter for (e.g., "KRAS G12C")
            exclude_problematic: Whether to exclude known problematic lines

        Returns:
            Ranked list of cell line recommendations with metadata
        """

        # Parse mutation if provided
        gene_filter = None
        mutation_filter = None
        if mutation:
            parts = mutation.upper().split()
            if len(parts) >= 1:
                gene_filter = parts[0]
            if len(parts) >= 2:
                mutation_filter = parts[1]

        # 1. Query Cellosaurus for cell lines matching tissue
        cellosaurus_results = await self._query_cellosaurus(tissue)

        # 2. Query DepMap/Cell Model Passports for genomic data
        depmap_results = await self._query_depmap(tissue, gene_filter)

        # 3. Merge and enrich results
        merged = self._merge_results(cellosaurus_results, depmap_results, tissue)

        # 4. Filter by mutation if specified
        if gene_filter:
            merged = self._filter_by_mutation(merged, gene_filter, mutation_filter)

        # 5. Flag problematic lines
        merged = self._flag_problematic(merged)

        # 6. Calculate match scores
        merged = self._calculate_scores(merged, tissue, gene_filter, mutation_filter)

        # 7. Rank results
        if exclude_problematic:
            # Move problematic lines to the end
            merged.sort(
                key=lambda x: (x.get("is_problematic", False), -x.get("match_score", 0))
            )
        else:
            merged.sort(key=lambda x: -x.get("match_score", 0))

        # 8. Prepare response
        recommendations = merged[:10]  # Top 10
        problematic = [m for m in merged if m.get("is_problematic")]

        return {
            "query": {
                "tissue": tissue,
                "mutation": mutation,
                "gene_filter": gene_filter,
                "mutation_filter": mutation_filter,
            },
            "total_found": len(merged),
            "recommendations": recommendations,
            "top_pick": recommendations[0] if recommendations else None,
            "avoid_list": problematic[:5],
            "data_sources": ["Cellosaurus", "DepMap/Cell Model Passports"],
            "notes": self._generate_notes(tissue, gene_filter, recommendations),
        }

    async def _query_cellosaurus(self, tissue: str) -> List[Dict]:
        """Query Cellosaurus API for cell lines."""

        # Build query terms
        tissue_terms = self.tissue_mappings.get(tissue.lower(), [tissue])
        query = " OR ".join([f'"{t}"' for t in tissue_terms[:3]])
        query += ' AND "Homo sapiens"'

        candidates = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                params = {"q": query, "format": "json", "rows": 50}
                resp = await client.get(self.cellosaurus_url, params=params)

                if resp.status_code == 200:
                    data = resp.json()

                    for hit in data.get("response", {}).get("docs", []):
                        name = hit.get("id", "Unknown")
                        accession = hit.get("ac", "")

                        # Parse disease information
                        diseases = hit.get("di", [])
                        disease_str = diseases[0] if diseases else "Unknown"

                        # Parse cell type
                        cell_type = hit.get("ca", "Unknown")

                        # Parse species
                        species = (
                            hit.get("ox", ["Unknown"])[0]
                            if hit.get("ox")
                            else "Unknown"
                        )

                        # Parse sex
                        sex = hit.get("sx", "Unknown")

                        # Parse references
                        refs = hit.get("rx", [])

                        candidates.append(
                            {
                                "name": name,
                                "accession": accession,
                                "tissue": tissue,
                                "disease": disease_str,
                                "cell_type": cell_type,
                                "species": species,
                                "sex": sex,
                                "reference_count": len(refs),
                                "source": "Cellosaurus",
                            }
                        )

            except Exception as e:
                logger.error("Cellosaurus API error: %s", e)

        return candidates

    async def _query_depmap(
        self, tissue: str, gene: Optional[str] = None
    ) -> List[Dict]:
        """Query DepMap/Cell Model Passports for genomic data."""

        candidates = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Query cell models endpoint
                # Cell Model Passports API: https://cellmodelpassports.sanger.ac.uk/
                params = {"tissue": tissue, "page_size": 50}
                resp = await client.get(f"{self.depmap_base_url}/models", params=params)

                if resp.status_code == 200:
                    data = resp.json()

                    for model in data.get("data", []):
                        name = model.get("model_name", "Unknown")

                        # Extract available data types
                        available_data = []
                        if model.get("has_wes"):
                            available_data.append("WES")
                        if model.get("has_wgs"):
                            available_data.append("WGS")
                        if model.get("has_rnaseq"):
                            available_data.append("RNA-seq")
                        if model.get("has_drug_response"):
                            available_data.append("Drug Response")
                        if model.get("has_crispr"):
                            available_data.append("CRISPR")
                        if model.get("has_methylation"):
                            available_data.append("Methylation")

                        # Extract mutations if available
                        mutations = model.get("mutations", [])

                        candidates.append(
                            {
                                "name": name,
                                "depmap_id": model.get("model_id", ""),
                                "tissue": model.get("tissue", tissue),
                                "disease": model.get("cancer_type", "Unknown"),
                                "disease_subtype": model.get("cancer_type_detail", ""),
                                "available_data": available_data,
                                "data_richness": len(available_data),
                                "mutations": mutations,
                                "growth_properties": model.get("growth_properties", ""),
                                "source": "DepMap",
                            }
                        )

            except Exception as e:
                logger.error("DepMap API error: %s", e)

                # Fallback: Return some well-known cancer cell lines
                fallback_lines = self._get_fallback_lines(tissue, gene)
                candidates.extend(fallback_lines)

        return candidates

    def _get_fallback_lines(
        self, tissue: str, gene: Optional[str] = None
    ) -> List[Dict]:
        """Fallback list of well-characterized cancer cell lines."""

        fallback = {
            "lung": [
                {
                    "name": "A549",
                    "disease": "Lung Adenocarcinoma",
                    "mutations": ["KRAS G12S"],
                    "data_richness": 6,
                },
                {
                    "name": "H1975",
                    "disease": "NSCLC",
                    "mutations": ["EGFR L858R", "EGFR T790M"],
                    "data_richness": 5,
                },
                {
                    "name": "H460",
                    "disease": "Large Cell Lung Carcinoma",
                    "mutations": ["KRAS Q61H"],
                    "data_richness": 5,
                },
                {
                    "name": "H358",
                    "disease": "NSCLC",
                    "mutations": ["KRAS G12C"],
                    "data_richness": 5,
                },
                {
                    "name": "H23",
                    "disease": "NSCLC",
                    "mutations": ["KRAS G12C"],
                    "data_richness": 4,
                },
                {
                    "name": "PC9",
                    "disease": "NSCLC",
                    "mutations": ["EGFR exon19del"],
                    "data_richness": 5,
                },
                {
                    "name": "HCC827",
                    "disease": "NSCLC",
                    "mutations": ["EGFR exon19del"],
                    "data_richness": 5,
                },
                {
                    "name": "CALU-1",
                    "disease": "NSCLC",
                    "mutations": ["KRAS G12C"],
                    "data_richness": 4,
                },
            ],
            "breast": [
                {
                    "name": "MCF7",
                    "disease": "Breast Adenocarcinoma",
                    "mutations": ["PIK3CA E545K"],
                    "data_richness": 6,
                },
                {
                    "name": "MDA-MB-231",
                    "disease": "Triple-Negative Breast Cancer",
                    "mutations": ["KRAS G13D", "BRAF G464V"],
                    "data_richness": 6,
                },
                {
                    "name": "T47D",
                    "disease": "Breast Carcinoma",
                    "mutations": ["PIK3CA H1047R"],
                    "data_richness": 5,
                },
                {
                    "name": "BT-474",
                    "disease": "Breast Carcinoma",
                    "mutations": ["PIK3CA K111N"],
                    "data_richness": 5,
                },
            ],
            "colon": [
                {
                    "name": "HCT116",
                    "disease": "Colorectal Carcinoma",
                    "mutations": ["KRAS G13D", "PIK3CA H1047R"],
                    "data_richness": 6,
                },
                {
                    "name": "SW480",
                    "disease": "Colorectal Adenocarcinoma",
                    "mutations": ["KRAS G12V", "TP53 R273H"],
                    "data_richness": 5,
                },
                {
                    "name": "COLO205",
                    "disease": "Colorectal Adenocarcinoma",
                    "mutations": ["BRAF V600E"],
                    "data_richness": 5,
                },
                {
                    "name": "HT29",
                    "disease": "Colorectal Adenocarcinoma",
                    "mutations": ["BRAF V600E", "PIK3CA P449T"],
                    "data_richness": 5,
                },
            ],
            "pancreas": [
                {
                    "name": "PANC-1",
                    "disease": "Pancreatic Carcinoma",
                    "mutations": ["KRAS G12D", "TP53 R273H"],
                    "data_richness": 5,
                },
                {
                    "name": "MIA PaCa-2",
                    "disease": "Pancreatic Carcinoma",
                    "mutations": ["KRAS G12C", "TP53 R248W"],
                    "data_richness": 5,
                },
                {
                    "name": "BxPC-3",
                    "disease": "Pancreatic Adenocarcinoma",
                    "mutations": ["TP53 Y220C"],
                    "data_richness": 4,
                },
                {
                    "name": "AsPC-1",
                    "disease": "Pancreatic Adenocarcinoma",
                    "mutations": ["KRAS G12D"],
                    "data_richness": 4,
                },
            ],
            "skin": [
                {
                    "name": "A375",
                    "disease": "Melanoma",
                    "mutations": ["BRAF V600E"],
                    "data_richness": 6,
                },
                {
                    "name": "SK-MEL-28",
                    "disease": "Melanoma",
                    "mutations": ["BRAF V600E"],
                    "data_richness": 5,
                },
                {
                    "name": "MEWO",
                    "disease": "Melanoma",
                    "mutations": ["BRAF WT", "NRAS WT"],
                    "data_richness": 4,
                },
                {
                    "name": "WM266-4",
                    "disease": "Melanoma",
                    "mutations": ["BRAF V600D"],
                    "data_richness": 4,
                },
            ],
        }

        lines = fallback.get(tissue.lower(), [])

        for line in lines:
            line["tissue"] = tissue
            line["available_data"] = ["WES", "RNA-seq", "CRISPR", "Drug Response"][
                : line["data_richness"]
            ]
            line["source"] = "Curated Database"

        return lines

    def _merge_results(
        self, cellosaurus: List[Dict], depmap: List[Dict], tissue: str
    ) -> List[Dict]:
        """Merge results from multiple sources, preferring DepMap data."""

        merged = {}

        # Add Cellosaurus results
        for item in cellosaurus:
            name = item["name"].upper()
            merged[name] = item

        # Merge/override with DepMap results (richer data)
        for item in depmap:
            name = item["name"].upper()
            if name in merged:
                # Merge: keep Cellosaurus metadata, add DepMap genomic data
                merged[name].update(
                    {
                        "available_data": item.get("available_data", []),
                        "data_richness": item.get("data_richness", 0),
                        "mutations": item.get("mutations", []),
                        "depmap_id": item.get("depmap_id", ""),
                    }
                )
            else:
                merged[name] = item

        return list(merged.values())

    def _filter_by_mutation(
        self, candidates: List[Dict], gene: str, mutation: Optional[str]
    ) -> List[Dict]:
        """Filter candidates by mutation status."""

        filtered = []

        for candidate in candidates:
            mutations = candidate.get("mutations", [])
            if not mutations:
                # Include lines without mutation data (may have the mutation)
                candidate["mutation_match"] = "Unknown"
                filtered.append(candidate)
                continue

            # Check for gene match
            mutation_str = " ".join(str(m) for m in mutations).upper()

            if gene.upper() in mutation_str:
                if mutation:
                    # Check specific mutation
                    if mutation.upper() in mutation_str:
                        candidate["mutation_match"] = "Exact"
                        filtered.insert(0, candidate)  # Priority
                    else:
                        candidate["mutation_match"] = "Gene Match"
                        filtered.append(candidate)
                else:
                    candidate["mutation_match"] = "Gene Match"
                    filtered.append(candidate)
            else:
                candidate["mutation_match"] = "No Match"
                # Still include but lower priority

        # Add non-matching lines at the end for comparison
        non_matching = [c for c in candidates if c.get("mutation_match") == "No Match"]
        filtered.extend(non_matching[:5])

        return filtered

    def _flag_problematic(self, candidates: List[Dict]) -> List[Dict]:
        """Flag known problematic cell lines."""

        for candidate in candidates:
            name = candidate["name"].upper()

            if name in self.problematic_lines:
                info = self.problematic_lines[name]
                candidate["is_problematic"] = True
                candidate["problem_info"] = info
                candidate["warning"] = f"⚠️ {info['issue']}"
            else:
                candidate["is_problematic"] = False

        return candidates

    def _calculate_scores(
        self,
        candidates: List[Dict],
        tissue: str,
        gene: Optional[str],
        mutation: Optional[str],
    ) -> List[Dict]:
        """Calculate match scores for ranking."""

        for candidate in candidates:
            score = 50  # Base score

            # Data richness bonus (0-20 points)
            data_richness = candidate.get("data_richness", 0)
            score += min(20, data_richness * 3)

            # Mutation match bonus (0-30 points)
            mutation_match = candidate.get("mutation_match", "Unknown")
            if mutation_match == "Exact":
                score += 30
            elif mutation_match == "Gene Match":
                score += 15
            elif mutation_match == "Unknown":
                score += 5

            # Reference count bonus (0-10 points) - well-studied lines
            ref_count = candidate.get("reference_count", 0)
            score += min(10, ref_count // 10)

            # Problematic penalty
            if candidate.get("is_problematic"):
                severity = candidate.get("problem_info", {}).get("severity", "moderate")
                if severity == "critical":
                    score -= 40
                elif severity == "high":
                    score -= 25
                else:
                    score -= 10

            candidate["match_score"] = max(0, min(100, score))

            # Generate reason string
            reasons = []
            if mutation_match == "Exact":
                reasons.append(f"Has {gene} {mutation}")
            elif mutation_match == "Gene Match":
                reasons.append(f"Has {gene} mutation")
            if data_richness >= 4:
                reasons.append("Rich dataset")
            if candidate.get("is_problematic"):
                reasons.append(candidate["warning"])

            candidate["reason"] = " | ".join(reasons) if reasons else "Tissue match"

        return candidates

    def _generate_notes(
        self, tissue: str, gene: Optional[str], recommendations: List[Dict]
    ) -> List[str]:
        """Generate helpful notes for the user."""

        notes = []

        if not recommendations:
            notes.append(
                f"No cell lines found for {tissue}. Consider broadening your search criteria."
            )
            return notes

        top = recommendations[0] if recommendations else None

        if top:
            if top.get("mutation_match") == "Exact":
                notes.append(
                    f"✓ Top pick {top['name']} has the exact mutation you're targeting."
                )

            if top.get("data_richness", 0) >= 5:
                notes.append(
                    f"✓ {top['name']} has extensive genomic and drug response data available."
                )

        # Check for problematic lines in top 5
        problematic_in_top = [r for r in recommendations[:5] if r.get("is_problematic")]
        if problematic_in_top:
            names = ", ".join([r["name"] for r in problematic_in_top])
            notes.append(f"⚠️ Note: {names} have known issues. See details before use.")

        # Add tissue-specific notes
        if tissue.lower() == "lung" and gene and "KRAS" in gene.upper():
            notes.append(
                "💡 For KRAS G12C, consider H358, H23, or CALU-1 as primary models."
            )

        if tissue.lower() == "skin":
            notes.append(
                "💡 For BRAF V600E melanoma, A375 and SK-MEL-28 are gold standards."
            )

        return notes
