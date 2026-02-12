# v9 Specs: Integrating Google DeepMind Research into Onco-TTT

**Status:** Draft
**Date:** 2026-02-13
**References:**
1.  *Accelerating Scientific Research with Gemini* (Google DeepMind, 2026)
2.  *Towards Robust Mathematical Reasoning* (Google DeepMind, 2025)
3.  Gemini Deep Think Blog Post

## 1. Executive Summary

This document outlines specifications for upgrading the Oncology Hypothesis Generation tool (`ttt.py`) by incorporating key methodologies from Google DeepMind's recent research on scientific discovery and robust reasoning. The goal is to evolve the current **Query-Adaptive Graph Ranker** from a static spreading-activation system into a **Robust, Agentic Neuro-Symbolic Discovery Engine**.

The core shift is from *retrieval* to *reasoning*. We will move from simply finding relevant nodes to actively stress-testing hypotheses, iteratively refining queries, and validating connections using "Deep Think" inspired loops.

## 2. Core Architectural Changes

### 2.1 From Static Ranking to Agentic Loops (Neuro-Symbolic)
*Insight: "Agentic Execution Loops... embedding the AI in an automated neuro-symbolic loop where it autonomously writes and executes code to numerically verify its own mathematical hypotheses."*

**Current State:** `QueryAdaptiveRanker.rank(graph, query)` is a single-pass function.
**New State:** `AgenticDiscoveryLoop` class that wraps the ranker.

**Specification:**
*   **Iterative Refinement:** The system shall not stop at the first ranking.
    *   *Step 1:* Initial Rank (`rank(query)`).
    *   *Step 2:* **Hypothesis Formation:** LLM analyzes top nodes and high-activation "novel" nodes.
    *   *Step 3:* **Feedback Generation:** LLM formulates *new* queries to verify or expand on specific sub-graphs (e.g., "Find mechanism linking Node A and Node B").
    *   *Step 4:* Re-Rank with weighted history.
*   **Termination:** Loop continues until "Reasoning Saturation" (information gain drops) or fixed depth (e.g., 3 hops/iterations).

### 2.2 Robustified Querying (Robustness)
*Insight: "Problem Robustification... modifying numerical values, adding distractors, paraphrasing... to ensure that models utilize nontrivial reasoning."*

**Current State:** Result depends entirely on the specific phrasing of the input `query`.
**New State:** `RobustQueryEngine`.

**Specification:**
*   **Perturbation:** For every user query $Q$, generate a set $\{Q_1, Q_2, ..., Q_N\}$ of robust variants.
    *   *Paraphrasing:* Synonymous medical terms (e.g., "Neoplasm" vs "Cancer").
    *   *Specificity Shift:* Generalizing or specializing terms.
    *   *Adversarial Distractors:* Adding noise to ensure the signal is strong enough to survive.
*   **Ensemble Ranking:** Run `QueryAdaptiveRanker` on all variants.
    *   **Robust Score:** $S_{final}(node) = \text{mean}(S_{Q_i}(node)) - \lambda \cdot \text{std}(S_{Q_i}(node))$.
    *   This penalizes nodes that only appear for specific query phrasings (artifacts) and rewards nodes that are robustly relevant across all semantic variations.

### 2.3 Adversarial Validator (Deep Technical Review)
*Insight: "Adversarial Self-Correction... instruct the model to (1) generate an initial review, (2) critique its own findings for hallucinations, and (3) iteratively refine."*

**Current State:** No validation of the "Novel Connections".
**New State:** `AdversarialReviewer`.

**Specification:**
*   **The "Critic" Agent:** After the `AgenticDiscoveryLoop` proposes a hypothesis (e.g., "Gene X influences Pathway Y via Protein Z"), instantiate a Critic.
*   **Protocol:**
    1.  **Attack:** The Critic searches specifically for evidence *contradicting* the link (e.g., "Find studies showing Gene X does NOT affect Protein Z").
    2.  **Defense:** The Discovery Agent must defend the hypothesis using graph evidence.
    3.  **Verdict:** Only hypotheses that survive the adversarial critique are presented to the user.

### 2.4 Cross-Pollination Heuristics
*Insight: "Cross-Pollination of Ideas... retrieving obscure theorems from entirely different mathematical domains."*

**Current State:** Activation spreads based on edge weights.
**New State:** `CrossDomainBooster`.

**Specification:**
*   **Cluster Awareness:** If the graph has community detection/clustering (e.g., "Immunology", "Genetics", "Clinical"), explicitly boost paths that traverse *between* clusters.
*   **Bridge Scoring:** Reward nodes that act as "bridges" between high-activation clusters that are otherwise disconnected.
    *   *Formula:* $Score(n) = Activation(n) \times \text{ClusterEntropy}(\text{Neighbors}(n))$.
    *   Nodes connecting neighbors from diverse clusters get a boost, facilitating "Cross-Pollination".

## 3. Implementation Specs for `ttt.py`

### Class: `RobustRanker` (Wraps `QueryAdaptiveRanker`)
```python
class RobustRanker:
    def __init__(self, base_ranker: QueryAdaptiveRanker, num_variations=5):
        self.ranker = base_ranker
        self.num_variations = num_variations

    def rank_robust(self, graph, query) -> Dict[str, float]:
        # 1. Generate variations (LLM call)
        # 2. Run base_ranker.rank() in parallel
        # 3. Aggregate scores (Mean - Lambda * StdDev)
        pass
```

### Class: `NeuroSymbolicLoop`
```python
class NeuroSymbolicLoop:
    def __init__(self, ranker: RobustRanker):
        self.ranker = ranker

    def run_deep_think(self, graph, initial_query, max_steps=3):
        context = []
        current_query = initial_query
        
        for step in range(max_steps):
            # 1. Execute Robust Ranking
            results = self.ranker.rank_robust(graph, current_query)
            
            # 2. Symbol Grounding (Check constraints/logic)
            # Verify if top results make biological sense or violate known axioms
            
            # 3. Agentic Reflection (LLM)
            # "Given these results, what is the missing link? What should I ask next?"
            next_query, rationale = self.llm_reflect(results, context)
            
            # 4. Pruning
            # Remove "hallucinated" or irrelevant paths from graph view
            
            context.append((current_query, results))
            current_query = next_query
            
        return self.synthesize_findings(context)
```

## 4. Evaluation Strategy (Inspired by IMO-Bench)

*   **HypothesisBench:** Create a dataset of "Hidden Connections" (known scientific discoveries that are non-obvious).
*   **Metric:**
    *   *Recall:* Does the system find the connection?
    *   *Robustness:* Does it find it even if the query is vague or perturbed? (Robustification)
    *   *Precision:* Does the Adversarial Validator filter out spurious connections?

## 5. Next Steps
1.  Refactor `ttt.py` to expose the `QueryAdaptiveRanker` for composition.
2.  Implement `RobustRanker` with a simple synonym generator first.
3.  Implement the `AdversarialReviewer` logic using the project's LLM interface.
