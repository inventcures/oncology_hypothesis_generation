# Onco-TTT (Oncology Test-Time Training Engine)

An AI-driven hypothesis generation platform that uses Test-Time Training (TTT) to adapt to specific oncology research queries in real-time.

## Architecture

- **Frontend:** Next.js 14, React, Tailwind CSS.
- **Backend:** FastAPI, NetworkX (Knowledge Graph), PyTorch (TTT Logic).
- **Core Modules:**
    - **ARK (Adaptive Retrieval of Knowledge):** Traverses the knowledge graph.
    - **TTT (Test-Time Training):** Adapts the agent's attention to the user's specific query context.
    - **MEDEA (The Verifier):** Verifies hypotheses against constraints (simulated).
    - **METIS (The Mentor):** UI layer for guidance.

## Getting Started

### 1. Start the Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will run at `http://127.0.0.1:8000`.

### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will run at `http://localhost:3000`.

## Features Implemented (Prototype)

- **Interactive Canvas:** Visualizes the relevant subgraph (Genes, Drugs, Diseases) dynamically based on the query.
- **TTT Simulation:** Simulates the "adaptation" phase where the model learns from the test instance.
- **Hypothesis Feed:** Displays generated hypotheses with Confidence and Novelty scores.
- **Mock Knowledge Graph:** Contains basic ontology for KRAS, STK11, and Lung Cancer contexts.

## Deployment

Auto-deploy is configured via Railway + GitHub Integration.
- Pushes to `main` trigger builds for `/backend` and `/frontend` independently.
