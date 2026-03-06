# V10: Adaptive Hypothesis Evolution — Integrating EvoX/AdaEvolve/ShinkaEvolve + Bayesian Teaching

**Status:** Draft
**Date:** 2026-03-06
**References:**
0. Lange et al. (2025). ShinkaEvolve: Open-Ended And Sample-Efficient Program Evolution (Sakana AI)
1. Liu et al. (2026). EvoX: Meta-Evolution for Automated Discovery (UC Berkeley / SkyDiscover)
2. Cemri et al. (2026). AdaEvolve: Adaptive LLM Driven Zeroth-Order Optimization (UC Berkeley / SkyDiscover)
3. Qiu et al. (2026). Bayesian Teaching Enables Probabilistic Reasoning in LLMs (Nature Communications)

---

## 1. Executive Summary

The current Onco-TTT system has an ADRS evolution loop (`orchestrator.py:run_evolution_loop`) that is **linear and fixed-strategy**: it generates one hypothesis at a time, validates it, and evolves it sequentially for `max_iterations=3`. The evolution strategy (the LLM prompt in `HypothesisEvolver.evolve()`) is static — it doesn't adapt based on what kinds of refinements have historically worked.

This spec upgrades the evolution loop by incorporating three families of ideas:

**A. Adaptive Multi-Population Evolution (from EvoX/AdaEvolve/ShinkaEvolve):**
- Replace the single-hypothesis linear loop with a **multi-island population** of competing hypotheses
- Implement **adaptive parent selection** (power-law sampling from ShinkaEvolve) instead of always evolving the latest hypothesis
- Add **bandit-based strategy selection** so the system learns which mutation operators (pivot gene, pivot disease, pivot mechanism, combine hypotheses) work best for the current query
- Implement **meta-guidance** (from AdaEvolve) — when evolution stalls, the system generates novel tactics from the history of what's been tried

**B. Hypothesis Novelty Filtering (from ShinkaEvolve):**
- Reject hypothesis variants that are semantically too similar to existing population members
- Maintain diversity in the hypothesis bank to avoid premature convergence on one line of thinking

**C. Bayesian Belief Updates (from Bayesian Teaching):**
- Replace the current binary pass/fail validation with **probabilistic belief tracking** over hypothesis viability
- Each validation check updates a belief distribution rather than producing a single score
- Teach the LLM to reason probabilistically about which hypotheses are most promising given accumulating evidence

---

## 2. Current State Analysis

### 2.1 What Exists

| Component | File | Current State |
|:---|:---|:---|
| Evolution loop | `orchestrator.py:304-360` | Linear: 1 hypothesis → validate → evolve → repeat (max 3) |
| Hypothesis schema | `schemas.py:17-27` | `HypothesisObject` with `parent_id`, `iteration`, `refinement_reason` |
| Validation scorecard | `schemas.py:43-50` | 4 fidelity levels (L1-L4), overall score/status |
| Hypothesis evolver | `orchestrator.py:219-275` | Single LLM prompt, no strategy selection |
| MAST monitor | `mast_monitor.py` | Trace analysis for failure modes |
| TTT/NeuroSymbolic | `ttt.py:112-171` | `NeuroSymbolicLoop.run_deep_think_stream()` — 3-step activation propagation with adversarial review |
| Cross-domain boost | `ttt.py:55-69` | Entropy-based diversity boost on graph activations |
| Entity extraction | `entity_extraction.py` | GLiNER2-based extraction, used to seed evolution loop |
| Frontend pipeline | `PipelineStepper.tsx` | Shows evolution progress steps |
| Frontend ADRS/MAST | `page.tsx` | ADRS and MAST features surfaced in UI |

### 2.2 Key Gaps

1. **Single-hypothesis lineage**: Only one hypothesis evolves at a time. No population, no competition, no diversity.
2. **Fixed mutation operator**: `HypothesisEvolver.evolve()` uses one prompt for all refinement types. No specialization for "pivot gene" vs "pivot disease" vs "narrow patient population."
3. **No fitness landscape awareness**: The evolver doesn't know what's been tried before. It can't avoid repeating failed strategies.
4. **Static explore/exploit balance**: Always tries to "fix" the failing hypothesis. Never explores radically different angles.
5. **Binary validation**: `ValidationStatus.PASS` or not. No probabilistic reasoning about partial evidence.
6. **No novelty filtering**: Can generate the same hypothesis twice with slight wording changes.

---

## 3. Architecture: Adaptive Hypothesis Evolution Engine (AHEE)

### 3.1 Overview

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────┐
│  AHEE Controller (new: hypothesis_evolution.py) │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Island 1 │  │ Island 2 │  │ Island 3 │     │
│  │(gene-    │  │(disease- │  │(mechanism│     │
│  │ centric) │  │ centric) │  │ -centric)│     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
│       │              │              │           │
│       ▼              ▼              ▼           │
│  ┌─────────────────────────────────────┐       │
│  │   Hypothesis Bank (all islands)     │       │
│  │   + Novelty Filter                  │       │
│  │   + Bayesian Belief Tracker         │       │
│  └──────────────┬──────────────────────┘       │
│                 │                               │
│  ┌──────────────▼──────────────────────┐       │
│  │   Adaptive Strategy Selector        │       │
│  │   (UCB bandit over mutation ops)    │       │
│  └──────────────┬──────────────────────┘       │
│                 │                               │
│  ┌──────────────▼──────────────────────┐       │
│  │   Meta-Guidance (stall detector)    │       │
│  └─────────────────────────────────────┘       │
└─────────────────────────────────────────────────┘
    │
    ▼
Cascading Evaluator (existing: validation.py L1-L4)
    │
    ▼
Ranked Hypotheses → Frontend
```

### 3.2 Core Components

#### A. Multi-Island Hypothesis Populations

**Concept** (from ShinkaEvolve/EvoX): Instead of evolving one hypothesis linearly, maintain multiple "islands" that explore different evolutionary axes.

Each island specializes in a different mutation dimension:
- **Island 1 — Gene-Centric**: Varies the target gene (same pathway, paralog, upstream/downstream)
- **Island 2 — Disease-Centric**: Varies the indication (different cancer types, subtypes, histologies)
- **Island 3 — Mechanism-Centric**: Varies the therapeutic mechanism (inhibitor → degrader → combination → immunotherapy angle)

Islands exchange their best hypotheses periodically (**migration**, from ShinkaEvolve's inter-island knowledge transfer).

```python
# New file: backend/app/hypothesis_evolution.py

@dataclass
class Island:
    name: str
    population: List[HypothesisObject]  # max ~5 per island
    mutation_dimension: str  # "gene" | "disease" | "mechanism"
    best_score: float = 0.0
    stall_count: int = 0
```

#### B. Adaptive Parent Selection (from ShinkaEvolve)

**Current**: Always evolves the latest hypothesis (`current_hypothesis`).
**New**: Power-law selection over the full population, biased toward high-fitness parents but maintaining diversity.

```python
def select_parent(population: List[HypothesisObject],
                  scores: Dict[str, float],
                  alpha: float = 1.5) -> HypothesisObject:
    """
    Power-law parent selection (ShinkaEvolve).
    alpha > 1: exploitation-heavy (pick high scorers)
    alpha < 1: exploration-heavy (more uniform)
    """
    sorted_pop = sorted(population, key=lambda h: scores.get(h.id, 0), reverse=True)
    ranks = range(1, len(sorted_pop) + 1)
    weights = [1.0 / (r ** alpha) for r in ranks]
    total = sum(weights)
    probs = [w / total for w in weights]
    return random.choices(sorted_pop, weights=probs, k=1)[0]
```

The `alpha` parameter is **not fixed** — it starts exploration-heavy (alpha=0.8) and shifts toward exploitation (alpha=2.0) as the population matures. This is the key insight from EvoX's adaptive strategy evolution.

#### C. Bandit-Based Mutation Operator Selection (from AdaEvolve)

**Current**: One prompt template in `HypothesisEvolver.evolve()`.
**New**: Multiple specialized mutation operators, selected by UCB1 bandit.

```python
class MutationOperator(str, Enum):
    PIVOT_GENE = "pivot_gene"       # Try a related gene
    PIVOT_DISEASE = "pivot_disease" # Try a different indication
    NARROW_POPULATION = "narrow"    # Add biomarker/subtype specificity
    COMBINATION = "combination"     # Combine two parent hypotheses
    MECHANISM_SHIFT = "mechanism"   # Change therapeutic modality
    CROSS_POLLINATE = "cross"       # Import idea from different island

@dataclass
class BanditArm:
    operator: MutationOperator
    total_reward: float = 0.0
    pull_count: int = 0

    @property
    def ucb_score(self, total_pulls: int, c: float = 1.414) -> float:
        if self.pull_count == 0:
            return float('inf')
        exploitation = self.total_reward / self.pull_count
        exploration = c * math.sqrt(math.log(total_pulls) / self.pull_count)
        return exploitation + exploration
```

After each evolution step, the "reward" is the **improvement in validation score** (the "accumulated improvement signal" from AdaEvolve). This lets the system learn that, for example, "pivot gene" works well for lung cancer queries but "narrow population" works better for melanoma queries.

#### D. Hypothesis Novelty Rejection (from ShinkaEvolve)

Before adding a new hypothesis to the population, check semantic similarity against existing members. Reject if too similar.

```python
def is_novel(candidate: HypothesisObject,
             population: List[HypothesisObject],
             threshold: float = 0.85) -> bool:
    """
    Reject hypotheses that are too similar to existing population.
    Uses simple structural comparison (not embedding-based, to avoid
    adding a dependency).
    """
    candidate_sig = f"{candidate.target_gene}|{candidate.disease}|{candidate.mutation}"
    for existing in population:
        existing_sig = f"{existing.target_gene}|{existing.disease}|{existing.mutation}"
        overlap = _jaccard_similarity(
            set(candidate_sig.lower().split("|")),
            set(existing_sig.lower().split("|"))
        )
        if overlap > threshold:
            return False
    return True
```

For richer novelty detection (future): embed hypothesis text via the LLM and compute cosine similarity. For now, structural field comparison is sufficient and avoids new dependencies.

#### E. Meta-Guidance: Stall Detection & Tactic Generation (from AdaEvolve)

When an island's best score hasn't improved for N iterations, trigger meta-guidance.

```python
async def generate_meta_guidance(
    history: List[Tuple[HypothesisObject, ValidationScorecard]],
    client: anthropic.AsyncAnthropic
) -> str:
    """
    AdaEvolve Meta-Guidance: When evolution stalls, analyze what's
    been tried and generate novel tactics.
    """
    summary = "\n".join([
        f"- {h.target_gene}/{h.disease}/{h.mechanism} → score={s.overall_score}, "
        f"status={s.overall_status.value}, reason={h.refinement_reason}"
        for h, s in history
    ])

    prompt = f"""You are a meta-strategist for oncology hypothesis evolution.

The following hypotheses have been tried and their validation outcomes:
{summary}

The evolution is stalled — no improvement in the last iterations.

Analyze the pattern of failures and propose a NOVEL strategic direction
that hasn't been tried yet. Think beyond incremental changes:
- Is there a completely different biological axis to explore?
- Is the original research question too narrow or too broad?
- Should we pivot to a different therapeutic modality entirely?

Return a JSON object:
{{"tactic": "description of novel approach", "reasoning": "why this might break the stall"}}
"""
    # ... LLM call ...
```

#### F. Bayesian Belief Tracking (from Bayesian Teaching)

**Current**: `ValidationScorecard.overall_score` is a single number.
**New**: Maintain a **belief distribution** over hypothesis viability that updates as evidence accumulates.

The key insight from Qiu et al. is that LLMs can learn to update beliefs in a Bayesian-consistent way when taught with examples from the normative model. We apply this as follows:

```python
@dataclass
class HypothesisBelief:
    hypothesis_id: str
    prior: float = 0.5  # Start at maximum uncertainty
    likelihoods: Dict[str, float] = field(default_factory=dict)

    @property
    def posterior(self) -> float:
        """Bayesian update: P(viable | evidence) ∝ P(evidence | viable) * prior"""
        log_posterior = math.log(self.prior)
        for check, likelihood in self.likelihoods.items():
            log_posterior += math.log(likelihood + 1e-10)
        return 1.0 / (1.0 + math.exp(-log_posterior))  # sigmoid normalization

    def update(self, check_name: str, score: float, fidelity: int):
        """
        Higher fidelity evidence counts more.
        score: 0-1 from validation check
        fidelity: 1-4 (L1 through L4)
        """
        weight = fidelity / 4.0  # L4 evidence weighs 4x L1
        self.likelihoods[check_name] = score ** weight
```

This replaces the simple `overall_score` average with a principled belief update. L4 clinical evidence dramatically shifts the posterior; L1 plausibility checks barely move it.

The frontend will show the **belief trajectory** — how confidence in a hypothesis evolves as evidence accumulates — rather than just a final score.

---

## 4. Implementation Plan

### Phase 1: Hypothesis Population & Bank (New File)

**File:** `backend/app/hypothesis_evolution.py` (new)

Create the core data structures:
- `Island` dataclass with population management
- `HypothesisBank` class that stores all hypotheses across islands with lineage tracking
- `HypothesisBelief` for probabilistic scoring
- `is_novel()` novelty filter

**Changes to existing files:**
- `schemas.py`: Add `MutationOperator` enum, `HypothesisBelief` model, `EvolutionConfig` model
- `orchestrator.py:run_evolution_loop()`: Refactor to delegate to new `AHEEController`

### Phase 2: Mutation Operators (Specialize the Evolver)

**File:** `backend/app/hypothesis_evolution.py`

Split `HypothesisEvolver.evolve()` (currently `orchestrator.py:228-275`) into specialized operators:

| Operator | Prompt Strategy | When Selected |
|:---|:---|:---|
| `PIVOT_GENE` | "Find a related gene in the same pathway that scores better on essentiality" | Low DepMap score |
| `PIVOT_DISEASE` | "Try a different cancer type where this gene is more essential" | Low indication fit |
| `NARROW_POPULATION` | "Add a biomarker or co-mutation to increase specificity" | High competition |
| `COMBINATION` | "Combine the best aspects of these two parent hypotheses" | Multiple strong candidates |
| `MECHANISM_SHIFT` | "Explore a different therapeutic modality for this target" | Druggability issues |
| `CROSS_POLLINATE` | "Import an idea from a different evolutionary island" | Stalled island |

Each operator is a specialized prompt template that replaces the current generic one.

### Phase 3: Bandit Strategy Selection

**File:** `backend/app/hypothesis_evolution.py`

Implement:
- `BanditArm` dataclass with UCB1 scoring
- `AdaptiveStrategySelector` that maintains arms per `MutationOperator`
- Reward signal = `delta_score` (new validation score - parent validation score)
- Alpha adaptation: `alpha = 0.8 + (1.2 * iteration / max_iterations)` for explore→exploit shift

### Phase 4: Meta-Guidance & Stall Detection

**File:** `backend/app/hypothesis_evolution.py`

Implement:
- Stall detection: if `best_score` unchanged for 2 consecutive iterations on an island
- `generate_meta_guidance()` that analyzes the full evolution history
- Tactic injection: meta-guidance output becomes a new "seed" hypothesis on the stalled island

### Phase 5: Bayesian Belief Integration

**Files:**
- `backend/app/hypothesis_evolution.py`: `HypothesisBelief` class
- `backend/app/validation.py`: Modify validation checks to return probability-compatible scores
- `schemas.py`: Add `belief_prior`, `belief_posterior`, `belief_trajectory` fields to `HypothesisObject`

### Phase 6: Wire Into Main Pipeline

**Files:**
- `backend/app/orchestrator.py`: Replace `run_evolution_loop` with delegation to `AHEEController.run()`
- `backend/app/main.py`: Update `/generate` endpoint to support new evolution output format
- `backend/app/main.py`: New `/evolution/status` SSE endpoint for real-time evolution progress

### Phase 7: Frontend Evolution Visualization

**Files:**
- `frontend/app/components/EvolutionDashboard.tsx` (new): Shows multi-island evolution tree, belief trajectories, bandit arm statistics
- `frontend/app/components/PipelineStepper.tsx`: Update to show parallel island progress
- `frontend/app/page.tsx`: Integrate new dashboard tab

---

## 5. Detailed Specifications

### 5.1 `AHEEController` — Main Controller

```python
class AHEEController:
    """
    Adaptive Hypothesis Evolution Engine.
    Orchestrates multi-island evolution with adaptive strategy selection.
    """
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        validation_agent: ValidationAgent,
        extractor: Any,
        config: EvolutionConfig = EvolutionConfig()
    ):
        self.client = client
        self.validation_agent = validation_agent
        self.extractor = extractor
        self.config = config
        self.bank = HypothesisBank()
        self.strategy_selector = AdaptiveStrategySelector()
        self.beliefs: Dict[str, HypothesisBelief] = {}
        self.mast_monitor = MASTMonitor(client)

    async def run(self, query: str) -> AsyncGenerator[Dict, None]:
        """
        Main evolution loop. Yields SSE events for frontend consumption.
        """
        # 1. Extract entities from query
        entities = self._extract_seed(query)

        # 2. Initialize islands with seed hypotheses
        islands = self._initialize_islands(entities, query)

        # 3. Evolution loop
        for generation in range(self.config.max_generations):
            for island in islands:
                # a. Select parent (power-law)
                parent = select_parent(
                    island.population,
                    {h.id: self.beliefs[h.id].posterior for h in island.population},
                    alpha=self._current_alpha(generation)
                )

                # b. Select mutation operator (bandit)
                operator = self.strategy_selector.select(island.mutation_dimension)

                # c. Generate candidate
                candidate = await self._mutate(parent, operator, island)

                # d. Novelty check
                if not is_novel(candidate, island.population):
                    yield {"type": "novelty_reject", "island": island.name}
                    continue

                # e. Evaluate (cascading fidelity)
                scorecard = await self._evaluate(candidate)

                # f. Update belief
                belief = HypothesisBelief(hypothesis_id=candidate.id)
                for check_name, check in scorecard.checks.items():
                    belief.update(check_name, check.score / 100, check.metrics[0].fidelity.value if check.metrics else 1)
                self.beliefs[candidate.id] = belief

                # g. Update bandit reward
                parent_posterior = self.beliefs.get(parent.id, HypothesisBelief(hypothesis_id=parent.id)).posterior
                delta = belief.posterior - parent_posterior
                self.strategy_selector.update(operator, delta)

                # h. Add to population (evict worst if full)
                island.population = self._update_population(island, candidate, belief)

                yield {
                    "type": "evolution_step",
                    "generation": generation,
                    "island": island.name,
                    "hypothesis": candidate.model_dump(),
                    "belief": belief.posterior,
                    "operator_used": operator.value,
                    "delta": delta
                }

            # Migration between islands every N generations
            if generation > 0 and generation % self.config.migration_interval == 0:
                self._migrate(islands)

            # Meta-guidance for stalled islands
            for island in islands:
                if island.stall_count >= self.config.stall_threshold:
                    tactic = await generate_meta_guidance(
                        self.bank.get_island_history(island.name), self.client
                    )
                    yield {"type": "meta_guidance", "island": island.name, "tactic": tactic}
                    island.stall_count = 0

        # 4. Return ranked results
        all_hypotheses = []
        for island in islands:
            all_hypotheses.extend(island.population)
        ranked = sorted(all_hypotheses, key=lambda h: self.beliefs[h.id].posterior, reverse=True)

        yield {
            "type": "final_results",
            "hypotheses": [h.model_dump() for h in ranked],
            "beliefs": {h.id: self.beliefs[h.id].posterior for h in ranked},
            "bandit_stats": self.strategy_selector.get_stats()
        }
```

### 5.2 `EvolutionConfig` — Tunable Parameters

```python
class EvolutionConfig(BaseModel):
    max_generations: int = 3           # Total evolution generations
    population_size: int = 5           # Max hypotheses per island
    num_islands: int = 3               # Number of parallel islands
    migration_interval: int = 2        # Migrate every N generations
    migration_rate: float = 0.2        # Fraction of population to migrate
    stall_threshold: int = 2           # Generations without improvement before meta-guidance
    novelty_threshold: float = 0.85    # Jaccard similarity threshold for rejection
    initial_alpha: float = 0.8         # Parent selection: exploration-heavy start
    final_alpha: float = 2.0           # Parent selection: exploitation-heavy end
    ucb_c: float = 1.414              # UCB1 exploration constant
```

### 5.3 Schema Additions

Add to `schemas.py`:

```python
class MutationOperator(str, Enum):
    PIVOT_GENE = "pivot_gene"
    PIVOT_DISEASE = "pivot_disease"
    NARROW_POPULATION = "narrow_population"
    COMBINATION = "combination"
    MECHANISM_SHIFT = "mechanism_shift"
    CROSS_POLLINATE = "cross_pollinate"

class BeliefState(BaseModel):
    prior: float
    posterior: float
    likelihoods: Dict[str, float]
    trajectory: List[float] = []  # posterior after each evidence update

class EvolutionEvent(BaseModel):
    generation: int
    island: str
    hypothesis_id: str
    operator: MutationOperator
    belief_posterior: float
    delta: float
```

### 5.4 Frontend: Evolution Dashboard

New component `EvolutionDashboard.tsx`:

| Section | Visualization | Data Source |
|:---|:---|:---|
| **Island View** | 3 columns, each showing hypothesis cards with belief scores | `evolution_step` events |
| **Lineage Tree** | Tree/DAG showing parent→child relationships across generations | `hypothesis.parent_id` chain |
| **Belief Trajectory** | Sparkline per hypothesis showing posterior over time | `BeliefState.trajectory` |
| **Bandit Arms** | Bar chart showing pull counts and average reward per operator | `bandit_stats` from final results |
| **Meta-Guidance Log** | Timeline of stall detections and tactic injections | `meta_guidance` events |

---

## 6. API Changes

### New Endpoint: Evolution-Mode Generation

```
POST /generate-evolved
Body: { "query": str, "config": EvolutionConfig (optional) }
Response: SSE stream of EvolutionEvent objects
Final event: { "type": "final_results", "hypotheses": [...], "beliefs": {...} }
```

### Modified Endpoint: Standard Generation

The existing `POST /generate` remains unchanged for backward compatibility. The evolution features are opt-in via the new endpoint or a `?evolved=true` query parameter.

---

## 7. Migration Strategy

### Backward Compatibility

- `run_evolution_loop()` in `orchestrator.py` remains functional but internally delegates to `AHEEController` with `num_islands=1, max_generations=3` (equivalent to current behavior)
- Existing frontend components continue to work — the new `EvolutionDashboard` is an additional tab
- `HypothesisObject` schema is extended (new optional fields), not replaced

### Incremental Rollout

1. **Phase 1-2** can ship independently — improves hypothesis quality without UI changes
2. **Phase 3-4** adds intelligence — bandit stats visible in API response
3. **Phase 5** adds Bayesian beliefs — replaces simple scores with posterior probabilities
4. **Phase 6-7** wires everything to frontend — full evolution visualization

---

## 8. Key Design Decisions

### Why Multi-Island Instead of Single Population?

Single population risks premature convergence. A researcher asking about "KRAS G12C resistance in lung cancer" benefits from simultaneously exploring:
- Different genes in KRAS pathway (Island 1)
- Same gene in different cancers (Island 2)
- Different therapeutic approaches to same target (Island 3)

This maps directly to how researchers actually think: they explore multiple axes simultaneously.

### Why UCB1 Bandit Instead of Fixed Strategy Weights?

The optimal mutation operator depends on the query. For well-studied targets (KRAS, EGFR), pivoting to a new gene is often more productive than narrowing the population. For novel targets, narrowing the population is key. UCB1 learns this per-query.

### Why Bayesian Beliefs Instead of Weighted Average Scores?

A hypothesis with strong L1 plausibility but no L4 clinical data should NOT be scored equivalently to one with moderate scores across all levels. The Bayesian update naturally captures this: L4 evidence is much more informative, so it shifts the posterior more. This aligns with how scientists actually weigh evidence.

### Why Not Full Embedding-Based Novelty?

Adding a sentence embedding model would increase the dependency footprint and inference latency. The structural field comparison (gene|disease|mutation Jaccard) catches the most common case of near-duplicate hypotheses. Embedding-based novelty can be added later as an enhancement.

---

## 9. Relationship to Prior Versions

| Version | Key Innovation | This Version Builds On |
|:---|:---|:---|
| v0 | Core architecture (ARK, MEDEA, METIS, HypoBench) | Foundation schemas, agent pattern |
| v1 | Knowledge graph enhanced scoring | KG traversal for evidence gathering |
| v5 | Real validation data, target dossier, evidence trails | Validation checks used as fitness evaluator |
| v8 | Visual feedback, streaming progress | SSE pattern reused for evolution events |
| v9 | NeuroSymbolic loop, robust ranking, adversarial review | `ttt.py` components used within each island's evaluation |
| ADRS-MAST | Evolution loop, MAST monitoring, cascading evaluation | Direct predecessor — this spec replaces the linear loop |

---

## 10. Success Metrics

| Metric | Current Baseline | Target |
|:---|:---|:---|
| Hypothesis diversity (unique gene-disease pairs in top 5) | 1 (single lineage) | ≥3 |
| Validation pass rate (L3+ checks) | ~30% (estimate) | ≥50% |
| Novel connection discovery (cross-domain links) | Manual/ad-hoc | Tracked per-query via cross-pollination count |
| Evolution efficiency (generations to best hypothesis) | Fixed at 3 | Adaptive, measured by stall rate |
| User trust (belief trajectory visibility) | Binary pass/fail | Probabilistic with evidence attribution |

---

## 11. Verification Plan

### Unit Tests
- `test_parent_selection`: Verify power-law distribution produces expected selection frequencies
- `test_novelty_filter`: Verify similar hypotheses rejected, diverse ones accepted
- `test_bandit_ucb`: Verify UCB1 selects under-explored arms, then converges to best
- `test_bayesian_update`: Verify posterior moves correctly with L1 vs L4 evidence
- `test_meta_guidance`: Verify stall detection triggers after N generations

### Integration Tests
- Run `AHEEController.run()` with a real query (e.g., "KRAS G12C resistance in NSCLC")
- Verify: multiple islands produce distinct hypothesis lineages
- Verify: bandit arms show differential reward accumulation
- Verify: belief posteriors are between 0 and 1, increase with positive evidence

### End-to-End Test
- Start backend, hit `/generate-evolved` endpoint
- Verify SSE stream produces correct event sequence: `evolution_step` → `migration` → `meta_guidance` (if stalled) → `final_results`
- Frontend: verify EvolutionDashboard renders island cards, lineage tree, belief sparklines

---

## 12. File Change Summary

| File | Action | Description |
|:---|:---|:---|
| `backend/app/hypothesis_evolution.py` | **NEW** | Core AHEE: Island, HypothesisBank, BanditArm, AHEEController, mutation operators, novelty filter, meta-guidance, Bayesian belief |
| `backend/app/schemas.py` | MODIFY | Add MutationOperator, BeliefState, EvolutionEvent, EvolutionConfig |
| `backend/app/orchestrator.py` | MODIFY | `run_evolution_loop()` delegates to AHEEController |
| `backend/app/main.py` | MODIFY | Add `/generate-evolved` SSE endpoint |
| `backend/app/validation.py` | MODIFY | Return score as float 0-1 (currently 0-100) for Bayesian compatibility |
| `frontend/app/components/EvolutionDashboard.tsx` | **NEW** | Multi-island visualization, belief trajectories, bandit stats |
| `frontend/app/components/PipelineStepper.tsx` | MODIFY | Support parallel island progress |
| `frontend/app/page.tsx` | MODIFY | Add Evolution tab, wire new endpoint |
| `backend/tests/test_evolution.py` | **NEW** | Unit + integration tests for AHEE |

---

## 13. Open Questions

1. **LLM cost**: Multi-island evolution with 3 islands × 5 population × 3 generations = up to 45 LLM calls per query. Is this acceptable, or should we default to a smaller configuration (2 islands × 3 population × 2 generations = 12 calls)?

2. **Parallelism**: Should islands evolve in parallel (`asyncio.gather`) or sequentially? Parallel is faster but increases concurrent API calls.

3. **Persistence**: Should the hypothesis bank persist across sessions? This would enable longitudinal evolution (user returns next day, continues evolving).

4. **Alpha adaptation curve**: Linear interpolation from `initial_alpha` to `final_alpha`, or something more sophisticated (cosine annealing, step schedule)?
