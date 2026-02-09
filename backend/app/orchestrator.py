"""
AgentOrchestrator - Claude Agents SDK Integration

Smart routing layer that uses Claude to decide which APIs to call,
reducing redundant fetches and optimizing for relevance.

Cost optimization strategies:
1. Query analysis - Claude decides which tools are needed
2. Semantic caching - Skip API calls for similar recent queries
3. Tiered fetching - Start with fast/cheap, escalate if needed
4. Result synthesis - Combine results intelligently
"""

import os
import json
import hashlib
import asyncio
import logging
import threading
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
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
    """Single cache entry with TTL"""

    data: Any
    timestamp: datetime
    ttl_seconds: int = 3600  # 1 hour default

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)


class SemanticCache:
    """
    LRU cache with semantic similarity matching.
    Uses simple keyword overlap for fast matching (no embeddings needed).
    """

    def __init__(self, max_size: int = 1000):
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    def _normalize_key(self, tool: str, params: Dict) -> str:
        """Create normalized cache key"""
        # Sort params for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True).lower()
        return f"{tool}:{hashlib.md5(sorted_params.encode()).hexdigest()}"

    def _extract_keywords(self, params: Dict) -> set:
        """Extract keywords from parameters for fuzzy matching"""
        keywords = set()
        for v in params.values():
            if isinstance(v, str):
                # Split on common delimiters and normalize
                words = v.lower().replace("-", " ").replace("_", " ").split()
                keywords.update(words)
        return keywords

    def get(self, tool: str, params: Dict, fuzzy: bool = True) -> Optional[Any]:
        """
        Get cached result, optionally with fuzzy matching.
        """
        with self._lock:
            key = self._normalize_key(tool, params)

            # Exact match first
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired:
                    # Move to end (most recently used)
                    self.cache.move_to_end(key)
                    self.hits += 1
                    return entry.data
                else:
                    # Expired, remove
                    del self.cache[key]

            # Fuzzy match (same tool, similar params)
            if fuzzy:
                query_keywords = self._extract_keywords(params)
                best_match = None
                best_score = 0

                for cached_key, entry in self.cache.items():
                    if entry.is_expired:
                        continue
                    if not cached_key.startswith(f"{tool}:"):
                        continue

                    # Extract keywords from stored params
                    cached_keywords = self._extract_keywords(
                        entry.data.get("_params", {})
                    )
                    if not cached_keywords:
                        continue

                    intersection = len(query_keywords & cached_keywords)
                    union = len(query_keywords | cached_keywords)
                    score = intersection / union if union > 0 else 0

                    if score > 0.8 and score > best_score:  # 80% similarity threshold
                        best_score = score
                        best_match = entry.data

                if best_match:
                    self.hits += 1
                    return best_match

            self.misses += 1
            return None

    def set(self, tool: str, params: Dict, data: Any, ttl: int = 3600):
        """Store result in cache"""
        with self._lock:
            key = self._normalize_key(tool, params)

            # Store params for fuzzy matching
            data_with_meta = data.copy() if isinstance(data, dict) else {"_data": data}
            data_with_meta["_params"] = params

            self.cache[key] = CacheEntry(
                data=data_with_meta, timestamp=datetime.now(), ttl_seconds=ttl
            )

            # Evict oldest if over capacity
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    def stats(self) -> Dict:
        """Return cache statistics"""
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0,
            "size": len(self.cache),
            "max_size": self.max_size,
        }


class AgentOrchestrator:
    """
    Claude-powered orchestrator for intelligent API routing.

    Instead of calling ALL APIs for every query, Claude analyzes the
    query and decides which tools are actually needed.
    """

    def __init__(
        self,
        literature_fn: Callable,
        validation_agent: Any,
        structure_agent: Any,
        patent_agent: Any,
        enable_cache: bool = True,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = (
            anthropic.Anthropic(api_key=self.anthropic_key)
            if self.anthropic_key
            else None
        )

        # Tool implementations
        self.literature_fn = literature_fn
        self.validation_agent = validation_agent
        self.structure_agent = structure_agent
        self.patent_agent = patent_agent

        # Cache
        self.cache = SemanticCache() if enable_cache else None
        self.model = model

        # Stats
        self.total_queries = 0
        self.tools_called = 0
        self.tools_skipped = 0

    async def process_query(
        self,
        query: str,
        context: Optional[str] = None,
        force_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user query with intelligent tool routing.

        Args:
            query: User's natural language query
            context: Optional context (e.g., "lung cancer research")
            force_tools: Force specific tools to be called (bypasses Claude routing)

        Returns:
            Combined results from relevant tools
        """
        self.total_queries += 1

        # If no API key, fall back to calling all tools
        if not self.client:
            return await self._fallback_all_tools(query, context)

        # Build system prompt
        system = """You are a biomedical research assistant that helps route queries to the right data sources.
        
Your job is to analyze the user's query and decide which tools to call. Be selective - only call tools that are directly relevant to answering the query. This saves time and resources.

Guidelines:
- For questions about mechanisms or evidence: use search_literature
- For questions about drugs or treatment: use get_drug_targets
- For questions about clinical trials or competition: use check_clinical_trials  
- For questions about gene importance: use get_essentiality
- For questions about safety: use get_expression_safety
- For questions about prognosis: use get_survival_data
- For questions about protein structure: use get_protein_structure

Extract gene names, disease names, and mutations from the query to use as tool parameters.
You may call multiple tools if the query requires multiple types of information."""

        user_message = f"Query: {query}"
        if context:
            user_message += f"\nContext: {context}"

        try:
            # Call Claude with tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=[{"role": "user", "content": user_message}],
            )

            # Process tool calls
            results = {}
            tool_calls = [
                block for block in response.content if block.type == "tool_use"
            ]

            if not tool_calls:
                # Claude decided no tools needed - return text response
                text_blocks = [
                    block.text for block in response.content if hasattr(block, "text")
                ]
                return {
                    "response": " ".join(text_blocks),
                    "tools_used": [],
                    "from_cache": False,
                }

            # Execute tool calls (with caching)
            tools_used = []
            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_input = tool_call.input

                # Check cache first
                cached = self.cache.get(tool_name, tool_input) if self.cache else None
                if cached:
                    results[tool_name] = cached
                    self.tools_skipped += 1
                    tools_used.append({"name": tool_name, "cached": True})
                else:
                    # Execute tool
                    result = await self._execute_tool(tool_name, tool_input)
                    results[tool_name] = result
                    self.tools_called += 1
                    tools_used.append({"name": tool_name, "cached": False})

                    # Cache result
                    if self.cache and result:
                        self.cache.set(tool_name, tool_input, result)

            return {
                "results": results,
                "tools_used": tools_used,
                "cache_stats": self.cache.stats() if self.cache else None,
            }

        except Exception as e:
            logging.getLogger(__name__).error("Orchestrator error: %s", e)
            return await self._fallback_all_tools(query, context)

    async def _execute_tool(self, tool_name: str, params: Dict) -> Any:
        """Execute a specific tool"""
        try:
            if tool_name == "search_literature":
                return await self.literature_fn(
                    params.get("query", ""), params.get("limit", 10)
                )

            elif tool_name == "get_drug_targets":
                return await self.validation_agent.check_drugability(
                    params.get("gene", "")
                )

            elif tool_name == "check_clinical_trials":
                return await self.validation_agent.check_competition(
                    params.get("gene", ""), params.get("disease", "cancer")
                )

            elif tool_name == "get_essentiality":
                return await self.validation_agent.check_essentiality(
                    params.get("gene", ""), params.get("cancer_type", "")
                )

            elif tool_name == "get_expression_safety":
                return await self.validation_agent.check_toxicity(
                    params.get("gene", "")
                )

            elif tool_name == "get_survival_data":
                return await self.validation_agent.check_survival(
                    params.get("gene", ""), params.get("cancer_type", "")
                )

            elif tool_name == "get_protein_structure":
                return await self.structure_agent.fetch_structure(
                    params.get("gene", ""), params.get("mutation")
                )

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}

    async def _fallback_all_tools(self, query: str, context: Optional[str]) -> Dict:
        """Fallback: call all relevant tools (when Claude unavailable).

        Uses GLiNER2 for entity extraction instead of regex heuristics.
        Falls back to regex if GLiNER2 is unavailable.
        """
        gene = "UNKNOWN"
        disease = "cancer"

        try:
            from .entity_extraction import get_extractor
            from .kg_builder import entity_text

            extractor = get_extractor()
            extraction = extractor.extract_entities(query)
            entities = extraction.get("entities", {})

            # Pick the best gene
            genes = entities.get("gene", [])
            if genes:
                gene = entity_text(genes[0]) or "UNKNOWN"

            # Pick the best disease
            diseases = entities.get("disease", [])
            if diseases:
                disease = entity_text(diseases[0]) or "cancer"
        except Exception:
            # GLiNER2 unavailable, fall back to regex
            import re

            gene_match = re.search(r"\b([A-Z][A-Z0-9]{2,})\b", query)
            gene = gene_match.group(1) if gene_match else "UNKNOWN"
            for d in [
                "lung",
                "breast",
                "melanoma",
                "pancreatic",
                "colorectal",
                "leukemia",
            ]:
                if d in query.lower():
                    disease = f"{d} cancer"
                    break

        results = {}

        # Call literature search
        try:
            results["literature"] = await self.literature_fn(query, 10)
        except Exception as e:
            logging.getLogger(__name__).warning("Literature search failed: %s", e)

        # Call validation checks
        try:
            results["validation"] = await self.validation_agent.validate_hypothesis(
                gene, disease
            )
        except Exception as e:
            logging.getLogger(__name__).warning("Validation fallback failed: %s", e)

        return {
            "results": results,
            "tools_used": [{"name": "all", "cached": False}],
            "fallback": True,
        }

    def get_stats(self) -> Dict:
        """Return orchestrator statistics"""
        return {
            "total_queries": self.total_queries,
            "tools_called": self.tools_called,
            "tools_skipped_cache": self.tools_skipped,
            "cache_stats": self.cache.stats() if self.cache else None,
            "estimated_savings": f"{(self.tools_skipped / max(1, self.tools_called + self.tools_skipped)) * 100:.1f}%",
        }


# Convenience function for quick queries
async def smart_query(
    query: str,
    literature_fn: Callable,
    validation_agent: Any,
    structure_agent: Any = None,
    patent_agent: Any = None,
) -> Dict:
    """
    One-shot smart query using orchestrator.

    Example:
        result = await smart_query(
            "Is KRAS G12C druggable in lung cancer?",
            literature_agent.search_papers,
            validation_agent
        )
    """
    orchestrator = AgentOrchestrator(
        literature_fn=literature_fn,
        validation_agent=validation_agent,
        structure_agent=structure_agent,
        patent_agent=patent_agent,
    )
    return await orchestrator.process_query(query)
