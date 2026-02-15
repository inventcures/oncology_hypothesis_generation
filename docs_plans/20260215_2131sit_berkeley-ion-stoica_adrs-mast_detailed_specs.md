# Detailed Plan & Specs: Incorporating ADRS and MAST in Oncology Hypothesis Generation

## 1. Executive Summary
This document outlines the architectural and logic changes required to transition the current "one-shot" hypothesis generation system into an **AI-Driven Research for Systems (ADRS)** iterative pipeline, while ensuring robustness using the **Multi-Agent Systems Failure Taxonomy (MAST)**.

The goal is to treat oncology hypothesis generation as an evolutionary process where hypotheses are generated, rigorously evaluated against biomedical ground truth (DepMap, TCGA, GTEx), and iteratively refined to maximize "Translational Fitness."

## 2. ADRS Integration: Hypothesis Evolution Pipeline (HEP)

Following the ADRS framework (Cheng et al., 2025), we will restructure the discovery loop.

### 2.1 Core Components
- **Prompt Generator (Evolver)**: Replaces the current query-routing Orchestrator. It takes a seed hypothesis or research objective and generates a structured "Target-Disease-Mutation" hypothesis.
- **Solution Generator (Hypothesis Refiner)**: Uses the current `NeuroSymbolicLoop` but instead of just query refinement, it modifies the hypothesis attributes (e.g., "If KRAS G12C is too competitive, try NRAS Q61R in Colorectal").
- **Evaluator (Reliable Verifier)**: Upgraded `ValidationAgent`. It must provide a "Structured Feedback Scorecard" (Fidelity Level 1: Heuristics, Level 2: KG Evidence, Level 3: Quantitative Bio-data).
- **Storage (Hypothesis Bank)**: Stores all iterations, their validation scores, and the reason for refinement.
- **Solution Selector**: Picks the top-performing hypotheses from the bank to seed the next generation.

### 2.2 Cascading Evaluator Levels
| Fidelity Level | Tool/Source | Metric | Cost/Speed |
| :--- | :--- | :--- | :--- |
| **L1: Plausibility** | Semantic Scholar / KG | Citation count, path connectivity | Low / Fast |
| **L2: Technical Fit** | AlphaFold (ttt.py) | Druggable pocket availability | Medium / Med |
| **L3: Biological Fit** | DepMap / GTEx | Chronos Score, Toxicity Index | Medium / Med |
| **L4: Clinical Fit** | TCGA / ClinTrials | Hazard Ratio, Competitive density | High / Slow |

## 3. MAST Integration: Runtime Robustness & Self-Correction

To prevent common failures in Multi-Agent Systems (Cemri et al., 2025), we will implement a `MASTMonitor` layer.

### 3.1 Taxonomy Implementation
The system will monitor agent traces for the following failure modes:
- **FC1: System Design Issues**
    - **Disobey Role Spec (FM-1.2)**: Ensure the `LiteratureAgent` doesn't attempt to calculate Hazard Ratios (tasks delegated to `ValidationAgent`).
    - **Step Repetition (FM-1.3)**: Detect if the orchestrator calls the same API with identical parameters more than twice without progress.
- **FC2: Inter-Agent Misalignment**
    - **Fail to Ask for Clarification (FM-2.2)**: If `ValidationAgent` returns "Unknown", the Evolver must ask for missing context instead of proceeding.
    - **Information Withholding (FM-2.4)**: Ensure full evidence traces are passed between `TTT` and `Validation` modules.
- **FC3: Task Verification**
    - **Incorrect Verification (FM-3.3)**: Implement a "Cross-Check Verifier" (e.g., if LLM rationale claims a gene is essential, verify the `Chronos Score` is actually < -0.5).

### 3.2 Recovery Strategies
| Detected Failure | Recovery Action |
| :--- | :--- |
| Step Repetition | Force parameter variation or query generalization. |
| Role Disobedience | Reset agent prompt with stricter "Constraint" block. |
| Incomplete Verification| Trigger "Deep Dive" mode (force L3/L4 validation). |

## 4. Implementation Plan

### Phase 1: Structured Communication (Standardization)
- Define a strict `HypothesisObject` and `ValidationScorecard` schema using Pydantic.
- Ensure all agent tool calls and responses adhere to this schema (theory of mind improvement).

### Phase 2: Hypothesis Evolver (ADRS Loop)
- Modify `orchestrator.py` to support multi-step iterations.
- Implement the "Refine" step where the LLM analyzes validation failures and proposes a "Hypothesis Delta."

### Phase 3: MAST Runtime Guard
- Implement `backend/app/mast_monitor.py` to trace and score internal agent conversations.
- Add a "Critique" step in `ttt.py` using the `AdversarialReviewer` to specifically search for MAST-defined failures.

### Phase 4: Reliable Verifier Enhancement
- Move `ValidationAgent` logic from template-based to "Evidence-Grounded Synthesis" where every claim must have a pointer to a tool result.

## 5. Success Metrics
- **Novelty Score**: Number of "Novel Connections" surfaced by `ttt.py`.
- **Validation Pass Rate**: Percentage of generated hypotheses that survive L3/L4 validation.
- **Robustness Index**: Reduction in "Step Repetition" and "Hallucinated Rationale" counts compared to current baseline.

---
*Reference:*
- *Cheng et al. (2025). Barbarians at the Gate: How AI is Upending Systems Research.*
- *Cemri et al. (2025). Why Do Multi-Agent LLM Systems Fail?*
