# Onco-TTT v2: Product Specifications & Feature Roadmap

## 1. User Persona Analysis
**Target User:** Translational Cancer Researcher (Academic PI or Biotech Scientist)
**Goal:** Rapidly validate whether a generated hypothesis (Gene X -> Phenotype Y) is scientifically sound, clinically relevant, and novel before investing resources in wet-lab experiments.

**The "Sanity Check" Loop:**
Before starting a project, the researcher asks:
1.  **Essentiality:** "If I knock this gene out, do cancer cells actually die? Is it specific to cancer or does it kill everything?"
2.  **Clinical Relevance:** "Does high expression of this gene correlate with poor patient survival?"
3.  **Tractability:** "Are there existing drugs/compounds that target this? Is the structure solvable?"
4.  **Safety:** "Is this gene expressed in vital normal tissues (heart, brain)?"
5.  **Novelty/Competition:** "Is there already a Phase II trial for this target?"

---

## 2. Data Source Integration Strategy
To answer the questions above, Onco-TTT v2 will integrate the following public APIs and datasets:

| Domain | Primary Source | Usage |
| :--- | :--- | :--- |
| **CRISPR/Dependency** | **DepMap (Broad Institute)** | Gene essentiality scores (Chronos), cell line lineage contexts. |
| **Clinical/Genomic** | **cBioPortal / TCGA / GDC** | Patient survival data, co-mutation patterns, copy number alterations. |
| **Expression/Safety** | **GTEx & CCLE** | Normal tissue vs. Tumor tissue expression comparison. |
| **Drugability** | **OpenTargets / DrugBank / ChEMBL** | Existing inhibitors, antibodies, and tractability scores. |
| **Clinical Landscape** | **ClinicalTrials.gov (AACT)** | Ongoing trials, recruitment status, competitive analysis. |
| **Literature** | **PubMed / bioRxiv** | Automated novelty checks and citation graphing. |

---

## 3. v2 Feature Specifications

### Feature 1: The "Dependency Dashboard" (DepMap Integration)
*   **User Question:** "Is this target essential in my specific cancer type?"
*   **Data Source:** DepMap API (CRISPR/RNAi datasets).
*   **Implementation Concept:**
    *   **Visual:** A lineage-specific box plot showing gene dependency scores (Chronos scores).
    *   **Logic:** If the score is < -1.0 (strongly essential) in the user's cancer type but > -0.5 (non-essential) in others, flag as "Selectively Essential" (High Value).
    *   **UI Element:** "Kill-Switch Indicator" – Red/Green status badge indicating if the target is a fundamental survival gene.

### Feature 2: Automated Survival Kaplan-Meiers
*   **User Question:** "Do patients with high expression of this target die faster?"
*   **Data Source:** TCGA (via cBioPortal API).
*   **Implementation Concept:**
    *   **Visual:** Interactive Kaplan-Meier survival curves generated on-the-fly.
    *   **Logic:** Split patient cohorts by "High Expression" vs. "Low Expression" (top/bottom quartile). Calculate Log-rank p-value automatically.
    *   **UI Element:** "Prognostic Value" card showing Hazard Ratio (HR) and p-value.

### Feature 3: The "Toxicity Trap" Checker (GTEx vs. TCGA)
*   **User Question:** "Will targeting this kill the patient via off-target toxicity?"
*   **Data Source:** GTEx (Normal Tissue) + TCGA (Tumor Tissue).
*   **Implementation Concept:**
    *   **Visual:** "Waterfall Plot" comparing expression in the target tumor vs. vital organs (Heart, Liver, Brain).
    *   **Logic:** Calculate a Tumor-to-Normal (T/N) ratio.
    *   **UI Element:** Warning modal: "High expression detected in Cardiac Tissue. High toxicity risk."

### Feature 4: "Chemo-Connect" Drugability Scout
*   **User Question:** "Do I have to invent a new drug, or can I buy one?"
*   **Data Source:** OpenTargets / ChEMBL / DrugBank.
*   **Implementation Concept:**
    *   **Visual:** Knowledge graph node.
    *   **Logic:** Search for approved drugs, Phase I compounds, or chemical probes associated with the protein structure.
    *   **UI Element:** List view: "Approved Drugs" (Green), "Experimental Compounds" (Yellow), "Undrugged" (Red).

### Feature 5: Biomarker Contextualizer
*   **User Question:** "Does this target only work if KRAS or TP53 is mutated?"
*   **Data Source:** DepMap (Context) / cBioPortal.
*   **Implementation Concept:**
    *   **Visual:** Correlation scatter plot.
    *   **Logic:** Correlate target dependency scores with driver mutation status (e.g., Target X is only essential in KRAS-mutant lines).
    *   **UI Element:** "Synthetic Lethality" Alert: "Target X appears synthetic lethal with Gene Y mutations."

### Feature 6: The "Competition Radar"
*   **User Question:** "Am I scooped?"
*   **Data Source:** ClinicalTrials.gov API.
*   **Implementation Concept:**
    *   **Visual:** Timeline view.
    *   **Logic:** NLP extraction of trial interventions to match the target gene/pathway.
    *   **UI Element:** "Active Trials" counter. If 0, display "First-in-class opportunity."

### Feature 7: "Auto-Rationale" Synthesis
*   **User Question:** "How do I pitch this in a grant?"
*   **Data Source:** LLM Synthesis of Features 1-6.
*   **Implementation Concept:**
    *   **Visual:** Text Block / PDF Export.
    *   **Logic:** Synthesize the data points into a coherent paragraph: *"Gene X is a selectively essential target in Lung Adenocarcinoma (DepMap), associated with poor survival (TCGA, p<0.05). While currently undrugged, it shows low expression in vital tissues, making it a viable candidate for novel inhibitor development."*
    *   **UI Element:** "Export Hypothesis Package" button.
