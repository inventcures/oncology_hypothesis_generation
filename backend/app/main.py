from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
import asyncio
import json
import logging
import time

logger = logging.getLogger(__name__)

from .ark import OncoGraph, OpenTargetsClient
from .ttt import (
    QueryAdaptiveRanker,
    RobustRanker,
    AdversarialReviewer,
    NeuroSymbolicLoop,
)
from .constants import (
    ACTIVATION_GLOW_THRESHOLD,
    ACTIVATION_RADIUS_BOOST,
    DEFAULT_NODE_RADIUS,
    MAX_HYPOTHESES,
    MAX_NODE_RADIUS,
    PROPAGATION_DECAY,
    PROPAGATION_EFFECT_THRESHOLD,
    PROPAGATION_MAX_HOPS,
    MAX_AFFECTED_NODES_RETURNED,
    DOSSIER_WEIGHT_VALIDATION,
    DOSSIER_WEIGHT_DRUGGABILITY,
    DOSSIER_WEIGHT_IP_FREEDOM,
    DOSSIER_WEIGHT_CLINICAL,
    DOSSIER_WEIGHT_MODEL,
    DOSSIER_WEIGHT_LITERATURE,
    TRIAL_SWEET_SPOT_MAX,
)
from .literature import LiteratureAgent
from .atlas import AtlasAgent
from .structure import StructureAgent
from .legal import PatentAgent
from .models import ModelAgent
from .protocols import ProtocolAgent
from .validation import ValidationAgent
from .orchestrator import AgentOrchestrator
from .entity_extraction import get_extractor
from .clinical_trials import ClinicalTrialsClient
from .schemas import (
    HypothesisObject, 
    ValidationScorecard, 
    MASTReport, 
    ValidationStatus,
    FidelityLevel
)

import httpx
import os
from contextlib import asynccontextmanager

shared_client = httpx.AsyncClient(timeout=60.0)


@asynccontextmanager
async def lifespan(app_instance):
    """Startup/shutdown lifecycle — properly close all persistent HTTP clients."""
    yield
    await shared_client.aclose()
    await ot_client.client.aclose()
    await lit_agent.client.aclose()


app = FastAPI(
    title="Onco-TTT API",
    description="Backend for Oncology Test-Time Training Engine",
    lifespan=lifespan,
)

# Enable CORS for frontend
allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,https://onco-ttt-frontend.up.railway.app,https://onco-hypothesis.up.railway.app,https://onco-hypothesis-generation.up.railway.app",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Cache-Control headers for GET endpoints ---
NO_CACHE_PATHS = {"/", "/health", "/orchestrator/stats"}
LONG_CACHE_PATHS = {"/gliner2/info"}


@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.method == "GET" and "cache-control" not in response.headers:
        path = request.url.path
        if path in NO_CACHE_PATHS:
            response.headers["cache-control"] = "no-cache"
        elif path in LONG_CACHE_PATHS:
            response.headers["cache-control"] = "public, max-age=3600"
        else:
            response.headers["cache-control"] = "public, max-age=300"
    return response


# --- API Key Auth (optional, for credit-burning endpoints) ---
API_KEY = os.getenv("ONCO_API_KEY")


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Require API key if ONCO_API_KEY is set. No-op if unset (dev mode)."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# --- Global State ---
# OncoGraph is NOT global — it is created per-request to avoid concurrent state corruption.
# Only the stateless OpenTargetsClient is shared (holds a persistent httpx connection pool).
ot_client = OpenTargetsClient()
base_ranker = QueryAdaptiveRanker()
robust_ranker = RobustRanker(base_ranker)
reviewer = AdversarialReviewer()
ttt_engine = NeuroSymbolicLoop(robust_ranker, reviewer)
lit_agent = LiteratureAgent()
atlas_agent = AtlasAgent()
structure_agent = StructureAgent(client=shared_client)
patent_agent = PatentAgent(client=shared_client)
model_agent = ModelAgent(client=shared_client)
protocol_agent = ProtocolAgent(client=shared_client)
ct_client = ClinicalTrialsClient(client=shared_client)
validation_agent = ValidationAgent(client=shared_client, ct_client=ct_client)

# Agent Orchestrator for smart routing (Claude Agents SDK)
orchestrator = AgentOrchestrator(
    literature_fn=lit_agent.search_papers,
    validation_agent=validation_agent,
    structure_agent=structure_agent,
    patent_agent=patent_agent,
    enable_cache=True,
)


# --- Data Models ---
class Query(BaseModel):
    text: str = Field(..., max_length=2000)
    context: Optional[str] = "General Oncology"


class Hypothesis(BaseModel):
    id: str
    title: str
    description: str
    confidence: float
    verified: bool
    novelty_score: float
    evidence: Optional[List[Dict[str, Any]]] = None


class GraphData(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    stats: Optional[Dict[str, Any]] = None
    legend: Optional[List[Dict[str, Any]]] = None


class Paper(BaseModel):
    id: Optional[str]
    title: str
    abstract: str
    authors: str
    year: Optional[int]
    citations: int
    journal: str
    url: Optional[str]
    source: str


class AtlasData(BaseModel):
    cells: List[Dict[str, Any]]


class GenerationResponse(BaseModel):
    hypotheses: List[Hypothesis]
    graph_context: GraphData
    papers: List[Paper] = []
    atlas: AtlasData = AtlasData(cells=[])
    extraction: Optional[Dict[str, Any]] = None


class ExtractionRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    include_relations: bool = True
    include_clinical: bool = False
    threshold: float = 0.4


class KGBuildRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    enrich_opentargets: bool = True
    width: float = 800
    height: float = 600


class DossierRequest(BaseModel):
    gene: str = Field(..., min_length=1, max_length=100)
    disease: str = Field(default="Cancer", max_length=200)
    mutation: Optional[str] = Field(default=None, max_length=100)
    cancer_type: Optional[str] = Field(default=None, max_length=200)
    tissue: str = Field(default="lung", max_length=50)

    def resolved_cancer_type(self) -> str:
        return self.cancer_type or self.disease


class SimulateRequest(BaseModel):
    target_node: str = Field(..., min_length=1, max_length=200)
    perturbation_type: Literal["inhibit", "activate", "knockout"] = "inhibit"
    query: str = Field(..., min_length=1, max_length=2000)


# --- Tissue Inference (single source of truth for backend) ---

TISSUE_MAP = [
    (["melanoma", "skin"], "skin"),
    (["breast"], "breast"),
    (["pancrea"], "pancreas"),
    (["colorectal", "colon"], "colon"),
    (["brain", "glioma", "glioblastoma"], "brain"),
    (["liver", "hepato"], "liver"),
    (["prostate"], "prostate"),
    (["ovarian", "ovary"], "ovary"),
    (["renal", "kidney"], "kidney"),
]


def _infer_tissue(query_text: str) -> str:
    """Infer tissue type from query text. Returns 'lung' as default."""
    q = query_text.lower()
    for keywords, tissue in TISSUE_MAP:
        if any(kw in q for kw in keywords):
            return tissue
    return "lung"


# --- Shared Helpers ---


def _build_adjacency(links: List[Dict]) -> Dict[str, List[Dict]]:
    """Pre-index links into a source→[link] adjacency map for O(1) lookups."""
    adj: Dict[str, List[Dict]] = {}
    for link in links:
        src = link.get("source", "")
        tgt = link.get("target", "")
        adj.setdefault(src, []).append(link)
        adj.setdefault(tgt, []).append(link)
    return adj


def _collect_evidence(
    node_id: str,
    node_label: str,
    links: List[Dict],
    partner_pool: List[Dict],
    default_relation: str = "associated_with",
    max_items: int = 5,
    adj: Optional[Dict[str, List[Dict]]] = None,
) -> List[Dict[str, Any]]:
    """Build evidence trail: edges connecting node_id to any node in partner_pool."""
    partner_map = {p.get("id"): p for p in partner_pool}
    relevant_links = adj.get(node_id, []) if adj else links
    items: List[Dict[str, Any]] = []
    for link in relevant_links:
        src, tgt = link.get("source"), link.get("target")
        if src == node_id and tgt in partner_map:
            partner = partner_map[tgt]
            items.append(
                {
                    "type": "graph_edge",
                    "source": node_label,
                    "target": partner.get("label") or partner.get("id"),
                    "relation": link.get("relation", default_relation),
                    "weight": link.get("weight", 0.5),
                }
            )
        elif tgt == node_id and src in partner_map:
            partner = partner_map[src]
            items.append(
                {
                    "type": "graph_edge",
                    "source": partner.get("label") or partner.get("id"),
                    "target": node_label,
                    "relation": link.get("relation", default_relation),
                    "weight": link.get("weight", 0.5),
                }
            )
        if len(items) >= max_items:
            break
    return items


def _inject_activations(nodes: List[Dict], activations: Dict[str, float]) -> None:
    """Inject activation scores into graph nodes for frontend rendering."""
    for node in nodes:
        node_id = node.get("id", "")
        act_score = activations.get(node_id, 0.0)
        node["relevance"] = act_score
        if act_score > ACTIVATION_GLOW_THRESHOLD:
            node["glow"] = True
            node["radius"] = min(
                node.get("radius", DEFAULT_NODE_RADIUS)
                * (1 + act_score * ACTIVATION_RADIUS_BOOST),
                MAX_NODE_RADIUS,
            )


# --- Hypothesis Generation (dynamic, based on extracted entities & relations) ---


def _generate_hypotheses(
    subgraph_data: dict,
    query_text: str,
    activations: Optional[Dict[str, float]] = None,
) -> List[Hypothesis]:
    """
    Generate hypotheses dynamically from the knowledge graph structure.

    Uses the actual extracted entities and their relationships to form
    testable biological hypotheses rather than pattern-matching on node IDs.
    When activation scores are provided, prioritizes high-relevance nodes.
    """
    act = activations or {}
    nodes = subgraph_data.get("nodes", [])
    links = subgraph_data.get("links", [])
    adj = _build_adjacency(links)
    if not nodes:
        return [
            Hypothesis(
                id="h_empty",
                title="Insufficient Data",
                description="Not enough biological entities could be extracted. Try rephrasing with specific gene/drug/disease names.",
                confidence=0.1,
                verified=False,
                novelty_score=0.5,
            )
        ]

    # Classify nodes — sort each group by activation relevance (highest first)
    def _by_relevance(n: dict) -> float:
        return act.get(n.get("id", ""), 0.0)

    genes = sorted(
        [n for n in nodes if n.get("type", "").lower() in ("gene", "target")],
        key=_by_relevance,
        reverse=True,
    )
    diseases = sorted(
        [n for n in nodes if n.get("type", "").lower() == "disease"],
        key=_by_relevance,
        reverse=True,
    )
    drugs = sorted(
        [n for n in nodes if n.get("type", "").lower() == "drug"],
        key=_by_relevance,
        reverse=True,
    )
    pathways = sorted(
        [n for n in nodes if n.get("type", "").lower() == "pathway"],
        key=_by_relevance,
        reverse=True,
    )
    mechanisms = sorted(
        [n for n in nodes if n.get("type", "").lower() == "mechanism"],
        key=_by_relevance,
        reverse=True,
    )
    mutations = sorted(
        [n for n in nodes if n.get("type", "").lower() == "mutation"],
        key=_by_relevance,
        reverse=True,
    )

    hypotheses: List[Hypothesis] = []
    h_idx = 0

    # --- Strategy 1: Gene-Disease association hypotheses ---
    for gene in genes[:2]:
        gene_name = gene.get("label") or gene.get("id", "Unknown")
        # Find diseases linked to this gene
        linked_diseases = []
        for link in links:
            partner = None
            if link.get("source") == gene.get("id"):
                partner = next(
                    (n for n in diseases if n.get("id") == link.get("target")), None
                )
            elif link.get("target") == gene.get("id"):
                partner = next(
                    (n for n in diseases if n.get("id") == link.get("source")), None
                )
            if partner:
                linked_diseases.append(
                    (partner.get("label") or partner.get("id"), link.get("weight", 0.5))
                )

        if linked_diseases:
            top_disease, weight = max(linked_diseases, key=lambda x: x[1])
            h_idx += 1
            gene_relevance = act.get(gene.get("id", ""), 0.5)
            conf = min(0.95, 0.5 + weight * 0.25 + gene_relevance * 0.2)
            evidence_items = _collect_evidence(
                gene.get("id", ""), gene_name, links, diseases, adj=adj
            )
            hypotheses.append(
                Hypothesis(
                    id=f"h{h_idx}",
                    title=f"{gene_name} as Driver in {top_disease}",
                    description=f"Analysis identified {gene_name} as a key node connected to {top_disease} with {len(linked_diseases)} supporting associations in the knowledge graph.",
                    confidence=round(conf, 2),
                    verified=conf > 0.8,
                    novelty_score=round(max(0.3, 1.0 - conf), 2),
                    evidence=evidence_items[:5] if evidence_items else None,
                )
            )

    # --- Strategy 2: Drug-Gene targeting hypotheses ---
    for drug in drugs[:2]:
        drug_name = drug.get("label") or drug.get("id", "Unknown")
        targets = []
        for link in links:
            relation = (link.get("relation") or "").lower()
            if "target" in relation or "inhibit" in relation:
                if link.get("source") == drug.get("id"):
                    t = next(
                        (n for n in genes if n.get("id") == link.get("target")), None
                    )
                    if t:
                        targets.append(t.get("label") or t.get("id"))
                elif link.get("target") == drug.get("id"):
                    t = next(
                        (n for n in genes if n.get("id") == link.get("source")), None
                    )
                    if t:
                        targets.append(t.get("label") or t.get("id"))

        if targets:
            h_idx += 1
            evidence_items = _collect_evidence(
                drug.get("id", ""),
                drug_name,
                links,
                genes,
                default_relation="targets",
                adj=adj,
            )
            hypotheses.append(
                Hypothesis(
                    id=f"h{h_idx}",
                    title=f"{drug_name} Targets {', '.join(targets[:2])}",
                    description=f"{drug_name} may modulate {', '.join(targets)} based on extracted relationship evidence from the query context.",
                    confidence=0.75,
                    verified=True,
                    novelty_score=0.6,
                    evidence=evidence_items[:5] if evidence_items else None,
                )
            )

    # --- Strategy 3: Mutation-Resistance / Mechanism hypotheses ---
    for mut in mutations[:1]:
        mut_name = mut.get("label") or mut.get("id", "Unknown")
        related_mechs = [(m.get("label") or m.get("id")) for m in mechanisms]
        related_genes = [(g.get("label") or g.get("id")) for g in genes[:2]]
        context = related_mechs[:1] or related_genes[:1] or ["downstream effectors"]
        h_idx += 1
        evidence_items = _collect_evidence(
            mut.get("id", ""), mut_name, links, nodes, adj=adj
        )
        hypotheses.append(
            Hypothesis(
                id=f"h{h_idx}",
                title=f"Mutation {mut_name} & Resistance",
                description=f"The {mut_name} mutation may drive resistance via {context[0]}, presenting a potential therapeutic vulnerability.",
                confidence=0.82,
                verified=False,
                novelty_score=0.78,
                evidence=evidence_items[:5] if evidence_items else None,
            )
        )

    # --- Strategy 4: Pathway involvement ---
    for pw in pathways[:1]:
        pw_name = pw.get("label") or pw.get("id", "Unknown")
        linked_genes_in_pw = []
        for link in links:
            if link.get("source") == pw.get("id") or link.get("target") == pw.get("id"):
                partner_id = (
                    link.get("target")
                    if link.get("source") == pw.get("id")
                    else link.get("source")
                )
                partner = next((n for n in genes if n.get("id") == partner_id), None)
                if partner:
                    linked_genes_in_pw.append(partner.get("label") or partner.get("id"))
        if linked_genes_in_pw:
            h_idx += 1
            evidence_items = _collect_evidence(
                pw.get("id", ""),
                pw_name,
                links,
                genes,
                default_relation="involves",
                adj=adj,
            )
            hypotheses.append(
                Hypothesis(
                    id=f"h{h_idx}",
                    title=f"{pw_name} Pathway Involvement",
                    description=f"The {pw_name} pathway connects {', '.join(linked_genes_in_pw[:3])}, suggesting coordinated signaling that may be therapeutically targetable.",
                    confidence=0.7,
                    verified=False,
                    novelty_score=0.85,
                    evidence=evidence_items[:5] if evidence_items else None,
                )
            )

    # --- Fallback: if no specific hypotheses could be formed ---
    if not hypotheses:
        top_node = nodes[0]
        top_name = top_node.get("label") or top_node.get("id", "Unknown")
        top_type = top_node.get("type", "entity")
        hypotheses.append(
            Hypothesis(
                id="h_gen",
                title=f"Novel Association: {top_name}",
                description=f"Analysis of {top_name} ({top_type}) reveals connections to {len(links)} other entities that merit further investigation.",
                confidence=0.55,
                verified=False,
                novelty_score=0.9,
            )
        )

    return hypotheses[:MAX_HYPOTHESES]


# --- Routes ---


@app.get("/")
def read_root():
    return {"message": "Onco-TTT API is running", "status": "active"}


@app.post(
    "/generate",
    response_model=GenerationResponse,
    dependencies=[Depends(verify_api_key)],
)
async def generate_hypotheses(query: Query):
    """
    Main hypothesis generation pipeline.

    Runs GLiNER2 entity extraction, knowledge graph construction with
    OpenTargets enrichment, graph-based activation propagation, literature
    search, and atlas projection concurrently.
    """
    # --- Request-scoped OncoGraph (avoids concurrent state corruption) ---
    req_graph = OncoGraph()
    req_graph.ot_client = ot_client  # share the persistent HTTP connection pool

    # Infer tissue type from query
    tissue_type = _infer_tissue(query.text)

    # 1. Run KG build, literature search, and atlas fetch CONCURRENTLY.
    #    Each task is independent — a failure in one must not kill the others.
    #    Atlas is sync, so wrap in asyncio.to_thread to avoid blocking the event loop.
    kg_result, papers_result, atlas_result = await asyncio.gather(
        req_graph.build_from_query(query.text),
        lit_agent.search_papers(query.text, limit=6),
        asyncio.to_thread(atlas_agent.fetch_tumor_atlas, tissue_type, 300),
        return_exceptions=True,
    )

    # Handle partial failures gracefully
    if isinstance(kg_result, BaseException):
        logger.error("KG build failed: %s", kg_result)

    if isinstance(papers_result, BaseException):
        logger.error("Literature search failed: %s", papers_result)
        papers_result = []

    if isinstance(atlas_result, BaseException):
        logger.error("Atlas fetch failed: %s", atlas_result)
        atlas_result = {"cells": [], "error": str(atlas_result)}

    papers = papers_result
    atlas_data = atlas_result

    # 2. Query-Adaptive Ranking: Propagate activations through graph
    #    Scores reflect how relevant each node is to this specific query.
    #    Uses Agentic Neuro-Symbolic Loop (Deep Think) for robust reasoning.
    deep_think_result = await ttt_engine.run_deep_think(req_graph.graph, query.text)
    activations = deep_think_result.get("activations", {})

    # 3. Get Rich Graph Data with Layout, colors, edge labels
    subgraph_data = req_graph.get_subgraph_data()

    _inject_activations(subgraph_data.get("nodes", []), activations)

    # 4. Hypothesis Generation — dynamically from extracted entities & relations
    #    Pass activation scores so hypotheses prioritize high-relevance nodes
    hypotheses = _generate_hypotheses(subgraph_data, query.text, activations)

    return GenerationResponse(
        hypotheses=hypotheses,
        graph_context=subgraph_data,
        papers=papers,
        atlas=atlas_data,
        extraction=req_graph.get_last_extraction(),
    )


# --- GLiNER2 Entity Extraction Endpoint ---


@app.post("/extract_entities")
async def extract_entities(req: ExtractionRequest):
    """
    Standalone GLiNER2 entity extraction endpoint.

    Extracts oncology entities (genes, diseases, drugs, pathways, mutations,
    cell types, biomarkers, mechanisms) from arbitrary text.

    Optionally includes relation extraction and clinical context parsing.
    """
    extractor = get_extractor()

    if req.include_relations:
        result = extractor.extract_all(req.text)
    else:
        result = extractor.extract_entities(req.text, threshold=req.threshold)

    if req.include_clinical:
        clinical = extractor.extract_clinical_context(req.text)
        result["clinical_context"] = clinical.get("clinical_context", [])

    return result


# --- Knowledge Graph Build Endpoint ---


@app.post("/build_kg")
async def build_knowledge_graph(req: KGBuildRequest):
    """
    Build a rich knowledge graph from arbitrary text.

    Pipeline:
    1. GLiNER2 extracts entities & relations from text
    2. (Optional) OpenTargets enriches with validated associations
    3. Returns color-coded, interactive graph JSON

    Response includes:
    - nodes: with type, color, border_color, confidence, radius, glow
    - links: with relation, label, weight, color, thickness, animated
    - stats: total_nodes, total_edges, entity_types, relation_types
    - legend: color-coded type legend with counts
    """
    from .kg_builder import KnowledgeGraphBuilder

    extractor = get_extractor()

    # Extract entities and relations
    extraction = extractor.extract_all(req.text)

    # Build KG
    builder = KnowledgeGraphBuilder()
    builder.add_entities(extraction.get("entities", {}))
    builder.add_relations(extraction.get("relations", {}))

    # OpenTargets enrichment
    if req.enrich_opentargets:
        genes = extraction.get("entities", {}).get("gene", [])
        if genes:
            best_gene = (
                genes[0] if isinstance(genes[0], str) else genes[0].get("text", "")
            )
            if best_gene:
                seed = await ot_client.search_entity(best_gene)
                if seed:
                    if seed["entity"] == "target":
                        neighbors = await ot_client.get_target_associations(seed["id"])
                    else:
                        neighbors = await ot_client.get_disease_associations(seed["id"])
                    builder.add_opentargets_associations(
                        seed["name"], seed["entity"], neighbors
                    )
                    builder.add_pathway_enrichment(best_gene)

    # Serialise
    kg_data = builder.serialise(width=req.width, height=req.height)
    kg_data["extraction"] = extraction

    return kg_data


# --- GLiNER2 Model Info & Cache Stats ---


@app.get("/gliner2/info")
def gliner2_model_info():
    """
    Returns GLiNER2 model status and extraction cache statistics.
    """
    extractor = get_extractor()
    return {
        "model": extractor.model_info(),
        "cache": extractor.cache_stats(),
    }


# --- Existing Routes (unchanged) ---


@app.get("/structure/{gene}")
async def get_structure_analysis(
    gene: str, mutation: Optional[str] = None, include_pdb: bool = False
):
    """
    Module A: Virtual Structural Biologist
    Fetches AlphaFold structure and predicts binding pockets.
    """
    result = await structure_agent.fetch_structure(gene, mutation)
    if not include_pdb and isinstance(result, dict):
        result.pop("pdb_content", None)
    return result


@app.get("/patents/check")
async def check_patents(gene: str, disease: str = "Cancer"):
    """
    Module B: Patent Hawk
    Checks for IP saturation (Freedom to Operate).
    """
    return await patent_agent.search_patents(gene, disease)


@app.get("/models/recommend")
async def recommend_models(
    tissue: str, mutation: Optional[str] = None, exclude_problematic: bool = True
):
    """
    Module C: Model Matchmaker
    Finds the best cell line 'avatar' for the experiment.
    """
    return await model_agent.find_models(tissue, mutation, exclude_problematic)


@app.get("/protocols/generate")
async def generate_protocol(
    method: str,
    gene: str,
    cell_line: str,
    target_sequence: Optional[str] = None,
    use_llm: bool = True,
):
    """
    Module D: Protocol Droid
    Generates experimental protocols with gRNA design.
    """
    return await protocol_agent.generate_protocol(
        method, gene, cell_line, target_sequence, use_llm
    )


@app.get("/validate")
async def validate_hypothesis(
    gene: str, disease: str, cancer_type: Optional[str] = None
):
    """
    v2 Validation Dashboard
    Runs comprehensive validation checks on a hypothesis.
    """
    return await validation_agent.validate_hypothesis(gene, disease, cancer_type)


@app.get("/clinical_trials")
async def get_clinical_trials(
    gene: str,
    disease: str = "cancer",
    status: str = "ALL",
    phase: str = "ALL",
    page_size: int = 50,
):
    """
    Search ClinicalTrials.gov for trials relevant to a gene target and disease.
    Returns individual trials and aggregated summary statistics.
    """
    return await ct_client.search_trials(
        gene=gene,
        disease=disease,
        status=status,
        phase=phase,
        page_size=page_size,
    )


@app.get("/papers/{paper_id}/citations")
async def get_paper_citations(paper_id: str, limit: int = 10):
    """
    Get papers that cite a given paper (by Semantic Scholar ID).
    Exposes LiteratureAgent.get_citations for the citation network feature.
    """
    return await lit_agent.get_citations(paper_id, limit)


@app.get("/papers/{paper_id}/references")
async def get_paper_references(paper_id: str, limit: int = 10):
    """
    Get papers referenced by a given paper.
    Exposes LiteratureAgent.get_references for the citation network feature.
    """
    return await lit_agent.get_references(paper_id, limit)


@app.post("/smart_query")
async def smart_query(query: Query):
    """
    Intelligent query routing using Claude Agents SDK.
    """
    result = await orchestrator.process_query(query=query.text, context=query.context)
    return result


@app.get("/orchestrator/stats")
def get_orchestrator_stats():
    """
    Returns statistics about the orchestrator's performance.
    """
    return orchestrator.get_stats()


@app.post("/dossier", dependencies=[Depends(verify_api_key)])
async def generate_dossier(req: DossierRequest):
    gene = req.gene
    disease = req.disease
    mutation = req.mutation
    cancer_type = req.resolved_cancer_type()
    tissue = req.tissue

    # Run all analyses in parallel
    results = await asyncio.gather(
        validation_agent.validate_hypothesis(gene, disease, cancer_type),
        structure_agent.fetch_structure(gene, mutation),
        patent_agent.search_patents(gene, disease),
        model_agent.find_models(tissue, mutation or gene, True),
        protocol_agent.generate_protocol("crispr", gene, "auto", None, True),
        ct_client.search_trials(gene=gene, disease=disease),
        lit_agent.search_papers(f"{gene} {disease}", limit=6),
        return_exceptions=True,
    )

    # Unpack with safe fallbacks
    validation = results[0] if not isinstance(results[0], BaseException) else None
    structure = results[1] if not isinstance(results[1], BaseException) else None
    patents = results[2] if not isinstance(results[2], BaseException) else None
    models = results[3] if not isinstance(results[3], BaseException) else None
    protocol = results[4] if not isinstance(results[4], BaseException) else None
    trials = results[5] if not isinstance(results[5], BaseException) else None
    papers = results[6] if not isinstance(results[6], BaseException) else []

    # Compute Go/No-Go score (weighted composite)
    scores = []
    if validation and isinstance(validation, dict):
        scores.append(
            (
                "validation",
                validation.get("overall_score", 0.5),
                DOSSIER_WEIGHT_VALIDATION,
            )
        )
    if structure and isinstance(structure, dict):
        scores.append(
            (
                "druggability",
                structure.get("druggability_score", 0.5),
                DOSSIER_WEIGHT_DRUGGABILITY,
            )
        )
    if patents and isinstance(patents, dict):
        patent_score = 1.0 - (patents.get("scooped_score", 50) / 100)
        scores.append(("ip_freedom", patent_score, DOSSIER_WEIGHT_IP_FREEDOM))
    if trials and isinstance(trials, dict):
        trial_count = trials.get("summary", {}).get("total_count", 0)
        trial_score = (
            min(1.0, trial_count / TRIAL_SWEET_SPOT_MAX)
            if trial_count <= TRIAL_SWEET_SPOT_MAX
            else max(0.3, 1.0 - (trial_count - TRIAL_SWEET_SPOT_MAX) / 100)
        )
        scores.append(("clinical_validation", trial_score, DOSSIER_WEIGHT_CLINICAL))
    if models and isinstance(models, dict):
        top_pick = models.get("top_pick", {})
        model_score = (top_pick.get("match_score", 50) / 100) if top_pick else 0.5
        scores.append(("model_availability", model_score, DOSSIER_WEIGHT_MODEL))
    scores.append(("literature", min(1.0, len(papers) / 6) if papers else 0.3, 0.10))

    total_weight = sum(w for _, _, w in scores)
    go_no_go = (
        sum(s * w for _, s, w in scores) / total_weight if total_weight > 0 else 0.5
    )

    return {
        "gene": gene,
        "disease": disease,
        "mutation": mutation,
        "timestamp": int(asyncio.get_event_loop().time()),
        "go_no_go_score": round(go_no_go, 3),
        "go_no_go_label": "Strong Go"
        if go_no_go > 0.75
        else "Go"
        if go_no_go > 0.6
        else "Conditional"
        if go_no_go > 0.45
        else "No-Go",
        "sections": {
            "validation": validation,
            "structure": structure,
            "patents": patents,
            "models": models,
            "protocol": protocol,
            "trials": trials,
            "papers": papers,
        },
        "score_breakdown": [
            {"name": n, "score": round(s, 3), "weight": w} for n, s, w in scores
        ],
    }


@app.get("/indications")
async def get_indication_expansion(gene: str, limit: int = 20):
    """
    For a given gene/target, find all associated diseases ranked by evidence score.
    Uses OpenTargets associations with larger page size.
    """
    # First resolve the gene to an Ensembl ID
    seed = await ot_client.search_entity(gene)
    if not seed or seed["entity"] != "target":
        return {
            "gene": gene,
            "indications": [],
            "error": "Gene not found in OpenTargets",
        }

    # Get associations (diseases for this target)
    neighbors = await ot_client.get_target_associations(seed["id"])

    indications = []
    for assoc in neighbors:
        indications.append(
            {
                "disease": assoc.get("name", "Unknown"),
                "disease_id": assoc.get("id", ""),
                "score": round(assoc.get("score", 0), 4),
                "entity_type": assoc.get("entity", "disease"),
            }
        )

    # Sort by score descending and apply limit
    indications.sort(key=lambda x: x["score"], reverse=True)
    indications = indications[:limit]

    return {
        "gene": gene,
        "ensembl_id": seed["id"],
        "total": len(indications),
        "indications": indications,
    }


@app.post("/simulate", dependencies=[Depends(verify_api_key)])
async def simulate_perturbation(req: SimulateRequest):
    """
    Simulate what happens when a node is perturbed (inhibited/activated/knocked out).
    Uses spreading activation through the knowledge graph.
    """
    target_node = req.target_node
    perturbation_type = req.perturbation_type
    query_text = req.query

    # Build the KG
    req_graph = OncoGraph()
    req_graph.ot_client = ot_client
    await req_graph.build_from_query(query_text)

    graph = req_graph.graph  # networkx graph
    if target_node not in graph:
        return {"error": f"Node '{target_node}' not found in knowledge graph"}

    # Determine initial perturbation signal
    signal = {"inhibit": -1.0, "activate": 1.0, "knockout": -1.0}[perturbation_type]

    # Propagate through graph using BFS with decay
    effects = {target_node: signal}
    visited = {target_node}
    queue = [(target_node, signal, 0)]  # (node, effect, distance)
    decay = PROPAGATION_DECAY

    while queue:
        current, current_effect, dist = queue.pop(0)
        if dist >= PROPAGATION_MAX_HOPS:
            continue
        for neighbor in graph.neighbors(current):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            edge_data = graph.get_edge_data(current, neighbor) or {}
            edge_weight = edge_data.get("weight", 0.5)
            relation = (edge_data.get("relation", "") or "").lower()

            # Determine propagation sign based on relation type
            if "inhibit" in relation or "suppress" in relation or "block" in relation:
                propagation_sign = -1
            else:
                propagation_sign = 1

            neighbor_effect = current_effect * decay * edge_weight * propagation_sign
            if abs(neighbor_effect) > PROPAGATION_EFFECT_THRESHOLD:
                effects[neighbor] = neighbor_effect
                queue.append((neighbor, neighbor_effect, dist + 1))

    # Build response with node metadata
    subgraph = req_graph.get_subgraph_data()
    node_map = {n["id"]: n for n in subgraph.get("nodes", [])}

    affected_nodes = []
    for node_id, effect in sorted(
        effects.items(), key=lambda x: abs(x[1]), reverse=True
    ):
        if node_id == target_node:
            continue
        node_info = node_map.get(node_id, {})
        affected_nodes.append(
            {
                "id": node_id,
                "label": node_info.get("label", node_id),
                "type": node_info.get("type", "unknown"),
                "effect": round(effect, 4),
                "direction": "downregulated" if effect < 0 else "upregulated",
            }
        )

    # Summarize pathway-level effects
    pathway_effects = []
    for node in affected_nodes:
        if node["type"] == "pathway":
            pathway_effects.append(
                {
                    "pathway": node["label"],
                    "net_effect": node["effect"],
                    "description": f"{node['label']} predicted to be {'suppressed' if node['effect'] < 0 else 'activated'} ({abs(node['effect']) * 100:.0f}% effect)",
                }
            )

    return {
        "target_node": target_node,
        "perturbation_type": perturbation_type,
        "total_affected": len(affected_nodes),
        "affected_nodes": affected_nodes[:MAX_AFFECTED_NODES_RETURNED],
        "pathway_effects": pathway_effects,
        "graph": subgraph,  # Return updated graph for visualization
    }


@app.get("/mutation_frequency")
async def get_mutation_frequency(gene: str):
    """
    Get mutation frequency data from ICGC Data Portal (open access).
    Returns mutation counts across cancer types.
    """
    try:
        search_resp = await shared_client.get(
            "https://dcc.icgc.org/api/v1/genes", params={"query": gene, "size": 1}
        )
        gene_id = gene
        if search_resp.status_code == 200:
            hits = search_resp.json().get("hits", [])
            if hits:
                gene_id = hits[0].get("id", gene)

        mut_resp = await shared_client.get(
            f"https://dcc.icgc.org/api/v1/genes/{gene_id}/mutations",
            params={
                "size": 50,
                "sort": "affectedDonorCountFiltered",
                "order": "desc",
            },
        )

        if mut_resp.status_code != 200:
            return {
                "gene": gene,
                "mutations": [],
                "source": "icgc",
                "error": f"ICGC returned {mut_resp.status_code}",
            }

        data = mut_resp.json()
        hits = data.get("hits", [])

        mutations = []
        for hit in hits[:30]:
            mutations.append(
                {
                    "id": hit.get("id", ""),
                    "mutation": hit.get("mutation", ""),
                    "type": hit.get("type", ""),
                    "chromosome": hit.get("chromosome", ""),
                    "start": hit.get("start"),
                    "consequence": hit.get("consequenceType", ""),
                    "affected_donors": hit.get("affectedDonorCountFiltered", 0),
                    "functional_impact": hit.get("functionalImpact", "Unknown"),
                }
            )

        return {
            "gene": gene,
            "gene_id": gene_id,
            "total_mutations": data.get("pagination", {}).get("total", 0),
            "mutations": mutations,
            "source": "icgc",
        }
    except Exception as e:
        logger.error("ICGC mutation frequency failed: %s", e)
        return {"gene": gene, "mutations": [], "source": "icgc", "error": str(e)}


@app.get("/chembl/bioactivity")
async def get_chembl_bioactivity(gene: str, limit: int = 20):
    """
    Get bioactivity data (IC50, Ki, EC50) from ChEMBL for a target gene.
    """
    base_url = "https://www.ebi.ac.uk/chembl/api/data"

    try:
        target_resp = await shared_client.get(
            f"{base_url}/target/search.json", params={"q": gene, "limit": 3}
        )

        if target_resp.status_code != 200:
            return {
                "gene": gene,
                "activities": [],
                "error": f"ChEMBL target search failed: {target_resp.status_code}",
            }

        targets = target_resp.json().get("targets", [])
        if not targets:
            return {
                "gene": gene,
                "activities": [],
                "error": "Target not found in ChEMBL",
            }

        target_chembl_id = targets[0].get("target_chembl_id", "")
        target_name = targets[0].get("pref_name", gene)

        activity_resp = await shared_client.get(
            f"{base_url}/activity.json",
            params={
                "target_chembl_id": target_chembl_id,
                "limit": limit,
                "standard_type__in": "IC50,Ki,EC50,Kd",
                "pchembl_value__isnull": "false",
                "order_by": "-pchembl_value",
            },
        )

        if activity_resp.status_code != 200:
            return {
                "gene": gene,
                "target_chembl_id": target_chembl_id,
                "activities": [],
                "error": "ChEMBL activity fetch failed",
            }

        activities_data = activity_resp.json().get("activities", [])

        activities = []
        seen_molecules = set()
        for act in activities_data:
            mol_id = act.get("molecule_chembl_id", "")
            if mol_id in seen_molecules:
                continue
            seen_molecules.add(mol_id)
            activities.append(
                {
                    "molecule_chembl_id": mol_id,
                    "molecule_name": act.get("molecule_pref_name") or mol_id,
                    "standard_type": act.get("standard_type", ""),
                    "standard_value": act.get("standard_value"),
                    "standard_units": act.get("standard_units", ""),
                    "pchembl_value": act.get("pchembl_value"),
                    "assay_type": act.get("assay_type", ""),
                    "assay_description": act.get("assay_description", ""),
                }
            )

        return {
            "gene": gene,
            "target_chembl_id": target_chembl_id,
            "target_name": target_name,
            "total_activities": len(activities),
            "activities": activities,
            "source": "chembl",
        }
    except Exception as e:
        logger.error("ChEMBL bioactivity failed: %s", e)
        return {"gene": gene, "activities": [], "source": "chembl", "error": str(e)}


@app.get("/drug_safety")
async def get_drug_safety(drug_name: str, limit: int = 10):
    """
    Get adverse event reports from OpenFDA for a drug.
    """
    try:
        resp = await shared_client.get(
            "https://api.fda.gov/drug/event.json",
            params={
                "search": f'patient.drug.medicinalproduct:"{drug_name}"',
                "count": "patient.reaction.reactionmeddrapt.exact",
                "limit": limit,
            },
        )

        if resp.status_code != 200:
            return {
                "drug": drug_name,
                "adverse_events": [],
                "error": f"OpenFDA returned {resp.status_code}",
            }

        data = resp.json()
        results = data.get("results", [])

        adverse_events = [
            {"reaction": r.get("term", ""), "count": r.get("count", 0)} for r in results
        ]

        count_resp = await shared_client.get(
            "https://api.fda.gov/drug/event.json",
            params={
                "search": f'patient.drug.medicinalproduct:"{drug_name}"',
                "limit": 1,
            },
        )
        total_reports = 0
        if count_resp.status_code == 200:
            meta = count_resp.json().get("meta", {}).get("results", {})
            total_reports = meta.get("total", 0)

        return {
            "drug": drug_name,
            "total_reports": total_reports,
            "top_adverse_events": adverse_events,
            "source": "openfda",
        }
    except Exception as e:
        logger.error("OpenFDA drug safety failed: %s", e)
        return {
            "drug": drug_name,
            "adverse_events": [],
            "source": "openfda",
            "error": str(e),
        }


@app.post("/generate_stream", dependencies=[Depends(verify_api_key)])
async def generate_stream(query: Query):
    """
    SSE streaming version of /generate. Sends progress events as each step completes.
    """

    async def event_stream():
        import time as _time

        _t0 = _time.monotonic()

        def _sse(payload: dict) -> str:
            payload["elapsed_ms"] = int((_time.monotonic() - _t0) * 1000)
            return f"data: {json.dumps(payload)}\n\n"

        req_graph = OncoGraph()
        req_graph.ot_client = ot_client
        tissue_type = _infer_tissue(query.text)

        yield _sse(
            {
                "type": "status",
                "message": "Extracting biological entities...",
                "progress": 0.1,
            }
        )

        # Run KG build
        try:
            kg_result = await req_graph.build_from_query(query.text)
            subgraph_data = req_graph.get_subgraph_data()
            yield _sse(
                {
                    "type": "kg_complete",
                    "message": "Knowledge graph built",
                    "progress": 0.4,
                    "data": {
                        "node_count": len(subgraph_data.get("nodes", [])),
                        "edge_count": len(subgraph_data.get("links", [])),
                    },
                }
            )
        except Exception as e:
            yield _sse({"type": "error", "step": "kg", "message": str(e)})
            subgraph_data = {"nodes": [], "links": []}

        # Run lit search in parallel with atlas
        yield _sse(
            {
                "type": "status",
                "message": "Searching literature & atlas...",
                "progress": 0.5,
            }
        )

        papers_result, atlas_result = await asyncio.gather(
            lit_agent.search_papers(query.text, limit=6),
            asyncio.to_thread(atlas_agent.fetch_tumor_atlas, tissue_type, 300),
            return_exceptions=True,
        )

        papers = papers_result if not isinstance(papers_result, BaseException) else []
        atlas_data = (
            atlas_result
            if not isinstance(atlas_result, BaseException)
            else {"cells": []}
        )

        yield _sse(
            {
                "type": "papers_complete",
                "message": f"Found {len(papers)} papers",
                "progress": 0.7,
                "data": {"paper_count": len(papers)},
            }
        )

        # Activation ranking
        yield _sse(
            {
                "type": "status",
                "message": "Initializing Deep Think engine...",
                "progress": 0.8,
            }
        )

        deep_think_result = None
        # Use streaming version of Deep Think to provide granular feedback
        async for event in ttt_engine.run_deep_think_stream(
            req_graph.graph, query.text
        ):
            if event["type"] == "step_start":
                yield _sse(
                    {
                        "type": "status",
                        "message": event["message"],
                        "progress": 0.8 + (event["step"] * 0.03),  # Increment slightly
                    }
                )
            elif event["type"] == "status":
                yield _sse({"type": "status", "message": event["message"]})
            elif event["type"] == "result":
                deep_think_result = event["data"]

        activations = (
            deep_think_result.get("activations", {}) if deep_think_result else {}
        )

        _inject_activations(subgraph_data.get("nodes", []), activations)

        hypotheses_list = _generate_hypotheses(subgraph_data, query.text, activations)
        hypotheses = [h.model_dump() for h in hypotheses_list]

        yield _sse(
            {"type": "status", "message": "Generating hypotheses...", "progress": 0.9}
        )

        # Final complete event with all data
        final_data = {
            "type": "complete",
            "progress": 1.0,
            "data": {
                "hypotheses": hypotheses,
                "graph_context": subgraph_data,
                "papers": papers if isinstance(papers, list) else [],
                "atlas": atlas_data if isinstance(atlas_data, dict) else {"cells": []},
                "extraction": req_graph.get_last_extraction(),
            },
        }
        yield _sse(final_data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/evolve", dependencies=[Depends(verify_api_key)])
async def evolve_hypothesis(query: Query, max_iterations: int = 3):
    """
    Full ADRS Discovery Loop: Generate -> Evaluate -> Refine.
    Incorporates MAST monitoring at each step.
    """
    history = await orchestrator.run_evolution_loop(query.text, max_iterations)
    
    # Format for response
    evolution_history = []
    for hypothesis, scorecard in history:
        evolution_history.append({
            "hypothesis": hypothesis.model_dump(),
            "scorecard": scorecard.model_dump()
        })
        
    return {
        "query": query.text,
        "iterations": len(history),
        "final_status": history[-1][1].overall_status,
        "history": evolution_history
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}
