from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time

from .ark import OncoGraph
from .ttt import TTTAdapter

app = FastAPI(
    title="Onco-TTT API", description="Backend for Oncology Test-Time Training Engine"
)

# Enable CORS for frontend
origins = [
    "http://localhost:3000",
    "https://onco-ttt-frontend.up.railway.app",  # Potential railway domain
    "*",  # Allow all for prototype simplicity
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


class GenerationResponse(BaseModel):
    hypotheses: List[Hypothesis]
    graph_context: GraphData


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

    # 4. Hypothesis Generation (Mocked based on graph content)
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

    return GenerationResponse(hypotheses=hypotheses, graph_context=subgraph_data)


@app.get("/health")
def health_check():
    return {"status": "ok"}
