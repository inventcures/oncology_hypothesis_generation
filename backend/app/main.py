from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time

from .ark import OncoGraph
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

app = FastAPI(
    title="Onco-TTT API", description="Backend for Oncology Test-Time Training Engine"
)

# Enable CORS for frontend
origins = [
    "http://localhost:3000",
    "https://onco-ttt-frontend.up.railway.app",
    "https://onco-hypothesis.up.railway.app",
    "https://onco-hypothesis-generation.up.railway.app",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global State ---
graph = OncoGraph()
ttt_engine = TTTAdapter()
lit_agent = LiteratureAgent()
atlas_agent = AtlasAgent()
structure_agent = StructureAgent()
patent_agent = PatentAgent()
model_agent = ModelAgent()
protocol_agent = ProtocolAgent()
validation_agent = ValidationAgent()

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
    text: str
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
    text: str
    include_relations: bool = True
    include_clinical: bool = False
    threshold: float = 0.4


class KGBuildRequest(BaseModel):
    text: str
    enrich_opentargets: bool = True
    width: float = 800
    height: float = 600


# --- Routes ---


@app.get("/")
def read_root():
    return {"message": "Onco-TTT API is running", "status": "active"}


@app.post("/generate", response_model=GenerationResponse)
async def generate_hypotheses(query: Query):
    """
    Executes the ARK + TTT + MEDEA pipeline.

    Now powered by GLiNER2 for entity extraction and rich KG creation
    with color-coded nodes, weighted edges, and relation labels.
    """
    # 1. ARK Phase: GLiNER2 extraction + OpenTargets enrichment -> rich KG
    await graph.build_from_query(query.text)

    # 2. TTT Phase: Adapt to the query context within the fetched graph
    relevant_nodes = ttt_engine.adapt(graph.graph, query.text)

    # 3. Get Rich Graph Data with Layout, colors, edge labels
    subgraph_data = graph.get_subgraph_data()

    # 4. Literature Search Phase
    papers = await lit_agent.search_papers(query.text, limit=6)

    # 5. Atlas Projection Phase
    tissue_type = "lung"  # Default
    if "melanoma" in query.text.lower():
        tissue_type = "skin"
    if "pancrea" in query.text.lower():
        tissue_type = "pancreas"
    if "colorectal" in query.text.lower():
        tissue_type = "colon"

    atlas_data = atlas_agent.fetch_tumor_atlas(tissue_type, limit=300)

    # 6. Hypothesis Generation (Mocked based on graph content)
    hypotheses = []
    node_ids = [n["id"] for n in subgraph_data.get("nodes", [])]

    if any("KRAS" in nid for nid in node_ids):
        hypotheses.append(
            Hypothesis(
                id="h1",
                title="KRAS-Related Resistance",
                description="TTT identified potential resistance mechanisms linked to KRAS downstream effectors.",
                confidence=0.89,
                verified=True,
                novelty_score=0.75,
            )
        )

    if any("STK11" in nid for nid in node_ids):
        hypotheses.append(
            Hypothesis(
                id="h2",
                title="STK11 & Immune Exclusion",
                description="STK11 loss promotes cold tumor microenvironment via WNT signaling.",
                confidence=0.92,
                verified=True,
                novelty_score=0.82,
            )
        )

    if not hypotheses:
        top_node = node_ids[0] if node_ids else "Unknown"
        hypotheses.append(
            Hypothesis(
                id="h_gen",
                title=f"Novel Association: {top_node}",
                description=f"Analysis of {top_node} suggests unexplored links to phenotypic outcomes.",
                confidence=0.6,
                verified=False,
                novelty_score=0.9,
            )
        )

    return GenerationResponse(
        hypotheses=hypotheses,
        graph_context=subgraph_data,
        papers=papers,
        atlas=atlas_data,
        extraction=graph.get_last_extraction(),
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
                ot_client = graph.ot_client
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
