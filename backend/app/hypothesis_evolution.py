"""
Adaptive Hypothesis Evolution Engine (AHEE)

Multi-island population-based evolution with adaptive strategy selection,
novelty filtering, Bayesian belief tracking, and meta-guidance.

References:
- ShinkaEvolve (Sakana AI): multi-island, power-law parent selection, novelty rejection
- AdaEvolve (UC Berkeley): UCB1 bandit mutation selection, meta-guidance on stall
- EvoX (UC Berkeley): adaptive alpha for explore/exploit shift
- Bayesian Teaching (Qiu et al., Nature Comms): probabilistic belief updates
"""

import math
import json
import random
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, AsyncGenerator

import anthropic

from .schemas import (
    HypothesisObject,
    ValidationScorecard,
    ValidationStatus,
    MutationOperator,
    EvolutionConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bayesian Belief Tracker
# ---------------------------------------------------------------------------

@dataclass
class HypothesisBelief:
    hypothesis_id: str
    prior: float = 0.5
    likelihoods: Dict[str, float] = field(default_factory=dict)
    trajectory: List[float] = field(default_factory=list)

    @property
    def posterior(self) -> float:
        log_posterior = math.log(max(self.prior, 1e-10))
        for likelihood in self.likelihoods.values():
            log_posterior += math.log(max(likelihood, 1e-10))
        return 1.0 / (1.0 + math.exp(-log_posterior))

    def update(self, check_name: str, score: float, fidelity: int):
        weight = fidelity / 4.0
        self.likelihoods[check_name] = max(score, 1e-10) ** weight
        self.trajectory.append(self.posterior)


# ---------------------------------------------------------------------------
# Island & Hypothesis Bank
# ---------------------------------------------------------------------------

@dataclass
class Island:
    name: str
    mutation_dimension: str  # "gene" | "disease" | "mechanism"
    population: List[HypothesisObject] = field(default_factory=list)
    best_score: float = 0.0
    stall_count: int = 0
    generation_history: List[Tuple[str, float]] = field(default_factory=list)


class HypothesisBank:
    def __init__(self):
        self._hypotheses: Dict[str, HypothesisObject] = {}
        self._scorecards: Dict[str, ValidationScorecard] = {}

    def add(self, hypothesis: HypothesisObject, scorecard: Optional[ValidationScorecard] = None):
        self._hypotheses[hypothesis.id] = hypothesis
        if scorecard:
            self._scorecards[hypothesis.id] = scorecard

    def get(self, hypothesis_id: str) -> Optional[HypothesisObject]:
        return self._hypotheses.get(hypothesis_id)

    def get_scorecard(self, hypothesis_id: str) -> Optional[ValidationScorecard]:
        return self._scorecards.get(hypothesis_id)

    def get_island_history(self, island_name: str) -> List[Tuple[HypothesisObject, ValidationScorecard]]:
        results = []
        for hid, h in self._hypotheses.items():
            if h.island == island_name and hid in self._scorecards:
                results.append((h, self._scorecards[hid]))
        return results

    def all_hypotheses(self) -> List[HypothesisObject]:
        return list(self._hypotheses.values())


# ---------------------------------------------------------------------------
# Novelty Filter
# ---------------------------------------------------------------------------

def _jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def is_novel(
    candidate: HypothesisObject,
    population: List[HypothesisObject],
    threshold: float = 0.85,
) -> bool:
    candidate_sig = {
        candidate.target_gene.lower(),
        candidate.disease.lower(),
        (candidate.mutation or "").lower(),
    }
    for existing in population:
        existing_sig = {
            existing.target_gene.lower(),
            existing.disease.lower(),
            (existing.mutation or "").lower(),
        }
        if _jaccard_similarity(candidate_sig, existing_sig) > threshold:
            return False
    return True


# ---------------------------------------------------------------------------
# Power-Law Parent Selection (ShinkaEvolve)
# ---------------------------------------------------------------------------

def select_parent(
    population: List[HypothesisObject],
    scores: Dict[str, float],
    alpha: float = 1.5,
) -> HypothesisObject:
    if len(population) == 1:
        return population[0]
    sorted_pop = sorted(population, key=lambda h: scores.get(h.id, 0), reverse=True)
    ranks = range(1, len(sorted_pop) + 1)
    weights = [1.0 / (r ** alpha) for r in ranks]
    return random.choices(sorted_pop, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Mutation Operators — specialized LLM prompts per strategy
# ---------------------------------------------------------------------------

MUTATION_PROMPTS: Dict[MutationOperator, str] = {
    MutationOperator.PIVOT_GENE: """\
You are an oncology research strategist. The current hypothesis targets {target_gene} \
in {disease}, but validation shows weak essentiality or target fitness.

Find a RELATED gene (same pathway, paralog, synthetic lethal partner, or \
upstream/downstream regulator) that is more likely to be essential in this \
disease context. Keep the disease and therapeutic approach similar.

Validation feedback (score {score}/100): {synthesis}""",

    MutationOperator.PIVOT_DISEASE: """\
You are an oncology research strategist. The current hypothesis targets {target_gene} \
in {disease}, but the indication fit is poor.

Identify a DIFFERENT cancer type or subtype where {target_gene} is more \
essential, has better survival correlation, or faces less competition. \
Keep the target gene and mechanism similar.

Validation feedback (score {score}/100): {synthesis}""",

    MutationOperator.NARROW_POPULATION: """\
You are an oncology research strategist. The current hypothesis targets {target_gene} \
in {disease}, but it faces HIGH competition from existing trials.

NARROW the patient population by adding a co-mutation, biomarker requirement, \
or histological subtype that creates a differentiated niche. The goal is to \
reduce competitive overlap while maintaining biological rationale.

Validation feedback (score {score}/100): {synthesis}""",

    MutationOperator.COMBINATION: """\
You are an oncology research strategist. You have two promising hypotheses:

Hypothesis A: {target_gene} in {disease} via {mechanism}
Hypothesis B: {alt_gene} in {alt_disease} via {alt_mechanism}

COMBINE the best elements of both into a single superior hypothesis. \
This could be a combination therapy, a dual-target approach, or a mechanism \
that bridges both biological insights.

Validation feedback on A (score {score}/100): {synthesis}""",

    MutationOperator.MECHANISM_SHIFT: """\
You are an oncology research strategist. The current hypothesis targets {target_gene} \
in {disease} via {mechanism}, but the current modality has druggability issues.

Explore a DIFFERENT therapeutic modality for the same target-disease pair. \
Consider: small molecule inhibitor, PROTAC/degrader, antibody-drug conjugate, \
bispecific antibody, CAR-T, mRNA vaccine, antisense oligonucleotide, or \
synthetic lethality-based combination.

Validation feedback (score {score}/100): {synthesis}""",

    MutationOperator.CROSS_POLLINATE: """\
You are an oncology research strategist. This island has stalled. \
A different evolutionary island produced this promising hypothesis:

Donor hypothesis: {alt_gene} in {alt_disease} via {alt_mechanism}

Import an IDEA from this donor and apply it to the current context of \
{target_gene} in {disease}. The import could be a mechanism insight, \
a patient selection strategy, or a therapeutic angle that hasn't been tried \
on this island yet.

Validation feedback (score {score}/100): {synthesis}""",
}

MUTATION_JSON_SCHEMA = """\

Return a JSON object (no markdown fencing):
{{"target_gene": "...", "disease": "...", "mutation": "... or null", \
"mechanism": "...", "rationale": "Why this is better", \
"refinement_reason": "Specific change made"}}"""


async def apply_mutation(
    operator: MutationOperator,
    parent: HypothesisObject,
    scorecard: ValidationScorecard,
    client: anthropic.AsyncAnthropic,
    model: str = "claude-sonnet-4-20250514",
    alt_hypothesis: Optional[HypothesisObject] = None,
) -> HypothesisObject:
    template = MUTATION_PROMPTS[operator]

    fmt_args: Dict[str, Any] = {
        "target_gene": parent.target_gene,
        "disease": parent.disease,
        "mechanism": parent.mechanism,
        "mutation": parent.mutation or "wild-type",
        "score": scorecard.overall_score,
        "synthesis": scorecard.synthesis,
    }
    if alt_hypothesis:
        fmt_args.update({
            "alt_gene": alt_hypothesis.target_gene,
            "alt_disease": alt_hypothesis.disease,
            "alt_mechanism": alt_hypothesis.mechanism,
        })
    else:
        fmt_args.update({"alt_gene": "", "alt_disease": "", "alt_mechanism": ""})

    prompt = template.format(**fmt_args) + MUTATION_JSON_SCHEMA

    response = await client.messages.create(
        model=model,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.content[0].text
    json_str = content[content.find("{"):content.rfind("}") + 1]
    result = json.loads(json_str)

    return HypothesisObject(
        id=str(uuid.uuid4()),
        target_gene=result["target_gene"],
        disease=result["disease"],
        mutation=result.get("mutation"),
        mechanism=result["mechanism"],
        rationale=result.get("rationale", ""),
        iteration=parent.iteration + 1,
        parent_id=parent.id,
        refinement_reason=result.get("refinement_reason", ""),
        island=parent.island,
        operator_used=operator,
    )


# ---------------------------------------------------------------------------
# UCB1 Bandit Strategy Selector (AdaEvolve)
# ---------------------------------------------------------------------------

@dataclass
class BanditArm:
    operator: MutationOperator
    total_reward: float = 0.0
    pull_count: int = 0

    def ucb_score(self, total_pulls: int, c: float = 1.414) -> float:
        if self.pull_count == 0:
            return float("inf")
        exploitation = self.total_reward / self.pull_count
        exploration = c * math.sqrt(math.log(total_pulls) / self.pull_count)
        return exploitation + exploration

    @property
    def avg_reward(self) -> float:
        return self.total_reward / self.pull_count if self.pull_count > 0 else 0.0


class AdaptiveStrategySelector:
    def __init__(self, ucb_c: float = 1.414):
        self.ucb_c = ucb_c
        self.arms: Dict[MutationOperator, BanditArm] = {
            op: BanditArm(operator=op) for op in MutationOperator
        }
        self._total_pulls = 0

    def select(self, exclude: Optional[List[MutationOperator]] = None) -> MutationOperator:
        candidates = {
            op: arm for op, arm in self.arms.items()
            if exclude is None or op not in exclude
        }
        if not candidates:
            candidates = self.arms

        best_op = max(
            candidates,
            key=lambda op: candidates[op].ucb_score(max(self._total_pulls, 1), self.ucb_c),
        )
        return best_op

    def update(self, operator: MutationOperator, reward: float):
        arm = self.arms[operator]
        arm.total_reward += reward
        arm.pull_count += 1
        self._total_pulls += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_pulls": self._total_pulls,
            "arms": {
                op.value: {
                    "pull_count": arm.pull_count,
                    "avg_reward": round(arm.avg_reward, 4),
                    "ucb_score": round(arm.ucb_score(max(self._total_pulls, 1), self.ucb_c), 4),
                }
                for op, arm in self.arms.items()
            },
        }
