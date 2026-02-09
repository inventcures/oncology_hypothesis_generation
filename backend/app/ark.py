"""
ARK - Adaptive Reasoning over Knowledge graphs

Combines:
1. GLiNER2 entity + relation extraction (local, private, deterministic)
2. OpenTargets GraphQL API for validated biological associations
3. Rich KG builder for color-coded, interactive graph output

Pipeline:
  Query text
    -> GLiNER2 extract_all(text) -> entities + relations + classification
    -> OpenTargets search_entity(seed) -> 1-hop associations
    -> KG builder merges both sources
    -> Rich serialised JSON with visual metadata for frontend
"""

import networkx as nx
import httpx
import asyncio
import logging
import re
from typing import List, Dict, Any, Optional

from .entity_extraction import get_extractor, OncologyEntityExtractor
from .kg_builder import KnowledgeGraphBuilder, entity_text

logger = logging.getLogger(__name__)

OT_API_URL = "https://api.platform.opentargets.org/api/v4/graphql"


class OpenTargetsClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search_entity(self, query_str: str) -> Optional[Dict[str, str]]:
        """
        Searches for a Target or Disease and returns the top hit.
        """
        query = """
        query Search($queryString: String!) {
          search(queryString: $queryString, entityNames: ["target", "disease"], page: {index: 0, size: 1}) {
            hits {
              id
              name
              entity
            }
          }
        }
        """
        try:
            resp = await self.client.post(
                OT_API_URL,
                json={"query": query, "variables": {"queryString": query_str}},
            )
            data = resp.json()
            hits = data.get("data", {}).get("search", {}).get("hits", [])
            if hits:
                return hits[0]
            return None
        except Exception as e:
            logger.warning("OT Search Error: %s", e)
            return None

    async def get_target_associations(self, ensembl_id: str) -> List[Dict]:
        """
        Get diseases associated with a target.
        """
        query = """
        query TargetAssociations($ensemblId: String!) {
          target(ensemblId: $ensemblId) {
            id
            approvedSymbol
            associatedDiseases(page: {size: 10}) {
              rows {
                disease {
                  id
                  name
                }
                score
              }
            }
          }
        }
        """
        try:
            resp = await self.client.post(
                OT_API_URL,
                json={"query": query, "variables": {"ensemblId": ensembl_id}},
            )
            data = resp.json()
            rows = (
                data.get("data", {})
                .get("target", {})
                .get("associatedDiseases", {})
                .get("rows", [])
            )
            return [
                {
                    "id": r["disease"]["name"],
                    "type": "Disease",
                    "score": r["score"],
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("OT Target Assoc Error: %s", e)
            return []

    async def get_disease_associations(self, efo_id: str) -> List[Dict]:
        """
        Get targets associated with a disease.
        """
        query = """
        query DiseaseAssociations($efoId: String!) {
          disease(efoId: $efoId) {
            id
            name
            associatedTargets(page: {size: 10}) {
              rows {
                target {
                  id
                  approvedSymbol
                }
                score
              }
            }
          }
        }
        """
        try:
            resp = await self.client.post(
                OT_API_URL, json={"query": query, "variables": {"efoId": efo_id}}
            )
            data = resp.json()
            rows = (
                data.get("data", {})
                .get("disease", {})
                .get("associatedTargets", {})
                .get("rows", [])
            )
            return [
                {
                    "id": r["target"]["approvedSymbol"],
                    "type": "Gene",
                    "score": r["score"],
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("OT Disease Assoc Error: %s", e)
            return []


class OncoGraph:
    """
    Enhanced ARK graph engine that combines GLiNER2 NER + relation
    extraction with OpenTargets API associations into a single rich
    knowledge graph.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.ot_client = OpenTargetsClient()
        self.kg_builder = KnowledgeGraphBuilder()
        self._extractor: Optional[OncologyEntityExtractor] = None
        self._last_extraction: Optional[Dict[str, Any]] = None

    @property
    def extractor(self) -> OncologyEntityExtractor:
        if self._extractor is None:
            self._extractor = get_extractor()
        return self._extractor

    async def build_from_query(self, query_text: str):
        """
        Dynamically builds a rich KG based on the user's query.

        Phase 1: GLiNER2 entity + relation extraction from query text
        Phase 2: OpenTargets API enrichment for seed entity
        Phase 3: Pathway & cell-type enrichment for gene seeds
        Phase 4: Merge into rich KG builder with visual metadata
        """
        self.kg_builder = KnowledgeGraphBuilder()  # fresh graph

        # ----- Phase 1: GLiNER2 extraction -----
        try:
            extraction = self.extractor.extract_all(query_text)
            self._last_extraction = extraction

            entities = extraction.get("entities", {})
            relations = extraction.get("relations", {})

            nodes_added = self.kg_builder.add_entities(entities)
            edges_added = self.kg_builder.add_relations(relations)

            logger.info(
                "GLiNER2 extracted %d entities, %d relations from query",
                nodes_added,
                edges_added,
            )
        except Exception as e:
            logger.warning("GLiNER2 extraction failed: %s (falling back to OT-only)", e)
            self._last_extraction = None

        # ----- Phase 2: OpenTargets enrichment -----
        # Find a seed gene from the GLiNER2 extraction or fall back to raw query
        seed_gene = self._pick_seed_gene(query_text)

        seed_entity = await self.ot_client.search_entity(seed_gene or query_text)

        if seed_entity:
            seed_id = seed_entity["id"]
            seed_name = seed_entity["name"]
            seed_type = "Gene" if seed_entity["entity"] == "target" else "Disease"

            neighbors = []
            if seed_type == "Gene":
                neighbors = await self.ot_client.get_target_associations(seed_id)
            else:
                neighbors = await self.ot_client.get_disease_associations(seed_id)

            self.kg_builder.add_opentargets_associations(
                seed_name,
                seed_type,
                neighbors,
            )

            # ----- Phase 3: Pathway & cell-type enrichment -----
            if seed_type == "Gene":
                self.kg_builder.add_pathway_enrichment(seed_name)

            # Also enrich any other genes found by GLiNER2
            if self._last_extraction:
                for gene_item in self._last_extraction.get("entities", {}).get(
                    "gene", []
                ):
                    gname = entity_text(gene_item)
                    if gname and gname != seed_name:
                        self.kg_builder.add_pathway_enrichment(gname)

        elif self.kg_builder.graph.number_of_nodes() == 0:
            # Both GLiNER2 and OT failed -> load fallback mock data
            self._load_mock_data()

        # Sync the internal networkx graph reference for TTT compatibility
        self.graph = self.kg_builder.graph

    def _pick_seed_gene(self, query_text: str) -> Optional[str]:
        """
        Pick the best seed gene from GLiNER2 extraction.
        Falls back to regex extraction.
        """
        if self._last_extraction:
            genes = self._last_extraction.get("entities", {}).get("gene", [])
            if genes:
                # Pick highest-confidence gene
                best = max(
                    genes,
                    key=lambda g: g.get("confidence", 0) if isinstance(g, dict) else 0,
                )
                return best if isinstance(best, str) else best.get("text", "")

        match = re.search(r"\b([A-Z][A-Z0-9]{2,7})\b", query_text)
        return match.group(1) if match else None

    def _load_mock_data(self):
        """Load fallback mock data into the KG builder."""
        mock_entities = {
            "gene": [
                {"text": "KRAS", "confidence": 0.95},
                {"text": "EGFR", "confidence": 0.90},
                {"text": "TP53", "confidence": 0.88},
                {"text": "STK11", "confidence": 0.85},
                {"text": "YAP1", "confidence": 0.80},
            ],
            "disease": [
                {"text": "Lung Adenocarcinoma", "confidence": 0.92},
                {"text": "Melanoma", "confidence": 0.78},
            ],
        }
        mock_relations = {
            "drives": [
                ("KRAS", "Lung Adenocarcinoma"),
                ("STK11", "Lung Adenocarcinoma"),
            ],
            "associated_with": [
                ("EGFR", "Lung Adenocarcinoma"),
                ("TP53", "Lung Adenocarcinoma"),
            ],
        }

        self.kg_builder.add_entities(mock_entities)
        self.kg_builder.add_relations(mock_relations)
        self.kg_builder.add_pathway_enrichment("KRAS")
        self.kg_builder.add_pathway_enrichment("STK11")

    def get_subgraph_data(self) -> Dict[str, Any]:
        """
        Returns a rich JSON-serializable graph payload.

        Includes color-coded nodes, weighted/labeled/colored edges,
        legend, and aggregate stats for the frontend.
        """
        return self.kg_builder.serialise()

    def get_last_extraction(self) -> Optional[Dict[str, Any]]:
        """Return the last GLiNER2 extraction result (for debugging / API)."""
        return self._last_extraction
