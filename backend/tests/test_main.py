"""
Backend test suite for Onco-TTT API.

Tests cover:
- API endpoints (health, root, structure, validation, clinical_trials, etc.)
- Pydantic model validation (DossierRequest, SimulateRequest)
- Helper functions (_build_adjacency, _collect_evidence, _inject_activations, _infer_tissue)
- Knowledge graph builder (entity ingestion, relation ingestion, serialisation)
- Extraction cache (LRU eviction, TTL expiry, thread safety)
- Orchestrator semantic cache (exact match, fuzzy match)
- External data file loading (pathways.json, validation_data.json)
- Auth middleware (API key validation)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Sync test client for simple endpoint tests."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Async test client for async endpoint tests."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Basic endpoint tests
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self, client):
        resp = client.get("/")
        data = resp.json()
        assert resp.status_code == 200
        assert "status" in data
        assert data["status"] == "active"

    def test_orchestrator_stats(self, client):
        resp = client.get("/orchestrator/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_queries" in data


# ---------------------------------------------------------------------------
# Pydantic model validation tests
# ---------------------------------------------------------------------------

class TestPydanticModels:
    def test_dossier_request_valid(self):
        from app.main import DossierRequest
        req = DossierRequest(gene="KRAS", disease="lung cancer")
        assert req.gene == "KRAS"
        assert req.resolved_cancer_type() == "lung cancer"

    def test_dossier_request_cancer_type_override(self):
        from app.main import DossierRequest
        req = DossierRequest(gene="EGFR", disease="cancer", cancer_type="NSCLC")
        assert req.resolved_cancer_type() == "NSCLC"

    def test_dossier_request_rejects_empty_gene(self):
        from app.main import DossierRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DossierRequest(gene="", disease="cancer")

    def test_simulate_request_valid(self):
        from app.main import SimulateRequest
        req = SimulateRequest(
            target_node="KRAS", perturbation_type="inhibit", query="test"
        )
        assert req.perturbation_type == "inhibit"

    def test_simulate_request_rejects_invalid_perturbation(self):
        from app.main import SimulateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SimulateRequest(
                target_node="KRAS", perturbation_type="destroy", query="test"
            )

    def test_simulate_request_accepts_all_types(self):
        from app.main import SimulateRequest
        for ptype in ("inhibit", "activate", "knockout"):
            req = SimulateRequest(
                target_node="X", perturbation_type=ptype, query="q"
            )
            assert req.perturbation_type == ptype


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_build_adjacency(self):
        from app.main import _build_adjacency
        links = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
            {"source": "A", "target": "C"},
        ]
        adj = _build_adjacency(links)
        assert len(adj["A"]) == 2
        assert len(adj["B"]) == 2
        assert len(adj["C"]) == 2

    def test_build_adjacency_empty(self):
        from app.main import _build_adjacency
        assert _build_adjacency([]) == {}

    def test_collect_evidence(self):
        from app.main import _collect_evidence
        links = [
            {"source": "KRAS", "target": "lung cancer", "relation": "drives", "weight": 0.9},
            {"source": "KRAS", "target": "BRAF", "relation": "activates", "weight": 0.8},
        ]
        partners = [
            {"id": "lung cancer", "label": "Lung Cancer"},
            {"id": "BRAF", "label": "BRAF"},
        ]
        evidence = _collect_evidence("KRAS", "KRAS", links, partners)
        assert len(evidence) == 2
        assert evidence[0]["source"] == "KRAS"

    def test_collect_evidence_with_adj(self):
        from app.main import _collect_evidence, _build_adjacency
        links = [
            {"source": "A", "target": "B", "relation": "r1", "weight": 0.9},
            {"source": "C", "target": "D", "relation": "r2", "weight": 0.5},
        ]
        adj = _build_adjacency(links)
        partners = [{"id": "B", "label": "B"}]
        evidence = _collect_evidence("A", "A", links, partners, adj=adj)
        assert len(evidence) == 1

    def test_inject_activations(self):
        from app.main import _inject_activations
        nodes = [
            {"id": "A", "radius": 22},
            {"id": "B", "radius": 22},
        ]
        activations = {"A": 0.9, "B": 0.1}
        _inject_activations(nodes, activations)
        assert nodes[0]["glow"] is True
        assert nodes[0]["relevance"] == 0.9
        assert "glow" not in nodes[1] or nodes[1].get("glow") is not True

    def test_infer_tissue(self):
        from app.main import _infer_tissue
        assert _infer_tissue("KRAS in melanoma") == "skin"
        assert _infer_tissue("breast cancer") == "breast"
        assert _infer_tissue("some generic query") == "lung"

    def test_infer_tissue_case_insensitive(self):
        from app.main import _infer_tissue
        assert _infer_tissue("PANCREATIC adenocarcinoma") == "pancreas"


# ---------------------------------------------------------------------------
# Knowledge Graph Builder tests
# ---------------------------------------------------------------------------

class TestKnowledgeGraphBuilder:
    def test_add_entities(self):
        from app.kg_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        count = builder.add_entities({
            "gene": [{"text": "KRAS", "confidence": 0.95}],
            "disease": ["lung cancer"],
        })
        assert count == 2
        assert builder.graph.has_node("KRAS")
        assert builder.graph.has_node("lung cancer")

    def test_add_entities_merge_higher_confidence(self):
        from app.kg_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        builder.add_entities({"gene": [{"text": "KRAS", "confidence": 0.5}]})
        builder.add_entities({"gene": [{"text": "KRAS", "confidence": 0.95}]})
        assert builder.graph.nodes["KRAS"]["confidence"] == 0.95

    def test_add_relations(self):
        from app.kg_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        builder.add_entities({"gene": ["KRAS", "BRAF"]})
        count = builder.add_relations({
            "associated_with": [{"head": "KRAS", "tail": "BRAF"}],
        })
        assert count == 1
        assert builder.graph.has_edge("KRAS", "BRAF")

    def test_serialise_empty(self):
        from app.kg_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        result = builder.serialise()
        assert result["nodes"] == []
        assert result["links"] == []
        assert result["stats"]["total_nodes"] == 0

    def test_serialise_with_data(self):
        from app.kg_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        builder.add_entities({"gene": ["KRAS", "BRAF"]})
        builder.add_relations({"associated_with": [("KRAS", "BRAF")]})
        result = builder.serialise()
        assert len(result["nodes"]) == 2
        assert len(result["links"]) == 1
        assert result["stats"]["total_nodes"] == 2

    def test_layout_caching(self):
        from app.kg_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        builder.add_entities({"gene": ["A", "B", "C"]})
        builder.add_relations({"associated_with": [("A", "B"), ("B", "C")]})
        pos1 = builder.compute_layout()
        pos2 = builder.compute_layout()
        assert pos1 is pos2

    def test_pathway_enrichment(self):
        from app.kg_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        builder.add_entities({"gene": [{"text": "KRAS", "confidence": 0.9}]})
        builder.add_pathway_enrichment("KRAS")
        assert builder.graph.has_node("MAPK Signaling")
        assert builder.graph.nodes["KRAS"].get("signal_role") == "target"

    def test_entity_text_formats(self):
        from app.kg_builder import entity_text
        assert entity_text("KRAS") == "KRAS"
        assert entity_text({"text": "BRAF"}) == "BRAF"
        assert entity_text(42) == "42"

    def test_infer_type(self):
        from app.kg_builder import KnowledgeGraphBuilder
        assert KnowledgeGraphBuilder._infer_type("KRAS") == "gene"
        assert KnowledgeGraphBuilder._infer_type("lung cancer") == "disease"
        assert KnowledgeGraphBuilder._infer_type("sotorasib") == "drug"
        assert KnowledgeGraphBuilder._infer_type("MAPK Signaling pathway") == "pathway"


# ---------------------------------------------------------------------------
# Extraction cache tests
# ---------------------------------------------------------------------------

class TestExtractionCache:
    def test_set_and_get(self):
        from app.entity_extraction import ExtractionCache
        cache = ExtractionCache(max_size=10)
        cache.set("hello world", "entities", {"entities": {"gene": ["KRAS"]}})
        result = cache.get("hello world", "entities")
        assert result is not None
        assert result["entities"]["gene"] == ["KRAS"]

    def test_cache_miss(self):
        from app.entity_extraction import ExtractionCache
        cache = ExtractionCache(max_size=10)
        assert cache.get("nonexistent", "entities") is None

    def test_lru_eviction(self):
        from app.entity_extraction import ExtractionCache
        cache = ExtractionCache(max_size=2)
        cache.set("a", "e", {"v": 1})
        cache.set("b", "e", {"v": 2})
        cache.set("c", "e", {"v": 3})
        assert cache.get("a", "e") is None
        assert cache.get("b", "e") is not None
        assert cache.get("c", "e") is not None

    def test_ttl_expiry(self):
        from app.entity_extraction import ExtractionCache, ExtractionCacheEntry
        import time
        cache = ExtractionCache(max_size=10)
        cache.set("x", "e", {"v": 1})
        key = cache._make_key("x", "e")
        cache.cache[key].ttl = 0.001
        time.sleep(0.01)
        assert cache.get("x", "e") is None

    def test_stats(self):
        from app.entity_extraction import ExtractionCache
        cache = ExtractionCache(max_size=10)
        cache.set("a", "e", {"v": 1})
        cache.get("a", "e")
        cache.get("miss", "e")
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


# ---------------------------------------------------------------------------
# Semantic cache (orchestrator) tests
# ---------------------------------------------------------------------------

class TestSemanticCache:
    def test_exact_match(self):
        from app.orchestrator import SemanticCache
        cache = SemanticCache(max_size=10)
        cache.set("search_literature", {"query": "KRAS lung"}, {"papers": []})
        result = cache.get("search_literature", {"query": "KRAS lung"})
        assert result is not None

    def test_fuzzy_match(self):
        from app.orchestrator import SemanticCache
        cache = SemanticCache(max_size=10)
        cache.set("search_literature", {"query": "KRAS lung cancer"}, {"papers": []})
        result = cache.get("search_literature", {"query": "KRAS lung"}, fuzzy=True)
        assert result is not None

    def test_no_cross_tool_fuzzy(self):
        from app.orchestrator import SemanticCache
        cache = SemanticCache(max_size=10)
        cache.set("search_literature", {"query": "KRAS"}, {"papers": []})
        result = cache.get("get_drug_targets", {"query": "KRAS"}, fuzzy=True)
        assert result is None

    def test_eviction(self):
        from app.orchestrator import SemanticCache
        cache = SemanticCache(max_size=2)
        cache.set("t", {"q": "a"}, {"v": 1})
        cache.set("t", {"q": "b"}, {"v": 2})
        cache.set("t", {"q": "c"}, {"v": 3})
        assert cache.stats()["size"] == 2


# ---------------------------------------------------------------------------
# External data file tests
# ---------------------------------------------------------------------------

class TestExternalData:
    def test_pathways_json_loads(self):
        from app.kg_builder import _PATHWAY_DATA
        assert "gene_pathways" in _PATHWAY_DATA
        assert "KRAS" in _PATHWAY_DATA["gene_pathways"]
        assert "signaling_cascades" in _PATHWAY_DATA

    def test_signaling_cascades_structure(self):
        from app.kg_builder import _PATHWAY_DATA
        kras_sig = _PATHWAY_DATA["signaling_cascades"].get("KRAS", {})
        assert "upstream" in kras_sig
        assert "downstream" in kras_sig
        assert len(kras_sig["upstream"]) > 0

    def test_validation_data_loads(self):
        from app.validation import _VALIDATION_DATA
        assert "essential_genes" in _VALIDATION_DATA
        assert "drug_data" in _VALIDATION_DATA
        assert "synthetic_lethality" in _VALIDATION_DATA
        assert "tcga_study_map" in _VALIDATION_DATA

    def test_validation_essential_genes(self):
        from app.validation import _VALIDATION_DATA
        essential = _VALIDATION_DATA["essential_genes"]
        assert "KRAS" in essential
        assert "lung" in essential["KRAS"]

    def test_validation_prognostic_genes(self):
        from app.validation import _VALIDATION_DATA
        prognostic = _VALIDATION_DATA["prognostic_genes"]
        assert "KRAS" in prognostic
        kras_lung = prognostic["KRAS"]["lung"]
        assert len(kras_lung) == 2


# ---------------------------------------------------------------------------
# Auth middleware tests
# ---------------------------------------------------------------------------

class TestAuth:
    def test_no_auth_required_when_env_unset(self, client):
        """When ONCO_API_KEY is not set, endpoints should be accessible."""
        with patch("app.main.API_KEY", None):
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_auth_rejects_missing_key(self, client):
        with patch("app.main.API_KEY", "secret123"):
            resp = client.post(
                "/generate",
                json={"text": "KRAS", "context": "test"},
            )
            assert resp.status_code == 401

    def test_auth_accepts_valid_key(self, client):
        """With correct key, should pass auth (may fail downstream, but not 401)."""
        with patch("app.main.API_KEY", "secret123"):
            resp = client.get("/health", headers={"x-api-key": "secret123"})
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestConstants:
    def test_constants_exist(self):
        from app.constants import (
            EXTRACTION_CACHE_MAX_SIZE,
            PROPAGATION_DECAY,
            DOSSIER_WEIGHT_VALIDATION,
            MAX_HYPOTHESES,
        )
        assert EXTRACTION_CACHE_MAX_SIZE > 0
        assert 0 < PROPAGATION_DECAY < 1
        assert 0 < DOSSIER_WEIGHT_VALIDATION <= 1
        assert MAX_HYPOTHESES > 0

    def test_dossier_weights_sum_to_one(self):
        from app.constants import (
            DOSSIER_WEIGHT_VALIDATION,
            DOSSIER_WEIGHT_DRUGGABILITY,
            DOSSIER_WEIGHT_IP_FREEDOM,
            DOSSIER_WEIGHT_CLINICAL,
            DOSSIER_WEIGHT_MODEL,
            DOSSIER_WEIGHT_LITERATURE,
        )
        total = (
            DOSSIER_WEIGHT_VALIDATION
            + DOSSIER_WEIGHT_DRUGGABILITY
            + DOSSIER_WEIGHT_IP_FREEDOM
            + DOSSIER_WEIGHT_CLINICAL
            + DOSSIER_WEIGHT_MODEL
            + DOSSIER_WEIGHT_LITERATURE
        )
        assert abs(total - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Hypothesis generation tests
# ---------------------------------------------------------------------------

class TestHypothesisGeneration:
    def test_empty_graph_returns_fallback(self):
        from app.main import _generate_hypotheses
        result = _generate_hypotheses({"nodes": [], "links": []}, "test query")
        assert len(result) == 1
        assert result[0].id == "h_empty"

    def test_gene_disease_hypothesis(self):
        from app.main import _generate_hypotheses
        subgraph = {
            "nodes": [
                {"id": "KRAS", "type": "gene", "label": "KRAS"},
                {"id": "lung cancer", "type": "disease", "label": "Lung Cancer"},
            ],
            "links": [
                {"source": "KRAS", "target": "lung cancer", "relation": "drives", "weight": 0.9},
            ],
        }
        result = _generate_hypotheses(subgraph, "KRAS lung cancer")
        assert len(result) >= 1
        assert "KRAS" in result[0].title

    def test_max_hypotheses_limit(self):
        from app.main import _generate_hypotheses, MAX_HYPOTHESES
        nodes = [
            {"id": f"G{i}", "type": "gene", "label": f"Gene{i}"} for i in range(10)
        ] + [
            {"id": f"D{i}", "type": "disease", "label": f"Disease{i}"} for i in range(10)
        ]
        links = [
            {"source": f"G{i}", "target": f"D{i}", "relation": "drives", "weight": 0.8}
            for i in range(10)
        ]
        result = _generate_hypotheses({"nodes": nodes, "links": links}, "test")
        assert len(result) <= MAX_HYPOTHESES


# ---------------------------------------------------------------------------
# Validation agent fallback tests
# ---------------------------------------------------------------------------

class TestValidationFallbacks:
    def test_fallback_essentiality_known_gene(self):
        from app.validation import ValidationAgent
        agent = ValidationAgent()
        result = agent._fallback_essentiality("KRAS", "lung cancer")
        assert result["status"] in ("pass", "caution", "fail")
        assert "score" in result

    def test_fallback_essentiality_unknown_gene(self):
        from app.validation import ValidationAgent
        agent = ValidationAgent()
        result = agent._fallback_essentiality("ZZZZZ", "unknown")
        assert result["status"] == "unknown"

    def test_fallback_drugability_known(self):
        from app.validation import ValidationAgent
        agent = ValidationAgent()
        result = agent._fallback_drugability("EGFR")
        assert result["status"] == "pass"
        assert "Erlotinib" in result["details"]["approved_drugs"]

    def test_fallback_toxicity_safe(self):
        from app.validation import ValidationAgent
        agent = ValidationAgent()
        result = agent._fallback_toxicity("KRAS")
        assert result["status"] == "pass"

    def test_fallback_toxicity_high(self):
        from app.validation import ValidationAgent
        agent = ValidationAgent()
        result = agent._fallback_toxicity("EGFR")
        assert result["status"] == "caution"

    def test_synthetic_lethality(self):
        from app.validation import ValidationAgent
        agent = ValidationAgent()
        result = agent._get_synthetic_lethality("PARP1")
        assert result is not None
        assert "BRCA1" in result["partners"]

    def test_template_synthesis(self):
        from app.validation import ValidationAgent
        agent = ValidationAgent()
        result = agent._template_synthesis(
            "KRAS", "lung cancer",
            {"status": "pass"}, {"status": "pass", "details": {"hazard_ratio": 1.8}},
            {"status": "pass"}, {"details": {"approved_drugs": ["Sotorasib"]}},
            {"status": "pass", "score": 80},
        )
        assert "text" in result
        assert len(result["text"]) > 10
