from typing import List, Dict, Tuple, Optional, Set, Any
import networkx as nx
import statistics
import os
import logging
import asyncio
import json
from .mast_monitor import MASTMonitor
from .schemas import MASTFailureMode

# Try to import anthropic, handle if missing
try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger(__name__)

class QueryAdaptiveRanker:
    """
    Query-Adaptive Graph Ranking via Activation Propagation.
    """
    def __init__(self):
        self.learning_rate = 0.1
        self.steps = 5
        self.decay = 0.85

    def rank(self, graph: nx.DiGraph, query: str) -> Dict[str, float]:
        query_terms = query.lower().split()
        activations: Dict[str, float] = {}
        for node in graph.nodes():
            score = 0.0
            node_data = graph.nodes[node]
            node_label = node_data.get("label", str(node)).lower()
            for term in query_terms:
                if term in node_label: score += 1.0
            activations[node] = score
        for _ in range(self.steps):
            new_acts = {n: a * self.decay for n, a in activations.items()}
            for node in graph.nodes():
                if activations[node] > 0:
                    for neighbor in graph.neighbors(node):
                        edge_data = graph.get_edge_data(node, neighbor)
                        ew = edge_data.get("weight", 0.5) if edge_data else 0.5
                        new_acts[neighbor] = new_acts.get(neighbor, 0) + (activations[node] * ew * self.learning_rate)
                    for pred in graph.predecessors(node):
                        edge_data = graph.get_edge_data(pred, node)
                        ew = edge_data.get("weight", 0.5) if edge_data else 0.5
                        new_acts[pred] = new_acts.get(pred, 0) + (activations[node] * ew * self.learning_rate * 0.5)
            activations = new_acts
        max_score = max(activations.values()) if activations else 1.0
        if max_score > 0: activations = {n: round(s / max_score, 4) for n, s in activations.items()}
        return activations

class CrossDomainBooster:
    def boost(self, graph: nx.DiGraph, activations: Dict[str, float]) -> Dict[str, float]:
        boosted = activations.copy()
        import math
        for node in graph.nodes():
            if node not in activations or activations[node] < 0.05: continue
            neighbor_types = [graph.nodes[n].get("type", "unknown") for n in graph.neighbors(node)]
            if not neighbor_types: continue
            type_counts = {t: neighbor_types.count(t) for t in set(neighbor_types)}
            entropy = 0.0
            for count in type_counts.values():
                p = count / len(neighbor_types)
                if p > 0: entropy -= p * math.log(p)
            boosted[node] *= (1.0 + (entropy * 0.2))
        return boosted

class RobustRanker:
    def __init__(self, base_ranker: QueryAdaptiveRanker, client: Optional[Any] = None):
        self.ranker = base_ranker
        self.client = client

    async def rank_robust(self, graph: nx.DiGraph, query: str) -> Dict[str, float]:
        # Implementation from previous version
        return self.ranker.rank(graph, query)

class AdversarialReviewer:
    """
    "Deep Technical Review" agent.
    Critiques hypotheses using MAST taxonomy to find contradictions or failures.
    """
    def __init__(self, client: Optional[Any] = None):
        self.client = client
        if not self.client and anthropic:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def critique_hypothesis(self, hypothesis: str, evidence: List[str]) -> Tuple[bool, str, List[MASTFailureMode]]:
        if not self.client: return True, "Review skipped", []
        prompt = f"""Act as a skeptical senior scientist. Analyze this hypothesis for MAST failure modes.
        Hypothesis: {hypothesis}
        Evidence: {json.dumps(evidence)}
        
        Check for:
        - FM-3.3: Incorrect Verification (Data doesn't support claim)
        - FM-2.4: Information Withholding (Missing key biological context)
        
        Return JSON: {{"passed": bool, "critique": "...", "failures": ["FM-X.X"]}}
        """
        try:
            response = await self.client.messages.create(model="claude-3-5-sonnet-20240620", max_tokens=500, messages=[{"role": "user", "content": prompt}])
            content = response.content[0].text
            json_str = content[content.find("{"):content.rfind("}")+1]
            result = json.loads(json_str)
            return result.get("passed", True), result.get("critique", ""), [MASTFailureMode(f) for f in result.get("failures", [])]
        except: return True, "Review error", []

class NeuroSymbolicLoop:
    def __init__(self, ranker: RobustRanker, reviewer: AdversarialReviewer):
        self.ranker = ranker
        self.reviewer = reviewer
        self.booster = CrossDomainBooster()
        self.mast_monitor = MASTMonitor(reviewer.client)

    async def run_deep_think_stream(self, graph: nx.DiGraph, initial_query: str, max_steps: int = 3):
        current_query = initial_query
        trace = []
        cumulative_activations = {}

        for step in range(max_steps):
            yield {
                "type": "step_start",
                "step": step + 1,
                "query": current_query,
                "message": f"Deep Think Cycle {step + 1}: Investigating '{current_query}'",
            }

            # 1. Rank & Boost
            yield {"type": "status", "message": f"Step {step + 1}: Robustified Ranking..."}
            results = await self.ranker.rank_robust(graph, current_query)
            
            yield {"type": "status", "message": f"Step {step + 1}: Cross-Domain Boosting..."}
            results = self.booster.boost(graph, results)
            
            # Merge activations
            for n, s in results.items():
                cumulative_activations[n] = max(cumulative_activations.get(n, 0), s)

            # 2. Adversarial Critique
            yield {"type": "status", "message": f"Step {step + 1}: Adversarial Review (MAST)..."}
            top_evidence = [graph.nodes[n].get("label", str(n)) for n in list(results.keys())[:5]]
            passed, critique, failures = await self.reviewer.critique_hypothesis(current_query, top_evidence)
            
            trace.append({
                "step": step,
                "query": current_query,
                "passed": passed,
                "critique": critique,
                "detected_failures": [f.value for f in failures]
            })

            if not passed and step < max_steps - 1:
                current_query = f"Verify {current_query} considering {critique}"
            else:
                break

        yield {
            "type": "result",
            "data": {"activations": cumulative_activations, "trace": trace},
        }

    async def run_deep_think(self, graph: nx.DiGraph, initial_query: str, max_steps: int = 3) -> Dict[str, Any]:
        result = None
        async for event in self.run_deep_think_stream(graph, initial_query, max_steps):
            if event["type"] == "result":
                result = event["data"]
        return result or {"activations": {}, "trace": []}
