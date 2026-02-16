"""
AgentOrchestrator - ADRS & MAST Integration

Implements the AI-Driven Research for Systems (ADRS) loop for oncology 
hypothesis generation, with runtime robustness monitoring via MAST.
"""

import os
import json
import hashlib
import asyncio
import logging
import re
import threading
import uuid
from .constants import SEMANTIC_CACHE_MAX_SIZE, SEMANTIC_SIMILARITY_THRESHOLD
from typing import Dict, List, Any, Optional, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
from .schemas import (
    HypothesisObject, 
    ValidationScorecard, 
    ValidationStatus, 
    FidelityLevel,
    MASTReport,
    MASTFailureMode
)
from .mast_monitor import MASTMonitor
import anthropic

# Tool definitions for Claude
TOOLS = [
    {
        "name": "search_literature",
        "description": "Search Semantic Scholar for academic papers about a gene, disease, or treatment. Use when the query asks about research, evidence, mechanisms, or clinical studies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for academic papers (gene names, disease, mechanism)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum papers to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_drug_targets",
        "description": "Query OpenTargets for druggability information, existing drugs, and clinical pipeline. Use when asking about treatments, drugs, or therapeutic potential.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {
                    "type": "string",
                    "description": "Gene symbol (e.g., KRAS, TP53, EGFR)",
                },
                "disease": {
                    "type": "string",
                    "description": "Disease name for association score",
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "check_clinical_trials",
        "description": "Search ClinicalTrials.gov for ongoing trials. Use when asking about competition, clinical development, or trial landscape.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Target gene"},
                "disease": {"type": "string", "description": "Disease/cancer type"},
                "status": {
                    "type": "string",
                    "description": "Trial status filter (RECRUITING, ACTIVE, COMPLETED)",
                    "enum": ["RECRUITING", "ACTIVE", "COMPLETED", "ALL"],
                    "default": "ALL",
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "get_essentiality",
        "description": "Check DepMap for gene essentiality in cancer cell lines. Use when asking about whether a gene is essential, dependency scores, or knockout effects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol"},
                "cancer_type": {
                    "type": "string",
                    "description": "Specific cancer type to filter cell lines",
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "get_expression_safety",
        "description": "Check GTEx for normal tissue expression to assess toxicity risk. Use when asking about safety, side effects, or tissue specificity.",
        "input_schema": {
            "type": "object",
            "properties": {"gene": {"type": "string", "description": "Gene symbol"}},
            "required": ["gene"],
        },
    },
    {
        "name": "get_survival_data",
        "description": "Get TCGA survival analysis data. Use when asking about prognosis, patient outcomes, or survival correlation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol"},
                "cancer_type": {
                    "type": "string",
                    "description": "TCGA cancer type code (e.g., LUAD, BRCA)",
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "get_protein_structure",
        "description": "Fetch AlphaFold structure and analyze druggable pockets. Use when asking about structure, binding sites, or protein conformation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol or UniProt ID"},
                "mutation": {
                    "type": "string",
                    "description": "Specific mutation to analyze (e.g., G12C, V600E)",
                },
            },
            "required": ["gene"],
        },
    },
]

@dataclass
class CacheEntry:
    data: Any
    timestamp: datetime
    ttl_seconds: int = 3600

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)

class SemanticCache:
    def __init__(self, max_size: int = SEMANTIC_CACHE_MAX_SIZE):
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    def _normalize_key(self, tool: str, params: Dict) -> str:
        sorted_params = json.dumps(params, sort_keys=True).lower()
        return f"{tool}:{hashlib.sha256(sorted_params.encode()).hexdigest()}"

    def _extract_keywords(self, params: Dict) -> set:
        keywords = set()
        for v in params.values():
            if isinstance(v, str):
                words = v.lower().replace("-", " ").replace("_", " ").split()
                keywords.update(words)
        return keywords

    def get(self, tool: str, params: Dict, fuzzy: bool = True) -> Optional[Any]:
        with self._lock:
            key = self._normalize_key(tool, params)
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired:
                    self.cache.move_to_end(key)
                    self.hits += 1
                    return entry.data
                else:
                    del self.cache[key]
            if fuzzy:
                query_keywords = self._extract_keywords(params)
                best_match, best_score = None, 0
                for cached_key, entry in self.cache.items():
                    if entry.is_expired or not cached_key.startswith(f"{tool}:"):
                        continue
                    cached_keywords = self._extract_keywords(entry.data.get("_params", {}))
                    if not cached_keywords: continue
                    intersection = len(query_keywords & cached_keywords)
                    union = len(query_keywords | cached_keywords)
                    score = intersection / union if union > 0 else 0
                    if score > SEMANTIC_SIMILARITY_THRESHOLD and score > best_score:
                        best_score = score
                        best_match = entry.data
                if best_match:
                    self.hits += 1
                    return best_match
            self.misses += 1
            return None

    def set(self, tool: str, params: Dict, data: Any, ttl: int = 3600):
        with self._lock:
            key = self._normalize_key(tool, params)
            data_with_meta = data.copy() if isinstance(data, dict) else {"_data": data}
            data_with_meta["_params"] = params
            self.cache[key] = CacheEntry(data=data_with_meta, timestamp=datetime.now(), ttl_seconds=ttl)
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    def stats(self) -> Dict:
        total = self.hits + self.misses
        return {"hits": self.hits, "misses": self.misses, "hit_rate": self.hits / total if total > 0 else 0, "size": len(self.cache), "max_size": self.max_size}

class HypothesisEvolver:
    """
    ADRS Solution Generator: Hypothesis Refiner.
    Takes validation feedback and evolves the hypothesis.
    """
    def __init__(self, client: anthropic.AsyncAnthropic, model: str):
        self.client = client
        self.model = model

    async def evolve(self, hypothesis: HypothesisObject, scorecard: ValidationScorecard) -> HypothesisObject:
        prompt = f"""You are an AI research scientist evolving an oncology hypothesis.
        
Current Hypothesis:
- Target: {hypothesis.target_gene}
- Disease: {hypothesis.disease}
- Mutation: {hypothesis.mutation}
- Mechanism: {hypothesis.mechanism}

Validation Feedback (Score: {scorecard.overall_score}/100, Status: {scorecard.overall_status}):
{scorecard.synthesis}

Task:
Refine this hypothesis to overcome validation failures.
- If essentiality is low, consider a related gene in the same pathway.
- If toxicity is high, search for a more tumor-selective mutation or context.
- If competition is high, find a novel combination or patient subpopulation.

Return a JSON object:
{{
    "target_gene": "...",
    "disease": "...",
    "mutation": "...",
    "mechanism": "...",
    "rationale": "Why this evolved version is better",
    "refinement_reason": "Specific fix for {scorecard.overall_status} status"
}}
"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        json_str = content[content.find("{") : content.rfind("}") + 1]
        result = json.loads(json_str)
        
        return HypothesisObject(
            id=str(uuid.uuid4()),
            target_gene=result["target_gene"],
            disease=result["disease"],
            mutation=result.get("mutation"),
            mechanism=result["mechanism"],
            rationale=result["rationale"],
            iteration=hypothesis.iteration + 1,
            parent_id=hypothesis.id,
            refinement_reason=result["refinement_reason"]
        )

class AgentOrchestrator:
    def __init__(
        self,
        literature_fn: Callable,
        validation_agent: Any,
        structure_agent: Any,
        patent_agent: Any,
        extractor: Any = None,
        enable_cache: bool = True,
        model: str = "claude-3-5-sonnet-20240620",
    ):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.AsyncAnthropic(api_key=self.anthropic_key) if self.anthropic_key else None
        self.literature_fn = literature_fn
        self.validation_agent = validation_agent
        self.structure_agent = structure_agent
        self.patent_agent = patent_agent
        self.extractor = extractor
        self.cache = SemanticCache() if enable_cache else None
        self.model = model
        self.mast_monitor = MASTMonitor(self.client)
        self.evolver = HypothesisEvolver(self.client, model)
        self._stats_lock = threading.Lock()
        self.total_queries = 0
        self.tools_called = 0
        self.tools_skipped = 0

    async def run_evolution_loop(self, initial_query: str, max_iterations: int = 3) -> List[Tuple[HypothesisObject, ValidationScorecard]]:
        """
        Full ADRS loop: Generate -> Evaluate -> Refine.
        """
        history = []
        
        # 1. Initial Extraction using GLiNER2
        target_gene = "Unknown"
        disease = "Cancer"
        mutation = None
        mechanism = "Unknown"

        if self.extractor:
            try:
                extraction = self.extractor.extract_entities(initial_query)
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
                logging.getLogger(__name__).error("Evolution loop extraction failed: %s", e)

        current_hypothesis = HypothesisObject(
            id=str(uuid.uuid4()),
            target_gene=target_gene,
            disease=disease,
            mutation=mutation,
            mechanism=mechanism,
            rationale="Initial hypothesis extracted from query",
            iteration=0
        )

        for i in range(max_iterations):
            # 2. Evaluation (Reliable Verifier)
            scorecard_data = await self.validation_agent.validate_hypothesis(
                current_hypothesis.target_gene, 
                current_hypothesis.disease
            )
            # Ensure it returns ValidationScorecard schema
            scorecard = ValidationScorecard(**scorecard_data) if isinstance(scorecard_data, dict) else scorecard_data
            
            history.append((current_hypothesis, scorecard))
            
            if scorecard.overall_status == ValidationStatus.PASS or i == max_iterations - 1:
                break
                
            # 3. Refinement (ADRS Evolver)
            current_hypothesis = await self.evolver.evolve(current_hypothesis, scorecard)
            
        return history

    async def process_query(self, query: str, context: Optional[str] = None) -> Dict[str, Any]:
        with self._stats_lock: self.total_queries += 1
        if not self.client: return await self._fallback_all_tools(query, context)

        trace = []
        system = """You are a biomedical research assistant that helps route queries to the right data sources."""
        user_message = f"Query: {query}"
        if context: user_message += f"\nContext: {context}"

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=[{"role": "user", "content": user_message}],
            )

            results = {}
            tool_calls = [block for block in response.content if block.type == "tool_use"]
            
            if not tool_calls:
                return {"response": response.content[0].text, "tools_used": [], "from_cache": False}

            for tool_call in tool_calls:
                trace.append({"type": "tool_call", "tool": tool_call.name, "params": tool_call.input})
                
                # MAST repetition check
                if self.mast_monitor.detect_step_repetition(trace):
                    results[tool_call.name] = {"error": "MAST Alert: Detected step repetition. Diversifying search."}
                    continue

                cached = self.cache.get(tool_call.name, tool_call.input) if self.cache else None
                if cached:
                    results[tool_call.name] = cached
                    with self._stats_lock: self.tools_skipped += 1
                else:
                    result = await self._execute_tool(tool_call.name, tool_call.input)
                    results[tool_call.name] = result
                    with self._stats_lock: self.tools_called += 1
                    if self.cache and result: self.cache.set(tool_call.name, tool_call.input, result)

            # Analyze trace with MAST
            mast_report = await self.mast_monitor.analyze_trace(trace)
            
            return {
                "results": results,
                "tools_used": [t["tool"] for t in trace],
                "mast_report": mast_report.model_dump(),
                "cache_stats": self.cache.stats() if self.cache else None,
            }

        except Exception as e:
            logging.getLogger(__name__).error("Orchestrator error: %s", e)
            return await self._fallback_all_tools(query, context)

    async def _execute_tool(self, tool_name: str, params: Dict) -> Any:
        try:
            if tool_name == "search_literature": return await self.literature_fn(params.get("query", ""), params.get("limit", 10))
            elif tool_name == "get_drug_targets": return await self.validation_agent.check_drugability(params.get("gene", ""))
            elif tool_name == "check_clinical_trials": return await self.validation_agent.check_competition(params.get("gene", ""), params.get("disease", "cancer"))
            elif tool_name == "get_essentiality": return await self.validation_agent.check_essentiality(params.get("gene", ""), params.get("cancer_type", ""))
            elif tool_name == "get_expression_safety": return await self.validation_agent.check_toxicity(params.get("gene", ""))
            elif tool_name == "get_survival_data": return await self.validation_agent.check_survival(params.get("gene", ""), params.get("cancer_type", ""))
            elif tool_name == "get_protein_structure": return await self.structure_agent.fetch_structure(params.get("gene", ""), params.get("mutation"))
            else: return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e: return {"error": str(e)}

    async def _fallback_all_tools(self, query: str, context: Optional[str]) -> Dict:
        # Simplified fallback
        return {"results": {}, "fallback": True}

    def get_stats(self) -> Dict:
        return {
            "total_queries": self.total_queries,
            "tools_called": self.tools_called,
            "tools_skipped_cache": self.tools_skipped,
            "cache_stats": self.cache.stats() if self.cache else None,
        }
