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


# --- Routes ---


@app.get("/")
def read_root():
    return {"message": "Onco-TTT API is running", "status": "active"}


@app.post("/generate", response_model=GenerationResponse)
async def generate_hypotheses(query: Query):
    """
    Executes the ARK + TTT + MEDEA pipeline.
    """
    # 1. ARK Phase: Fetch real data from OpenTargets
    # This replaces the static mock data with a dynamic subgraph based on the query
    await graph.build_from_query(query.text)

    # 2. TTT Phase: Adapt to the query context within the fetched graph
    # (Simulated delay for "Training" visualization is now the API latency)
    relevant_nodes = ttt_engine.adapt(graph.graph, query.text)

    # 3. Get Graph Data with Layout
    subgraph_data = graph.get_subgraph_data()

    # 4. Literature Search Phase
    # Fetch real papers relevant to the query to support the hypotheses
    papers = await lit_agent.search_papers(query.text, limit=6)

    # 5. Atlas Projection Phase
    # Infer tissue type from query (simple heuristic) and fetch single-cell data
    tissue_type = "lung"  # Default
    if "melanoma" in query.text.lower():
        tissue_type = "skin"
    if "pancrea" in query.text.lower():
        tissue_type = "pancreas"
    if "colorectal" in query.text.lower():
        tissue_type = "colon"

    # Non-blocking call (or fast fetch)
    atlas_data = atlas_agent.fetch_tumor_atlas(tissue_type, limit=300)

    # 6. Hypothesis Generation (Mocked based on graph content)
    # In a real system, an LLM would generate these based on subgraph_data

    hypotheses = []

    # Check what nodes are actually in the graph now

    node_ids = [n["id"] for n in subgraph_data["nodes"]]

    # Dynamic Mocking based on graph content
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
        # Generic hypothesis for whatever was found
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
    )


@app.get("/structure/{gene}")
async def get_structure_analysis(gene: str, mutation: Optional[str] = None):
    """
    Module A: Virtual Structural Biologist
    Fetches AlphaFold structure and predicts binding pockets.

    Args:
        gene: Gene symbol (e.g., "KRAS", "EGFR")
        mutation: Optional mutation string (e.g., "G12C", "V600E")
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

    Args:
        tissue: Target tissue type (e.g., "lung", "breast", "colon")
        mutation: Optional mutation filter (e.g., "KRAS G12C")
        exclude_problematic: Whether to deprioritize known problematic lines
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

    Args:
        method: Experiment type (crispr, western, drug_assay, rnai, qpcr, etc.)
        gene: Target gene symbol
        cell_line: Cell line to use
        target_sequence: Optional sequence for gRNA design
        use_llm: Whether to use LLM for protocol generation (requires API key)
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

    Includes:
    1. Essentiality (DepMap CRISPR)
    2. Survival Impact (TCGA)
    3. Safety Profile (GTEx)
    4. Tractability (Drug databases)
    5. Biomarker Context (Synthetic lethality)
    6. Competition (Clinical trials)
    7. Auto-Rationale Synthesis
    """
    return await validation_agent.validate_hypothesis(gene, disease, cancer_type)


@app.get("/health")
def health_check():
    return {"status": "ok"}
