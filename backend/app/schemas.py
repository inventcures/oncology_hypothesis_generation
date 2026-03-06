from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
import math

class ValidationStatus(str, Enum):
    PASS = "pass"
    CAUTION = "caution"
    FAIL = "fail"
    UNKNOWN = "unknown"

class FidelityLevel(int, Enum):
    L1_PLAUSIBILITY = 1  # Literature / KG
    L2_TECHNICAL_FIT = 2 # Structure / AlphaFold
    L3_BIOLOGICAL_FIT = 3 # DepMap / GTEx
    L4_CLINICAL_FIT = 4   # TCGA / ClinTrials

class MutationOperator(str, Enum):
    PIVOT_GENE = "pivot_gene"
    PIVOT_DISEASE = "pivot_disease"
    NARROW_POPULATION = "narrow_population"
    COMBINATION = "combination"
    MECHANISM_SHIFT = "mechanism_shift"
    CROSS_POLLINATE = "cross_pollinate"


class HypothesisObject(BaseModel):
    id: str
    target_gene: str
    disease: str
    mutation: Optional[str] = None
    mechanism: str
    rationale: str
    evidence_score: float = 0.0
    iteration: int = 0
    parent_id: Optional[str] = None
    refinement_reason: Optional[str] = None
    island: Optional[str] = None
    operator_used: Optional[MutationOperator] = None
    belief_prior: float = 0.5
    belief_posterior: float = 0.5
    belief_trajectory: List[float] = []

class ValidationMetric(BaseModel):
    name: str
    value: Any
    interpretation: str
    fidelity: FidelityLevel

class ValidationCheck(BaseModel):
    title: str
    status: ValidationStatus
    score: float
    summary: str
    metrics: List[ValidationMetric] = []
    details: Dict[str, Any] = {}

class ValidationScorecard(BaseModel):
    hypothesis_id: str
    overall_score: float
    overall_status: ValidationStatus
    fidelity_reached: FidelityLevel
    checks: Dict[str, ValidationCheck]
    synthesis: str
    evidence_links: List[str] = []

class BeliefState(BaseModel):
    prior: float = 0.5
    posterior: float = 0.5
    likelihoods: Dict[str, float] = {}
    trajectory: List[float] = []


class EvolutionEvent(BaseModel):
    generation: int
    island: str
    hypothesis_id: str
    operator: MutationOperator
    belief_posterior: float
    delta: float


class EvolutionConfig(BaseModel):
    max_generations: int = 3
    population_size: int = 5
    num_islands: int = 3
    migration_interval: int = 2
    migration_rate: float = 0.2
    stall_threshold: int = 2
    novelty_threshold: float = 0.85
    initial_alpha: float = 0.8
    final_alpha: float = 2.0
    ucb_c: float = 1.414


class MASTFailureMode(str, Enum):
    DISOBEY_TASK = "FM-1.1"
    DISOBEY_ROLE = "FM-1.2"
    STEP_REPETITION = "FM-1.3"
    CONTEXT_LOSS = "FM-1.4"
    CLARIFICATION_FAIL = "FM-2.2"
    INFO_WITHHOLDING = "FM-2.4"
    INCORRECT_VERIFICATION = "FM-3.3"

class MASTReport(BaseModel):
    detected_failures: List[MASTFailureMode]
    critique: str
    recovery_suggestion: Optional[str] = None
    agent_trace: List[Dict[str, Any]]
