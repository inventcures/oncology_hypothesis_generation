# v1 Enhanced: Knowledge Graph & Single-Cell Integration Specifications

## 1. Executive Summary
This phase transforms Onco-TTT from a hypothesis generator into a **Multi-Modal Oncology Workbench**. We will integrate **Single-Cell Transcriptomics (scRNA-seq)** to validate hypotheses at the cellular level and expand the Knowledge Graph (KG) with **Pathway** and **Cell Type** ontologies.

## 2. Data Source Integration

### A. Single-Cell Data (The "Cell Atlas")
*   **Source:** **CZ CELLxGENE (Chan Zuckerberg Cell by Gene)**.
    *   *Why?* It is the largest standardized open-source repository of single-cell data with a robust API (`cellxgene-census`).
*   **Data to Fetch:**
    *   **Embeddings:** Pre-calculated UMAP/t-SNE coordinates for tumor tissues.
    *   **Metadata:** Cell Type annotations (e.g., "CD8+ T-Cell", "Malignant Epithelial").
    *   **Expression:** Gene expression levels for targets identified by ARK (e.g., "Is KRAS actually expressed in these tumor cells?").

### B. Comprehensive Knowledge Graph
*   **Current:** OpenTargets (Target-Disease).
*   **New Layers:**
    *   **Pathway Commons / Reactome:** To add `Pathway` nodes.
        *   *Logic:* KRAS -> activates -> MAPK Pathway.
    *   **Cell Ontology (CL):** To add `Cell Type` nodes.
        *   *Logic:* PD-1 -> expressed_in -> T-Cell.

## 3. Architecture Updates

### Backend (`/backend`)
1.  **New Module: `atlas.py`**
    *   Implements `SingleCellAgent`.
    *   Connects to CELLxGENE API.
    *   **Caching Strategy:** Since single-cell datasets are huge (GBs), we will fetch lightweight "slice" summaries (subsampled to ~500-1000 cells) for the frontend prototype.
2.  **Graph Schema Expansion (`ark.py`)**
    *   Add Node Types: `Pathway`, `CellType`.
    *   Add Edge Types: `part_of_pathway`, `enriched_in_celltype`.

### Frontend (`/frontend`)
1.  **New Tab: "Cell Atlas"**
    *   **Visualization:** Interactive Scatter Plot (UMAP).
    *   **Interaction:**
        *   *Color by:* Cell Type (default) vs. Gene Expression (heatmap).
        *   *Cross-Filtering:* Clicking a "Gene" node in the Graph View highlights expressing cells in the Atlas View.

## 4. Implementation Steps

### Phase 1: The Atlas Agent
1.  Install `cellxgene-census` (or use their REST API if lighter).
2.  Implement `fetch_tumor_atlas(cancer_type)`: Returns UMAP coords + annotations.
3.  Expose `/atlas/projection` endpoint.

### Phase 2: KG Expansion
1.  Update `OncoGraph` to include `Pathway` nodes (mocked or fetched via a lightweight pathway API like `gseapy` or Reactome).
2.  Link Genes to Pathways in the visualizer.

### Phase 3: Frontend Integration
1.  Add `AtlasView` component (using Recharts or primitive SVG scatter).
2.  Implement the "Bridge": When a Hypothesis mentions "Immune Exclusion", automatically load the "Melanoma" single-cell atlas to show the lack of T-Cells.

## 5. Visual Outcome (Goal)
The user asks: *"Role of YAP1 in immunotherapy?"*
1.  **Graph:** Shows `YAP1` connected to `Drug Resistance` and `Hippo Pathway`.
2.  **Atlas:** Loads a Lung Cancer UMAP.
3.  **Insight:** User clicks `YAP1`. The Atlas lights up, showing `YAP1` is high *only* in the "Fibroblast" cluster, suggesting a stromal mechanism of resistance rather than tumor-intrinsic.
