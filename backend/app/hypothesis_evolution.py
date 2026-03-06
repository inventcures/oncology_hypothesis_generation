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
