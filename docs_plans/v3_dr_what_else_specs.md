# Onco-TTT v3: The "Deep Research" Expansion Specs

## 1. Executive Summary
**Current State (v0-v2):** Identifies *what* to target (Gene X in Cancer Y) and verifies *validity* (Expression, Literature).
**The Gap:** A researcher with a valid hypothesis still faces the "Valley of Death" before starting experiments:
1.  **Structure:** "Is there actually a binding pocket?" (Structural Biology)
2.  **IP:** "Did Pfizer patent this 5 years ago?" (Intellectual Property)
3.  **Models:** "Which cell line represents this specific patient subset?" (Model Selection)
4.  **Execution:** "What is the exact Western Blot protocol?" (Experimental Design)

**v3 Goal:** Transform Onco-TTT from a "Hypothesis Generator" into a **"Pre-Clinical AI Co-Pilot"** that delivers a complete "Go/No-Go" package.

---

## 2. New Module Specifications

### Module A: The "Virtual Structural Biologist" (VSB)
*   **User Question:** "Is this target actually druggable, or is it a smooth sphere?"
*   **Data Sources:**
    *   **AlphaFold Database (EBI):** Fetch predicted 3D structures.
    *   **P2Rank (Backend Tool):** ML-based ligand binding site prediction.
*   **Workflow:**
    1.  **Fetch:** Agent retrieves `AF-P12345-F1-model_v4.pdb` for the target gene.
    2.  **Analyze:** Runs `p2rank` on the structure to identify concave pockets with high "druggability" scores.
    3.  **Visualize:** Frontend renders the protein using **Mol*** (or NGL Viewer).
    4.  **Overlay:** Highlights the top 3 pockets in Red/Blue/Green.
    5.  **Mutation Check:** If the hypothesis involves a mutation (e.g., *KRAS G12C*), the VSB highlights residue 12 to see if it sits *inside* a pocket or on the surface.
*   **UI Deliverable:** A "Structure Card" showing the protein rotatable in 3D with a "Druggability Probability" score (0-100%).

### Module B: The "Patent Hawk"
*   **User Question:** "Am I wasting my time on an idea that is already patented?"
*   **Data Source:** **USPTO Open Data API** & **Google Patents**.
*   **Workflow:**
    1.  **Query Construction:** `(Abstract: [Target Gene]) AND (Abstract: [Disease Indication]) AND (Date > 2020)`.
    2.  **Retrieval:** Fetches patent titles, assignees (Pharma companies), and claims.
    3.  **Analysis:**
        *   *Scooped Score:* High count of recent patents = High risk of being scooped.
        *   *White Space:* No patents found = "First-in-Class" opportunity.
*   **UI Deliverable:** A "Freedom to Operate" Heatmap.
    *   *X-Axis:* Years.
    *   *Y-Axis:* Competitors (e.g., Roche, Novartis, Broad Institute).
    *   *Cell Color:* Intensity of patent filing activity.

### Module C: The "Model Matchmaker"
*   **User Question:** "I can't test this on patients. Which cell line is the perfect avatar?"
*   **Data Sources:**
    *   **Cellosaurus API:** Metadata (Age, Sex, Tissue, Disease Subtype).
    *   **DepMap/CCLE:** Genomic features (Mutations, Copy Number).
*   **Workflow:**
    1.  **Input:** User hypothesis defines the context (e.g., "Lung Adeno, KRAS-mutant, Male").
    2.  **Filter 1 (Cellosaurus):** Find all `Lung Adenocarcinoma` lines from `Male` donors.
    3.  **Filter 2 (DepMap):** Filter for lines with `KRAS` mutations (G12C/G12D).
    4.  **Rank:** Rank by "Dataset Richness" (lines that have CRISPR + RNA + Proteomics data are better).
    5.  **Exclude:** Flag "Problematic" lines (e.g., HeLa contamination) using Cellosaurus warnings.
*   **UI Deliverable:** "Recommended Models" Table.
    *   *Top Pick:* **A549** (Match: 95%).
    *   *Avoid:* **H1299** (Reason: p53 null, might skew results).

### Module D: The "Protocol Droid"
*   **User Question:** "How do I prove this? Write the method for me."
*   **Data Source:** Internal LLM + Knowledge Base of Standard Protocols (OpenWetWare styles).
*   **Workflow:**
    1.  **Contextual Generation:**
        *   *Task:* "Validate Gene X knockdown induces apoptosis."
        *   *Method:* CRISPR-Cas9 or siRNA.
    2.  **Drafting:** Generates a step-by-step protocol tailored to the *specific cell line* (from Module C) and *target gene*.
        *   *Customization:* "Use gRNA sequence: [predicted sequence] targeting Exon 2."
        *   *Timeline:* "Day 0: Seed cells... Day 3: Harvest."
*   **UI Deliverable:** A Markdown-formatted "Methods Section" ready for copy-paste into a lab notebook or grant application.

---

## 3. "Deep Research" Integrated User Journey

1.  **Hypothesis:** User types "Targeting YAP1 in Mesothelioma."
2.  **Onco-TTT Core (v1):** Confirms validity. "YAP1 is highly expressed and drives proliferation."
3.  **Deep Research Trigger (v3):** "Run Deep Feasibility Check."
4.  **The "Report" Generation (Spinning...):**
    *   *VSB:* "YAP1 TEAD binding domain is druggable (Score: 0.85). See Pocket A."
    *   *Patent Hawk:* "Warning: 12 patents filed by Novartis in 2024 targeting YAP1-TEAD."
    *   *Matchmaker:* "Best model: NCI-H2052 (Mesothelioma, BAP1 loss)."
    *   *Protocol:* "Suggested validation: Proximity Ligation Assay (PLA) for YAP1-TEAD interaction."
5.  **Decision:** User sees the patent wall and decides to pivot to a "PROTAC" strategy (degrader) instead of an inhibitor to evade the IP blockade.

## 4. Technical Stack Additions
*   **Backend:**
    *   `biotite` or `BioPython` for PDB parsing.
    *   `p2rank` (Java) binary wrapper or Docker container.
    *   `requests` for USPTO and Cellosaurus APIs.
*   **Frontend:**
    *   `molstar` (Mol*) React component for 3D protein rendering.
    *   `recharts` for the Patent Heatmap.

## 5. Success Metrics (HypoBench Expansion)
*   **Feasibility Score:** Does the AI accurately predict if a target has a binding pocket? (Benchmark against known "undruggable" targets like classic KRAS or MYC).
*   **IP Awareness:** Does it flag major blockbuster drugs as "Patented"?
