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


# ---------------------------------------------------------------------------
# Meta-Guidance & Stall Detection (AdaEvolve)
# ---------------------------------------------------------------------------

def detect_stall(island: Island, threshold: int = 2) -> bool:
    return island.stall_count >= threshold


def update_stall_tracking(island: Island, new_best: float):
    if new_best > island.best_score:
        island.best_score = new_best
        island.stall_count = 0
    else:
        island.stall_count += 1


async def generate_meta_guidance(
    history: List[Tuple[HypothesisObject, ValidationScorecard]],
    client: anthropic.AsyncAnthropic,
    model: str = "claude-sonnet-4-20250514",
) -> Dict[str, str]:
    if not history:
        return {"tactic": "Start fresh with a new biological axis", "reasoning": "No history available"}

    summary = "\n".join([
        f"- {h.target_gene}/{h.disease}/{h.mechanism} "
        f"(op={h.operator_used.value if h.operator_used else 'seed'}) "
        f"-> score={s.overall_score}, status={s.overall_status.value}, "
        f"reason={h.refinement_reason or 'initial'}"
        for h, s in history
    ])

    prompt = f"""You are a meta-strategist for oncology hypothesis evolution.

The following hypotheses have been tried and their validation outcomes:
{summary}

The evolution is stalled -- no improvement in recent iterations.

Analyze the pattern of failures and propose a NOVEL strategic direction \
that hasn't been tried yet. Think beyond incremental changes:
- Is there a completely different biological axis to explore?
- Is the original research question too narrow or too broad?
- Should we pivot to a different therapeutic modality entirely?

Return a JSON object (no markdown fencing):
{{"tactic": "description of novel approach", "reasoning": "why this might break the stall"}}"""

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        json_str = content[content.find("{"):content.rfind("}") + 1]
        return json.loads(json_str)
    except Exception as e:
        logger.error("Meta-guidance generation failed: %s", e)
        return {"tactic": "Try a completely unrelated gene in the disease pathway", "reasoning": f"LLM fallback due to: {e}"}


async def inject_meta_seed(
    island: Island,
    tactic: Dict[str, str],
    base_hypothesis: HypothesisObject,
    client: anthropic.AsyncAnthropic,
    model: str = "claude-sonnet-4-20250514",
) -> HypothesisObject:
    prompt = f"""You are an oncology hypothesis generator.

A meta-strategist has suggested the following novel tactic:
Tactic: {tactic['tactic']}
Reasoning: {tactic['reasoning']}

The previous best hypothesis was: {base_hypothesis.target_gene} in \
{base_hypothesis.disease} via {base_hypothesis.mechanism}.

Generate a NEW hypothesis that follows the meta-strategist's tactic. \
This should be a significant departure from what's been tried before.

Return a JSON object (no markdown fencing):
{{"target_gene": "...", "disease": "...", "mutation": "... or null", \
"mechanism": "...", "rationale": "Why this follows the new tactic", \
"refinement_reason": "Meta-guidance: {tactic['tactic'][:80]}"}}"""

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=600,
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
            iteration=base_hypothesis.iteration + 1,
            parent_id=base_hypothesis.id,
            refinement_reason=result.get("refinement_reason", ""),
            island=island.name,
            operator_used=MutationOperator.CROSS_POLLINATE,
        )
    except Exception as e:
        logger.error("Meta-seed injection failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# Bayesian belief from ValidationScorecard
# ---------------------------------------------------------------------------

FIDELITY_MAP: Dict[str, int] = {
    "essentiality": 3,
    "survival": 4,
    "toxicity": 3,
    "drugability": 2,
    "competition": 4,
}


def belief_from_scorecard(
    hypothesis_id: str, scorecard: ValidationScorecard
) -> HypothesisBelief:
    belief = HypothesisBelief(hypothesis_id=hypothesis_id)
    for check_name, check in scorecard.checks.items():
        score_01 = check.score / 100.0
        fidelity = FIDELITY_MAP.get(check_name, 1)
        belief.update(check_name, score_01, fidelity)
    return belief


# ---------------------------------------------------------------------------
# AHEE Controller — main evolution engine
# ---------------------------------------------------------------------------

ISLAND_CONFIGS = [
    ("gene-centric", "gene"),
    ("disease-centric", "disease"),
    ("mechanism-centric", "mechanism"),
]

DIMENSION_PREFERRED_OPS: Dict[str, List[MutationOperator]] = {
    "gene": [MutationOperator.PIVOT_GENE, MutationOperator.COMBINATION],
    "disease": [MutationOperator.PIVOT_DISEASE, MutationOperator.NARROW_POPULATION],
    "mechanism": [MutationOperator.MECHANISM_SHIFT, MutationOperator.CROSS_POLLINATE],
}


class AHEEController:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        validation_agent: Any,
        extractor: Any = None,
        config: Optional[EvolutionConfig] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.client = client
        self.validation_agent = validation_agent
        self.extractor = extractor
        self.config = config or EvolutionConfig()
        self.model = model
        self.bank = HypothesisBank()
        self.strategy_selector = AdaptiveStrategySelector(ucb_c=self.config.ucb_c)
        self.beliefs: Dict[str, HypothesisBelief] = {}

    def _current_alpha(self, generation: int) -> float:
        cfg = self.config
        progress = generation / max(cfg.max_generations - 1, 1)
        return cfg.initial_alpha + (cfg.final_alpha - cfg.initial_alpha) * progress

    def _extract_seed(self, query: str) -> Dict[str, str]:
        target_gene = "Unknown"
        disease = "Cancer"
        mutation = None

        if self.extractor:
            try:
                extraction = self.extractor.extract_entities(query)
                genes = extraction.get("entities", {}).get("gene", [])
                if genes:
                    target_gene = genes[0]["text"]
                diseases = extraction.get("entities", {}).get("disease", [])
                if diseases:
                    disease = diseases[0]["text"]
                mutations = extraction.get("entities", {}).get("mutation", [])
                if mutations:
                    mutation = mutations[0]["text"]
            except Exception as e:
                logger.error("AHEE seed extraction failed: %s", e)

        return {"target_gene": target_gene, "disease": disease, "mutation": mutation}

    def _initialize_islands(self, seed: Dict[str, str], query: str) -> List[Island]:
        islands = []
        num = min(self.config.num_islands, len(ISLAND_CONFIGS))
        for i in range(num):
            name, dimension = ISLAND_CONFIGS[i]
            h = HypothesisObject(
                id=str(uuid.uuid4()),
                target_gene=seed["target_gene"],
                disease=seed["disease"],
                mutation=seed.get("mutation"),
                mechanism="Unknown",
                rationale=f"Seed hypothesis from query: {query[:100]}",
                iteration=0,
                island=name,
            )
            island = Island(name=name, mutation_dimension=dimension, population=[h])
            islands.append(island)
            self.beliefs[h.id] = HypothesisBelief(hypothesis_id=h.id)
        return islands

    def _update_population(
        self, island: Island, candidate: HypothesisObject, belief: HypothesisBelief
    ) -> List[HypothesisObject]:
        island.population.append(candidate)
        if len(island.population) > self.config.population_size:
            worst = min(
                island.population,
                key=lambda h: self.beliefs.get(h.id, HypothesisBelief(hypothesis_id=h.id)).posterior,
            )
            island.population.remove(worst)
        return island.population

    def _migrate(self, islands: List[Island]):
        if len(islands) < 2:
            return
        for i, source in enumerate(islands):
            if not source.population:
                continue
            target_island = islands[(i + 1) % len(islands)]
            best = max(
                source.population,
                key=lambda h: self.beliefs.get(h.id, HypothesisBelief(hypothesis_id=h.id)).posterior,
            )
            migrant = best.model_copy(deep=True)
            migrant.id = str(uuid.uuid4())
            migrant.island = target_island.name
            if is_novel(migrant, target_island.population, self.config.novelty_threshold):
                target_island.population.append(migrant)
                self.beliefs[migrant.id] = HypothesisBelief(
                    hypothesis_id=migrant.id,
                    prior=self.beliefs.get(best.id, HypothesisBelief(hypothesis_id=best.id)).posterior,
                )

    async def _pick_alt_hypothesis(self, islands: List[Island], current_island: Island) -> Optional[HypothesisObject]:
        other_pops = [
            h for island in islands if island.name != current_island.name
            for h in island.population
        ]
        if not other_pops:
            return None
        return max(
            other_pops,
            key=lambda h: self.beliefs.get(h.id, HypothesisBelief(hypothesis_id=h.id)).posterior,
        )

    async def run(self, query: str) -> AsyncGenerator[Dict, None]:
        seed = self._extract_seed(query)
        islands = self._initialize_islands(seed, query)

        yield {
            "type": "evolution_start",
            "num_islands": len(islands),
            "config": self.config.model_dump(),
        }

        for generation in range(self.config.max_generations):
            for island in islands:
                if not island.population:
                    continue

                scores = {
                    h.id: self.beliefs.get(h.id, HypothesisBelief(hypothesis_id=h.id)).posterior
                    for h in island.population
                }
                parent = select_parent(island.population, scores, self._current_alpha(generation))

                operator = self.strategy_selector.select()

                parent_scorecard = self.bank.get_scorecard(parent.id)
                if not parent_scorecard:
                    parent_scorecard = await self.validation_agent.validate_hypothesis(
                        parent.target_gene, parent.disease, parent.id
                    )
                    if isinstance(parent_scorecard, dict):
                        parent_scorecard = ValidationScorecard(**parent_scorecard)
                    self.bank.add(parent, parent_scorecard)
                    parent_belief = belief_from_scorecard(parent.id, parent_scorecard)
                    self.beliefs[parent.id] = parent_belief

                alt = await self._pick_alt_hypothesis(islands, island)

                try:
                    candidate = await apply_mutation(
                        operator, parent, parent_scorecard, self.client,
                        self.model, alt_hypothesis=alt,
                    )
                    candidate.island = island.name
                except Exception as e:
                    logger.error("Mutation %s failed: %s", operator.value, e)
                    yield {"type": "mutation_error", "island": island.name, "operator": operator.value, "error": str(e)}
                    continue

                if not is_novel(candidate, island.population, self.config.novelty_threshold):
                    yield {"type": "novelty_reject", "island": island.name, "generation": generation}
                    continue

                try:
                    scorecard = await self.validation_agent.validate_hypothesis(
                        candidate.target_gene, candidate.disease, candidate.id
                    )
                    if isinstance(scorecard, dict):
                        scorecard = ValidationScorecard(**scorecard)
                except Exception as e:
                    logger.error("Validation failed for candidate: %s", e)
                    continue

                belief = belief_from_scorecard(candidate.id, scorecard)
                self.beliefs[candidate.id] = belief
                self.bank.add(candidate, scorecard)

                candidate.belief_prior = 0.5
                candidate.belief_posterior = belief.posterior
                candidate.belief_trajectory = belief.trajectory

                parent_posterior = self.beliefs.get(
                    parent.id, HypothesisBelief(hypothesis_id=parent.id)
                ).posterior
                delta = belief.posterior - parent_posterior
                self.strategy_selector.update(operator, delta)

                update_stall_tracking(island, belief.posterior)
                self._update_population(island, candidate, belief)
                island.generation_history.append((candidate.id, belief.posterior))

                yield {
                    "type": "evolution_step",
                    "generation": generation,
                    "island": island.name,
                    "hypothesis": candidate.model_dump(),
                    "belief_posterior": round(belief.posterior, 4),
                    "operator_used": operator.value,
                    "delta": round(delta, 4),
                    "scorecard_summary": {
                        "overall_score": scorecard.overall_score,
                        "overall_status": scorecard.overall_status.value,
                    },
                }

            # Migration
            if generation > 0 and generation % self.config.migration_interval == 0:
                self._migrate(islands)
                yield {"type": "migration", "generation": generation}

            # Meta-guidance for stalled islands
            for island in islands:
                if detect_stall(island, self.config.stall_threshold):
                    history = self.bank.get_island_history(island.name)
                    tactic = await generate_meta_guidance(history, self.client, self.model)
                    yield {"type": "meta_guidance", "island": island.name, "tactic": tactic}

                    if island.population:
                        try:
                            meta_seed = await inject_meta_seed(
                                island, tactic, island.population[0], self.client, self.model,
                            )
                            island.population.append(meta_seed)
                            self.beliefs[meta_seed.id] = HypothesisBelief(hypothesis_id=meta_seed.id)
                        except Exception as e:
                            logger.error("Meta-seed injection failed: %s", e)
                    island.stall_count = 0

        # Final ranked results
        all_hypotheses = []
        for island in islands:
            all_hypotheses.extend(island.population)

        ranked = sorted(
            all_hypotheses,
            key=lambda h: self.beliefs.get(h.id, HypothesisBelief(hypothesis_id=h.id)).posterior,
            reverse=True,
        )

        for h in ranked:
            b = self.beliefs.get(h.id)
            if b:
                h.belief_posterior = b.posterior
                h.belief_trajectory = b.trajectory

        yield {
            "type": "final_results",
            "hypotheses": [h.model_dump() for h in ranked],
            "beliefs": {
                h.id: round(self.beliefs.get(h.id, HypothesisBelief(hypothesis_id=h.id)).posterior, 4)
                for h in ranked
            },
            "bandit_stats": self.strategy_selector.get_stats(),
            "island_summary": [
                {"name": isl.name, "population_size": len(isl.population), "best_score": round(isl.best_score, 4)}
                for isl in islands
            ],
        }
