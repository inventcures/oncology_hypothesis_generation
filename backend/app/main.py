from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

from .ark import OncoGraph, OpenTargetsClient
from .ttt import TTTAdapter
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

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app_instance):
    """Startup/shutdown lifecycle — properly close persistent HTTP clients."""
    yield
    # Shutdown: close all persistent httpx clients
    await ot_client.client.aclose()
    await lit_agent.client.aclose()


app = FastAPI(
    title="Onco-TTT API",
    description="Backend for Oncology Test-Time Training Engine",
    lifespan=lifespan,
)

# Enable CORS for frontend
origins = [
    "http://localhost:3000",
    "https://onco-ttt-frontend.up.railway.app",
    "https://onco-hypothesis.up.railway.app",
    "https://onco-hypothesis-generation.up.railway.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global State ---
# OncoGraph is NOT global — it is created per-request to avoid concurrent state corruption.
# Only the stateless OpenTargetsClient is shared (holds a persistent httpx connection pool).
ot_client = OpenTargetsClient()
ttt_engine = TTTAdapter()
lit_agent = LiteratureAgent()
atlas_agent = AtlasAgent()
structure_agent = StructureAgent()
patent_agent = PatentAgent()
model_agent = ModelAgent()
protocol_agent = ProtocolAgent()
validation_agent = ValidationAgent()
ct_client = ClinicalTrialsClient()

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


# --- Hypothesis Generation (dynamic, based on extracted entities & relations) ---


def _generate_hypotheses(subgraph_data: dict, query_text: str) -> List[Hypothesis]:
    """
    Generate hypotheses dynamically from the knowledge graph structure.

    Uses the actual extracted entities and their relationships to form
    testable biological hypotheses rather than pattern-matching on node IDs.
    """
    nodes = subgraph_data.get("nodes", [])
    links = subgraph_data.get("links", [])
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

    # Classify nodes
    genes = [n for n in nodes if n.get("type", "").lower() in ("gene", "target")]
    diseases = [n for n in nodes if n.get("type", "").lower() == "disease"]
    drugs = [n for n in nodes if n.get("type", "").lower() == "drug"]
    pathways = [n for n in nodes if n.get("type", "").lower() == "pathway"]
    mechanisms = [n for n in nodes if n.get("type", "").lower() == "mechanism"]
    mutations = [n for n in nodes if n.get("type", "").lower() == "mutation"]

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
            conf = min(0.95, 0.6 + weight * 0.3)
            hypotheses.append(
                Hypothesis(
                    id=f"h{h_idx}",
                    title=f"{gene_name} as Driver in {top_disease}",
                    description=f"Analysis identified {gene_name} as a key node connected to {top_disease} with {len(linked_diseases)} supporting associations in the knowledge graph.",
                    confidence=round(conf, 2),
                    verified=conf > 0.8,
                    novelty_score=round(max(0.3, 1.0 - conf), 2),
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
            hypotheses.append(
                Hypothesis(
                    id=f"h{h_idx}",
                    title=f"{drug_name} Targets {', '.join(targets[:2])}",
                    description=f"{drug_name} may modulate {', '.join(targets)} based on extracted relationship evidence from the query context.",
                    confidence=0.75,
                    verified=True,
                    novelty_score=0.6,
                )
            )

    # --- Strategy 3: Mutation-Resistance / Mechanism hypotheses ---
    for mut in mutations[:1]:
        mut_name = mut.get("label") or mut.get("id", "Unknown")
        related_mechs = [(m.get("label") or m.get("id")) for m in mechanisms]
        related_genes = [(g.get("label") or g.get("id")) for g in genes[:2]]
        context = related_mechs[:1] or related_genes[:1] or ["downstream effectors"]
        h_idx += 1
        hypotheses.append(
            Hypothesis(
                id=f"h{h_idx}",
                title=f"Mutation {mut_name} & Resistance",
                description=f"The {mut_name} mutation may drive resistance via {context[0]}, presenting a potential therapeutic vulnerability.",
                confidence=0.82,
                verified=False,
                novelty_score=0.78,
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
            hypotheses.append(
                Hypothesis(
                    id=f"h{h_idx}",
                    title=f"{pw_name} Pathway Involvement",
                    description=f"The {pw_name} pathway connects {', '.join(linked_genes_in_pw[:3])}, suggesting coordinated signaling that may be therapeutically targetable.",
                    confidence=0.7,
                    verified=False,
                    novelty_score=0.85,
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

    return hypotheses[:5]  # Cap at 5 hypotheses


# --- Routes ---


@app.get("/")
def read_root():
    return {"message": "Onco-TTT API is running", "status": "active"}


@app.post("/generate", response_model=GenerationResponse)
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

    # 2. TTT Phase: Propagate activations through graph (used for node ranking)
    ttt_engine.adapt(req_graph.graph, query.text)

    # 3. Get Rich Graph Data with Layout, colors, edge labels
    subgraph_data = req_graph.get_subgraph_data()

    # 4. Hypothesis Generation — dynamically from extracted entities & relations
    hypotheses = _generate_hypotheses(subgraph_data, query.text)

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
async def get_structure_analysis(gene: str, mutation: Optional[str] = None):
    """
    Module A: Virtual Structural Biologist
    Fetches AlphaFold structure and predicts binding pockets.
    """
    return await structure_agent.fetch_structure(gene, mutation)


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


@app.get("/health")
def health_check():
    return {"status": "ok"}
