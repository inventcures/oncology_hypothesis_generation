from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

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
