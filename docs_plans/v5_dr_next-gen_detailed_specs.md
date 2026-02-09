# V5: Next-Gen Platform — Making Onco-TTT Indispensable for Cancer Researchers & Drug Discovery Teams

## Deep Research Summary

After auditing every backend module (14 files, ~6,200 LOC), every frontend component (6 files, ~3,350 LOC), every spec (v0-v4, v7), the scientific preprint, and the full external API surface (14 data sources) — this document identifies what would make Onco-TTT genuinely useful to:

1. **Academic researchers** — PI's, postdocs, grad students doing hypothesis-driven cancer biology
2. **Translational scientists** — Bridging bench-to-bedside at academic medical centers
3. **Biotech/pharma drug discovery** — Target ID, target validation, competitive intelligence teams
4. **Clinical development** — Portfolio strategy, indication selection, biomarker strategy

The recommendations are ordered by **impact-to-effort ratio** — highest-leverage changes first.

---

## Part A: Critical Fixes (Ship-Blocking Gaps)

These aren't features — they're things that would cause a researcher to distrust the platform and never return.

### A1. Make Validation Checks Use Real Data (Not Fallbacks)

**Problem:** Two of the six validation checks (`check_survival` via cBioPortal and `check_drugability` via OpenTargets) have API code written but **always return `None`**, silently falling through to hardcoded data. A pharmacologist would immediately spot that "KRAS has 3 drugs in Phase III" is the same answer regardless of what cancer type they query. Trust destroyed.

**Fix:**
- `check_drugability`: Implement the Ensembl ID lookup (gene symbol → ENSG) that's blocking the OpenTargets drugs GraphQL query. The query itself is already written.
- `check_survival`: The cBioPortal clinical data fetch works. Implement the actual Kaplan-Meier computation: sort by OS_MONTHS, compute step function, log-rank statistic. Use `scipy.stats` (already a dependency via `structure.py`). Replace the synthetic exponential decay curves.

**Who cares:** Everyone. Survival data is the first thing an oncologist checks. Drug landscape is the first thing a pharma BD team checks.

**Effort:** Medium (3-4 hours). The API calls are already written; it's the data processing that's missing.

### A2. Make TTT Actually Do Something

**Problem:** `ttt.py` runs activation propagation but the result is **discarded** — `main.py:383` calls `adapt()` and ignores the return value. The TTT name is in the project title, the preprint, and the homepage. If anyone reads the code, this is a credibility problem.

**Two options:**
1. **Honest option:** Rename to "Activation Propagation" or "Query-Adapted Graph Ranking." Remove "Test-Time Training" from marketing. Use the activation scores to rank/weight nodes in the graph and influence hypothesis generation (they currently don't).
2. **Ambitious option:** Implement actual query-time gradient updates using a small MLP over node embeddings. Even a 2-layer network with 10 gradient steps would be legitimate TTT. Use PyTorch (already in requirements).

**Recommendation:** Option 1 now (30 min), Option 2 as v6. But at minimum, **use the activation scores** — feed them into `_generate_hypotheses` to weight which genes/drugs get featured.

**Who cares:** Anyone who reads the preprint or the About page. Peer reviewers. Competitors.

### A3. Surface Errors to Users

**Problem:** Validation, Clinical Trials, and Deep Research all swallow errors with `console.error`. If ClinicalTrials.gov is down, the user sees an infinite spinner or empty state with no explanation. No component has an error UI.

**Fix:** Add error state to all dashboard components. Pattern: `{ data, loading, error }` triple in parent state. Render a clear error card with retry button.

**Effort:** Low (1-2 hours).

---

## Part B: High-Impact Features for Academic Researchers

### B1. Hypothesis Lineage — "Why Do You Think This?"

**Problem:** The platform generates hypotheses like *"KRAS G12C mutation may confer resistance to immunotherapy through STK11 co-mutation"* but doesn't show **why**. Researchers need to see the evidence chain: which graph edges, which papers, which validation checks contributed to this claim.

**Feature:**
- Each hypothesis gets a collapsible "Evidence Trail" section
- Shows: (1) the specific graph path (nodes + edges) that generated it, (2) the papers whose abstracts mention the key entities, (3) the validation check scores relevant to the claim
- Clicking any evidence item navigates to the corresponding tab/view
- Visual: a mini directed graph showing just the subgraph that produced this hypothesis

**Who cares:** PIs writing grants (need to cite evidence). Reviewers evaluating the platform. Anyone deciding whether to spend $50K on a wet-lab experiment based on this output.

**Effort:** Medium. Backend: return `evidence_path` from `_generate_hypotheses`. Frontend: new `EvidenceTrail` component in hypothesis cards.

### B2. Multi-Gene / Pathway-Level Queries

**Problem:** The platform picks a single "seed gene" (`_pick_seed_gene`) and builds the graph around it. Real research questions are multi-gene: *"How do KRAS, STK11, and KEAP1 co-mutations affect immunotherapy response?"* The current system would pick KRAS and ignore the other two.

**Feature:**
- Extract ALL genes from the query (already done by GLiNER2)
- Build subgraphs for each gene, then merge with shared nodes highlighted
- New "intersection analysis": which diseases, drugs, pathways are shared across the queried genes?
- Show Venn-like overlap statistics

**Who cares:** Translational researchers studying co-mutation patterns. Combinatorial drug discovery teams. Anyone studying synthetic lethality.

**Effort:** Medium-High. Backend: loop `build_from_query` over multiple seeds, merge KGs. Frontend: multi-color node borders for shared entities.

### B3. Save, Compare, and Share Analyses

**Problem:** No persistence. If a researcher runs a query, closes the tab, and comes back — everything is gone. No way to compare two hypotheses side-by-side. No way to share results with a collaborator.

**Feature (phased):**
- **Phase 1 — URL State:** Encode query + viewMode in URL params. Shareable links. Browser back/forward works. (`/app?q=KRAS+lung+cancer&view=trials`)
- **Phase 2 — Local History:** `localStorage`-backed query history with timestamps. Sidebar shows recent queries. Click to re-run.
- **Phase 3 — Export Package:** "Download Analysis" button that exports a self-contained HTML report (graph SVG + hypothesis cards + validation summary + trials summary + papers list). Researcher can email this to a PI or attach to a grant.

**Who cares:** Everyone. This is table-stakes for any research tool.

**Effort:** Phase 1: Low (2 hours). Phase 2: Low (3 hours). Phase 3: Medium (6 hours).

### B4. Literature Deep-Dive — Citation Network

**Problem:** The Papers tab shows a flat list of 10 papers. Researchers need to understand the **citation landscape**: which papers are foundational (highly cited), which are recent (cite many others), and what the intellectual lineage is.

**Feature:**
- Use the existing `LiteratureAgent.get_citations()` and `get_references()` methods (implemented but **never exposed via any route**)
- Build a citation network graph: nodes = papers, edges = citations
- Overlay on the main graph or a separate "Citation Graph" sub-tab under Papers
- Highlight review papers (high in-degree), seminal papers (old + high citations), and cutting-edge work (recent + cites many)
- "Key Papers" algorithm: papers that are cited by many AND cite the query entities

**Who cares:** Grad students doing lit reviews. PIs assessing novelty of their hypothesis. Reviewers checking if the user missed important prior work.

**Effort:** Medium. Backend: new endpoint exposing citation graph. Frontend: reuse graph rendering with paper-node styling.

---

## Part C: High-Impact Features for Pharma/Biotech Drug Discovery

### C1. Target Dossier — One-Click Comprehensive Report

**Problem:** A drug discovery team evaluating a target (e.g., KRAS G12C in NSCLC) currently needs to click through 7 tabs and manually assemble the picture. They want a single, exportable report.

**Feature:**
- "Generate Target Dossier" button in the toolbar
- Automatically runs ALL analyses in parallel: KG build, literature search, all 6 validation checks, all 4 deep research modules, clinical trials search
- Assembles into a structured report with executive summary:
  - **Target Profile:** Gene function, known biology, expression pattern
  - **Genetic Evidence:** Essentiality (DepMap), survival impact (TCGA), mutation frequency
  - **Druggability Assessment:** Structural analysis, pocket druggability, known drugs, competitor compounds
  - **Safety Profile:** Normal tissue expression (GTEx), toxicity flags
  - **Competitive Landscape:** Active clinical trials (phase distribution, key sponsors), patent landscape, scooped score
  - **Experimental Path:** Recommended cell lines, suggested protocols, key reagents
  - **Literature Context:** Top papers, citation network, knowledge gaps
- **Go/No-Go Score:** Weighted composite of all checks (configurable weights)
- **Export:** PDF (via html2pdf or server-side), PowerPoint (key slides), JSON (for pipeline integration)

**Who cares:** Target validation teams at biotechs (this is literally their job, done manually today). VCs doing diligence on biotech pitches. BD teams evaluating in-licensing opportunities.

**Effort:** High (2-3 days). Mostly frontend orchestration + report template. Backend endpoints already exist.

### C2. Competitive Intelligence Dashboard

**Problem:** The current Clinical Trials tab and Patent Hawk are separate. A competitive intelligence analyst needs them unified with trend analysis.

**Feature:**
- Merge trials + patents into a single "Competitive Landscape" view
- **Timeline view:** Horizontal timeline showing patent filings (bottom) and trial starts (top) on the same axis
- **Competitor profiles:** For each company active in the space, show: # patents, # trials, phases, indications, modalities
- **White space analysis:** Which combinations of target + indication + modality have NO trials or patents? (The "first-in-class opportunity" detection from v2 spec, actually implemented)
- **Trend alerts:** Is activity accelerating or declining? Compare last 2 years vs prior 3 years (already computed in `_calculate_scooped_score` but never surfaced visually)
- **MOA breakdown:** Group trials by mechanism of action (inhibitor, degrader, antibody, ADC, cell therapy, etc.)

**Who cares:** BD teams, portfolio strategy, competitive intelligence analysts at mid/large pharma. Biotech founders positioning their programs.

**Effort:** Medium-High. New frontend component. Backend: merge clinical_trials + legal responses, add MOA classification.

### C3. Indication Expansion Explorer

**Problem:** A pharma team has a validated target (e.g., they have a KRAS G12C inhibitor). They want to know: *what other cancers should we test this in?* Current platform only answers one gene+disease at a time.

**Feature:**
- Input: a gene/target (or drug name)
- Output: ranked list of indications (cancer types) with evidence scores
- For each indication: mutation frequency (TCGA/COSMIC), essentiality (DepMap by lineage), existing clinical activity, competitive density
- **Heatmap:** Genes (rows) x Cancer Types (columns), colored by composite opportunity score
- Sources: OpenTargets associations (already fetched, limited to 10 — increase to 50), DepMap lineage-specific dependency

**Who cares:** Clinical development teams deciding which Phase II indications to pursue. Portfolio strategy. Biotech founders picking their lead indication.

**Effort:** Medium. Backend: new endpoint querying OpenTargets with larger page size + DepMap lineage data. Frontend: heatmap component.

### C4. Biomarker Strategy Module

**Problem:** `check_biomarker_context` is entirely hardcoded (5 entries). Real biomarker strategy requires: which patient subpopulation will respond? What's the prevalence? Is there a companion diagnostic?

**Feature:**
- **Co-mutation analysis:** For the target gene, what other mutations co-occur? (Query cBioPortal mutation data, compute co-occurrence statistics)
- **Expression-based stratification:** High vs low expression of the target — different survival? (Build on the survival check, but stratify by expression quartile)
- **Existing companion diagnostics:** Query FDA-approved CDx database (via OpenFDA or curated list)
- **Biomarker prevalence:** What % of patients in the target indication carry the relevant mutation/expression pattern?
- **Patient selection strategy:** LLM-synthesized recommendation for clinical trial eligibility criteria

**Who cares:** Translational medicine teams. Clinical development (designing trial inclusion criteria). Regulatory strategy (CDx requirements).

**Effort:** High (3-4 days). Requires new data sources (cBioPortal mutations API, OpenFDA).

---

## Part D: Platform Quality & Architecture

### D1. Break Up the God Component

**Problem:** `page.tsx` is 1,888 lines with 22 state variables. It's the entire application in one function. This makes every change risky, every review painful, and every new contributor lost.

**Refactor:**
```
page.tsx (shell: layout, routing, shared state)
├── components/HeroView.tsx (landing page)
├── components/ResultsSidebar.tsx (query input, hypotheses)
├── components/GraphView.tsx (SVG knowledge graph)
├── components/TableView.tsx (entity table)
├── components/MetricsView.tsx (confidence/novelty bars)
├── components/PapersView.tsx (literature cards)
├── components/ValidationDashboard.tsx (existing)
├── components/FeasibilityView.tsx (deep research)
├── components/ClinicalTrialsDashboard.tsx (existing)
└── hooks/useAnalysis.ts (shared state + API logic)
```

**Who cares:** Anyone maintaining or extending this codebase. Every future feature is harder without this.

**Effort:** Medium (4-5 hours). No new features, pure refactor.

### D2. Proper Type Safety

**Problem:** `validationData: any`, `trialsData: any`, chart sub-components accept `{ data: any }`. Duplicate type definitions between components (`PocketData` vs `Pocket`).

**Fix:**
- Create `types/` directory with shared type definitions
- Import everywhere. No `any` in component props.
- Re-export from a barrel file

**Effort:** Low (2 hours).

### D3. Real Graph Interaction

**Problem:** The knowledge graph is a static SVG with pre-computed coordinates. No zoom, no pan, no drag. For graphs with 30+ nodes, it's unreadable.

**Fix:**
- Replace static SVG with a lightweight force-directed library (e.g., `d3-force` with React, or `@react-sigma/core` for large graphs)
- Add: zoom/pan (scroll + drag), node drag, click-to-expand (fetch 1-hop neighbors on demand), minimap for large graphs
- Keep the current SVG as a "static export" option

**Who cares:** Anyone exploring a complex knowledge graph. The current static layout works for 10-15 nodes but breaks visually at 30+.

**Effort:** Medium-High (1-2 days). Significant frontend work.

### D4. Streaming / Progressive Loading

**Problem:** The main `/generate` endpoint takes 3-8 seconds. During this time, the user sees fake status messages on timers (`setTimeout` at 800ms, 1800ms, 2800ms) that have no connection to actual progress.

**Fix:**
- Backend: Use Server-Sent Events (SSE) to stream progress. As each concurrent task completes (KG built, papers found, atlas loaded), send an event.
- Frontend: Replace the fake status messages with real ones. Progressively render results as they arrive (show graph immediately when KG is done, don't wait for papers).

**Who cares:** Everyone. Perceived performance is real performance.

**Effort:** Medium (4-6 hours). FastAPI supports SSE via `StreamingResponse`.

---

## Part E: Data Source Expansions

### E1. COSMIC (Catalogue Of Somatic Mutations In Cancer)

**What:** Mutation frequency data across cancer types. "KRAS G12C occurs in 13% of NSCLC."
**Why:** Critical for indication selection, patient prevalence estimation, biomarker strategy.
**API:** COSMIC API (requires academic license) or ICGC Data Portal (open).
**Effort:** Low-Medium.

### E2. DepMap (Broad Institute) — Direct API

**What:** The current implementation uses Cell Model Passports (Sanger) as a proxy for DepMap data. The actual Broad DepMap portal has richer data: gene effect scores across 1,000+ cell lines, PRISM drug sensitivity.
**Why:** More comprehensive essentiality data. PRISM drug sensitivity enables compound-target correlation.
**API:** DepMap Portal REST API or bulk download.
**Effort:** Medium.

### E3. ChEMBL Bioactivity Data

**What:** IC50/EC50/Ki values for compounds against specific targets. Currently only using OpenTargets drug data (approved + clinical).
**Why:** Drug discovery teams need to see the full SAR (structure-activity relationship) landscape, not just approved drugs.
**API:** ChEMBL REST API (open, well-documented).
**Effort:** Medium.

### E4. TCGA / GDC (Genomic Data Commons)

**What:** Multi-omic cancer patient data. Currently only accessed via cBioPortal (and that doesn't work). Direct GDC API access would give: mutation profiles, copy number, gene expression, methylation.
**Why:** Foundation for survival analysis, expression stratification, co-mutation analysis.
**API:** GDC REST API (open, token for controlled access).
**Effort:** Medium-High.

### E5. DrugBank / OpenFDA

**What:** FDA-approved drugs with detailed MOA, pharmacokinetics, drug-drug interactions, adverse events.
**Why:** Safety profiling for drug repurposing hypotheses. "This drug is approved for X, could it work for Y?"
**API:** DrugBank (academic license) or OpenFDA (open).
**Effort:** Low-Medium.

---

## Part F: Moonshot Features (High Effort, High Differentiation)

### F1. "What If" Simulator

**What:** Interactive perturbation analysis. User selects a node in the graph and asks "What if we inhibit this?" The system propagates the effect through the graph, showing downstream consequences.
**Why:** This is how drug discovery scientists think. "If I inhibit KRAS, what happens to MAPK pathway? Does it activate a bypass through PI3K?"
**Implementation:** Use the graph topology + edge weights to simulate signal propagation. Not a full ODE model — a qualitative network perturbation analysis.
**Effort:** High (1 week).

### F2. Longitudinal Monitoring

**What:** Save a query and get notified when new evidence appears: new paper published, new clinical trial registered, new drug approval, patent filed.
**Why:** Research is longitudinal. A hypothesis validated today might be invalidated next month by a new publication.
**Implementation:** Cron job (daily/weekly) re-runs saved queries against ClinicalTrials.gov + Semantic Scholar. Diff against previous results. Email/webhook notification.
**Effort:** High (requires persistent storage, job scheduler, notification system).

### F3. Multi-Modal Input

**What:** Upload a gene list (from RNA-seq), a VCF file (from sequencing), or a pathology image. The system extracts entities from the file and builds the analysis automatically.
**Why:** Researchers don't always start with a text question. They start with data.
**Implementation:** Gene list → batch KG build. VCF → extract mutations → per-mutation analysis. Image → future (pathology AI).
**Effort:** Gene list: Low-Medium. VCF: Medium. Image: Very High.

### F4. Collaborative Workspace

**What:** Multiple researchers can work on the same analysis. Shared annotations, comments on hypotheses, upvote/downvote evidence.
**Why:** Research is collaborative. A PI and their postdoc need to discuss hypotheses asynchronously.
**Implementation:** Requires user auth, persistent storage (PostgreSQL), WebSocket for real-time sync.
**Effort:** Very High (multi-week project).

---

## Implementation Priority Matrix

### Tier 1 — "Fix credibility issues" (Do this week)

| # | Feature | Effort | Impact | Who Benefits |
|---|---------|--------|--------|--------------|
| A1 | Real validation data (survival + drugs) | 3-4h | Critical | Everyone |
| A2 | Use TTT activation scores or rename | 30min-2h | Critical | Credibility |
| A3 | Surface errors to users | 1-2h | High | Everyone |
| B3-P1 | URL state (shareable links) | 2h | High | Everyone |
| D2 | Type safety cleanup | 2h | Medium | Maintainability |

### Tier 2 — "Make it useful" (Next 2 weeks)

| # | Feature | Effort | Impact | Who Benefits |
|---|---------|--------|--------|--------------|
| B1 | Hypothesis lineage / evidence trail | 6-8h | Very High | Academics |
| B3-P2 | Local query history | 3h | High | Everyone |
| B4 | Citation network | 6-8h | High | Academics |
| C1 | Target Dossier (one-click report) | 2-3d | Very High | Pharma/Biotech |
| D1 | Break up god component | 4-5h | High | Maintainability |
| D4 | Streaming / progressive loading | 4-6h | High | Everyone |

### Tier 3 — "Differentiate" (Next month)

| # | Feature | Effort | Impact | Who Benefits |
|---|---------|--------|--------|--------------|
| B2 | Multi-gene / pathway queries | 1-2d | Very High | Translational |
| C2 | Competitive intelligence dashboard | 1-2d | Very High | Pharma BD |
| C3 | Indication expansion explorer | 1d | Very High | Clinical dev |
| D3 | Interactive graph (zoom/pan/drag) | 1-2d | High | Everyone |
| B3-P3 | Export analysis package | 6h | High | Academics |
| E1 | COSMIC integration | 4-6h | High | Everyone |
| E3 | ChEMBL bioactivity data | 6-8h | High | Drug discovery |

### Tier 4 — "Win the market" (Next quarter)

| # | Feature | Effort | Impact | Who Benefits |
|---|---------|--------|--------|--------------|
| C4 | Biomarker strategy module | 3-4d | Very High | Translational/Clinical |
| E2 | Direct DepMap integration | 1-2d | High | Drug discovery |
| E4 | GDC/TCGA direct access | 2-3d | High | Academics |
| F1 | "What If" simulator | 1w | Transformative | Drug discovery |
| F2 | Longitudinal monitoring | 1w | High | Everyone |
| F3 | Multi-modal input (gene lists) | 3-4d | High | Academics |

---

## Competitive Positioning

### Current State
Onco-TTT is a **prototype demo** with impressive breadth (7 tabs, 14 data sources) but shallow depth (many features use fallback/curated data, no persistence, no real TTT). It's good for a conference poster. It's not yet something a researcher would bookmark.

### After Tier 1+2
A **credible research tool** that an academic would use for initial hypothesis exploration and a pharma scientist would use for quick target triage. The Target Dossier + real validation data + evidence trails make it genuinely useful. Comparable to a lightweight BioGPS or Open Targets but with hypothesis generation.

### After Tier 3+4
A **category-defining platform** bridging the gap between knowledge bases (Open Targets, DepMap) and experimental design. No existing tool does KG-based hypothesis generation + validation + competitive intelligence + experimental planning in a single interface. The closest competitors are:

- **Open Targets**: Richer data, no hypothesis generation, no experimental planning
- **BenchSci**: Literature AI, no KG, no validation suite
- **Innoplexus/Signals (CAS)**: Enterprise pharma tools, $100K+/year, no open-source alternative
- **Elicit/Consensus**: Literature Q&A, no biology-specific validation

Onco-TTT's unique position: **open-source, hypothesis-first, full-stack from question to protocol**.

---

## Technical Debt to Resolve Alongside Features

| Issue | Location | Risk | Fix |
|-------|----------|------|-----|
| `orchestrator.py` calls non-existent `analyze_structure` | `orchestrator.py:~L340` | Runtime error on structure tool use | Rename to `fetch_structure` |
| Sync Anthropic client in async context | `orchestrator.py` | Event loop blocking | Use `anthropic.AsyncAnthropic` |
| Per-request httpx clients (no reuse) | `models.py`, `protocols.py`, `legal.py` | Connection overhead, potential leaks | Use shared persistent client from lifespan |
| Atlas UMAP coordinates are random | `atlas.py:~L61` | Misleading visualization | Either compute real UMAP or remove the tab until real |
| Hardcoded pathway enrichment (15 genes only) | `kg_builder.py` | No pathway data for non-curated genes | Use Reactome REST API |
| Node ID case sensitivity | `kg_builder.py` | Duplicate nodes for same entity | Normalize IDs to uppercase |
| MolstarViewer stale highlights | `MolstarViewer.tsx` | Pocket/mutation changes don't re-render | Add pockets + mutationAnalysis to useEffect deps |
| Empty catch block | `MolstarViewer.tsx:L208` | Silent failures | Log or surface error |
| Dead dark mode CSS | `globals.css` | Confusion | Remove or implement properly |

---

## Summary

The platform has remarkable **breadth** — 14 external data sources, 7 views, entity extraction, graph building, literature search, structural analysis, patent search, cell line recommendation, protocol generation, validation, clinical trials. Very few open-source tools cover this much ground.

The gap is **depth and trust**. Two validation checks silently use fake data. TTT doesn't actually train. Errors are invisible. Nothing is persistent. The graph is static.

**The single highest-leverage change is making the existing features work with real data.** Not adding new features — making the current ones trustworthy. A researcher who sees one fake number will never trust any of the real ones.

After that, the Target Dossier (C1) and Evidence Trail (B1) are the features that would make someone say: *"I can't do my job without this."*
