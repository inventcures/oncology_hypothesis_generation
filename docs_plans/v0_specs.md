# Product Spec: Onco-TTT (Oncology Test-Time Training Engine)

## 1. Executive Summary
**Onco-TTT** is an AI-driven hypothesis generation platform for oncology researchers. Unlike static RAG systems, Onco-TTT employs **Test-Time Training (TTT)** to adapt its neural retrieval and reasoning models to the specific biological context of a user's query *in real-time*. This "learning to discover" approach is constrained by **MEDEA's** rigorous verification protocols and guided by **METIS's** pedagogical interaction model, ensuring hypotheses are not only novel (HypoBench metric) but biologically plausible.

## 2. Core Architecture

The system is composed of four interacting agents/modules:

### A. The Adaptive Explorer (ARK + TTT)
*   **Base Logic:** Uses **ARK (Adaptive Retrieval of Knowledge)** to traverse a heterogeneous Knowledge Graph (OpenTargets, PubMed, ClinicalTrials).
*   **Innovation (TTT):** Instead of a fixed traversal policy, the Explorer uses **Test-Time Training**.
    *   *Input:* "Mechanisms of resistance to KRAS G12C inhibitors in lung cancer."
    *   *Process:* The model performs temporary gradient updates on its attention mechanism during inference. It minimizes a "Surprise Loss" (seeking novel connections) while maximizing "Relevance Reward" (semantic similarity to the query context).
    *   *Outcome:* The model "overfits" to the specific query, becoming a temporary expert on KRAS G12C for that session.

### B. The Verifier (MEDEA)
*   **Role:** The "Critic" in the Actor-Critic loop.
*   **Modules:**
    *   *Context Check:* "Is this mechanism physically possible in Lung Tissue?" (e.g., checks expression levels).
    *   *Integrity Check:* "Does this contradict established dogma?" (If yes, flag as 'High Risk/High Reward' rather than 'False').
*   **Workflow:** Filters the Explorer's outputs before they reach the user.

### C. The Mentor (METIS)
*   **Role:** User Interface and Query Refinement.
*   **Logic:** Assesses the user's "stage" of research.
    *   *Early Stage:* Suggests broad reviews and high-level targets.
    *   *Late Stage:* Suggests specific experiments and biomarkers.
    *   *Routing:* Routes the user to specific external tools (e.g., "Use CRISPR-Cas9 design tool X for this target").

### D. The Evaluator (HypoBench)
*   **Role:** Self-Correction.
*   **Metrics:** Scores internal candidates on:
    *   *Novelty:* Distance from established edges in the KG.
    *   *Validity:* Citation support strength.
    *   *Explanatory Power:* Does it mechanistically explain the phenomenon?

## 3. Data Ingestion & Integration
*   **Primary Sources:**
    *   **OpenTargets Platform:** Gene-disease associations (GraphQL API).
    *   **PubMed/PMC:** Literature mining (for causal assertions).
    *   **ClinicalTrials.gov:** Current trial status (preventing redundant hypotheses).
    *   **Social Signal:** Twitter/X scientific discourse (for emerging, pre-print trends).

## 4. User Interface / UX Design
*   **Philosophy:** Minimalist, "Surprising Detail" (based on Web Resource #1), and Clean Viz (Saloni's Guide).
*   **Interface Layout:**
    *   **The Canvas:** An infinite whiteboard where hypotheses are nodes.
    *   **The Feed:** A chronological stream of "thoughts" from the Agent as it explores (e.g., "Found connection via Pathway X... Verifying... Rejected due to low expression").
*   **Visualizations (Saloni-Compliant):**
    *   *No 3D Pie Charts.*
    *   *Small Multiples:* To show gene expression across different cancer subtypes side-by-side.
    *   *Grey Backgrounds:* Soft grey backgrounds for plots to let colored data points pop.
    *   *Direct Labeling:* No legends; labels directly on the lines/bars.

## 5. Workflow Example
1.  **User Query:** "Why do some patients fail immunotherapy in Melanoma despite high TMB?"
2.  **TTT Phase:** System spins for 30s. "Adapting to Melanoma TMB landscape..." (Training on the test instance).
3.  **Exploration:** ARK traverses graph. Finds "STK11 mutations" and "WNT signaling".
4.  **Verification:** MEDEA checks: "Is WNT signaling active in these cell lines?" -> Yes.
5.  **Mentoring:** METIS Output: "I've generated 3 hypotheses. The strongest links STK11 loss to 'immune desert' phenotype via WNT. Would you like to see the supporting papers or design a validation experiment?"
