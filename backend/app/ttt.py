from typing import List, Dict, Tuple, Optional, Set, Any
import networkx as nx
import statistics
import os
import logging
import asyncio
import json

# Try to import anthropic, handle if missing
try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger(__name__)


class QueryAdaptiveRanker:
    """
    Query-Adaptive Graph Ranking via Activation Propagation.

    Performs spreading-activation on the knowledge graph to discover
    which nodes are most relevant to a specific query. The activation
    scores are used to:
    1. Rank/weight nodes for hypothesis generation (higher activation = prioritized)
    2. Add a 'relevance' signal to the serialised graph (frontend glow/size)
    3. Surface non-obvious connections (nodes with high activation but no direct query match)

    This is NOT neural test-time training — it is a graph-theoretic
    spreading-activation algorithm inspired by associative memory models.
    """

    def __init__(self):
        self.learning_rate = 0.1
        self.steps = 5
        self.decay = 0.85  # Activation decays each step to prevent unbounded growth

    def rank(self, graph: nx.DiGraph, query: str) -> Dict[str, float]:
        """
        Propagate query-seeded activations through the graph.

        Returns:
            Dict mapping node_id -> activation_score (normalized 0-1).
            Scores reflect query-specific relevance.
        """
        query_terms = query.lower().split()
        activations: Dict[str, float] = {}

        # 1. Seed activations from query term matches
        for node in graph.nodes():
            score = 0.0
            # Handle node which might be complex object or string
            # Assuming node is ID, and we look up data in graph
            node_data = graph.nodes[node]
            node_label = node_data.get("label", str(node)).lower()

            # Simple term matching
            for term in query_terms:
                if term in node_label:
                    score += 1.0
            activations[node] = score

        # 2. Propagate activations through graph edges
        for step in range(self.steps):
            new_acts = {n: a * self.decay for n, a in activations.items()}
            for node in graph.nodes():
                if activations[node] > 0:
                    # Propagate to neighbors (outgoing)
                    for neighbor in graph.neighbors(node):
                        edge_data = graph.get_edge_data(node, neighbor)
                        edge_weight = edge_data.get("weight", 0.5) if edge_data else 0.5
                        new_acts[neighbor] = new_acts.get(neighbor, 0) + (
                            activations[node] * edge_weight * self.learning_rate
                        )
                    # Also propagate backwards (undirected spreading effect)
                    for predecessor in graph.predecessors(node):
                        edge_data = graph.get_edge_data(predecessor, node)
                        edge_weight = edge_data.get("weight", 0.5) if edge_data else 0.5
                        new_acts[predecessor] = new_acts.get(predecessor, 0) + (
                            activations[node] * edge_weight * self.learning_rate * 0.5
                        )
            activations = new_acts

        # 3. Normalize to 0-1 range
        max_score = max(activations.values()) if activations else 1.0
        if max_score > 0:
            activations = {n: round(s / max_score, 4) for n, s in activations.items()}

        return activations

    def get_top_nodes(self, activations: Dict[str, float], k: int = 10) -> List[str]:
        """Return top-k activated node IDs."""
        sorted_nodes = sorted(activations.items(), key=lambda x: x[1], reverse=True)
        return [n for n, score in sorted_nodes[:k] if score > 0.01]

    def get_novel_connections(
        self,
        activations: Dict[str, float],
        query: str,
        k: int = 5,
        graph: Optional[nx.DiGraph] = None,
    ) -> List[Tuple[str, float]]:
        """
        Find nodes with high activation but NO direct query term match.
        These represent non-obvious connections discovered via propagation.
        """
        query_terms = set(query.lower().split())
        novel = []
        for node, score in activations.items():
            if score > 0.1:
                # Check label if graph provided, else use node ID
                node_label = str(node).lower()
                if graph:
                    node_label = graph.nodes[node].get("label", str(node)).lower()

                if not any(term in node_label for term in query_terms):
                    novel.append((node, score))
        novel.sort(key=lambda x: x[1], reverse=True)
        return novel[:k]


class CrossDomainBooster:
    """
    Boosts nodes that act as 'bridges' between different clusters (e.g., Immunology <-> Genetics).
    Implements the 'Cross-Pollination' heuristic.
    """

    def __init__(self):
        pass

    def boost(
        self, graph: nx.DiGraph, activations: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Adjust activation scores to reward boundary-spanning nodes.
        """
        boosted_activations = activations.copy()

        # Calculate cluster entropy for each node's neighborhood
        for node in graph.nodes():
            if node not in activations or activations[node] < 0.05:
                continue

            neighbors = list(graph.neighbors(node))
            if not neighbors:
                continue

            # Collect cluster/type info of neighbors
            neighbor_types = []
            for n in neighbors:
                # Assuming 'type' or 'cluster' attribute exists, defaulting to 'unknown'
                n_type = graph.nodes[n].get("type", "unknown")
                neighbor_types.append(n_type)

            if not neighbor_types:
                continue

            # Calculate entropy (diversity of neighbor types)
            type_counts = {t: neighbor_types.count(t) for t in set(neighbor_types)}
            total_neighbors = len(neighbors)
            entropy = 0.0
            import math

            for count in type_counts.values():
                p = count / total_neighbors
                if p > 0:
                    entropy -= p * math.log(p)

            # Boost score based on entropy (higher entropy = more cross-domain)
            # Factor: 1.0 to 1.5x based on entropy
            boost_factor = 1.0 + (entropy * 0.2)
            boosted_activations[node] *= boost_factor

        return boosted_activations


class RobustRanker:
    """
    Wraps QueryAdaptiveRanker to perform ensemble ranking over perturbed queries.
    Implements 'Robustified Querying' to ensure findings are stable.
    """

    def __init__(
        self,
        base_ranker: QueryAdaptiveRanker,
        client: Optional[Any] = None,
        num_variations: int = 3,
    ):
        self.ranker = base_ranker
        self.num_variations = num_variations
        self.client = client
        if not self.client and anthropic:
            # Try to instantiate if key available
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def _generate_variations(self, query: str) -> List[str]:
        """Generate semantic variations of the query using LLM."""
        if not self.client:
            return [query]  # Fallback if no LLM

        prompt = f"""Generate {self.num_variations} semantic variations of the following scientific query to test robustness.
        Include 1 paraphrase, 1 generalization, and 1 more specific version.
        Return ONLY the variations, one per line.
        
        Query: "{query}"
        """

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            variations = [line.strip() for line in text.split("\n") if line.strip()]
            return [query] + variations[: self.num_variations]
        except Exception as e:
            logger.warning(f"Failed to generate query variations: {e}")
            return [query]

    async def rank_robust(self, graph: nx.DiGraph, query: str) -> Dict[str, float]:
        """
        Execute robust ranking by aggregating scores across query variations.

        Score = Mean(Scores) - Lambda * StdDev(Scores)
        """
        variations = await self._generate_variations(query)
        logger.info(f"Robust ranking with variations: {variations}")

        all_activations = []
        for q in variations:
            # base_ranker.rank is synchronous
            acts = self.ranker.rank(graph, q)
            all_activations.append(acts)

        # Aggregate
        final_scores = {}
        all_nodes = set().union(*[d.keys() for d in all_activations])

        lambda_penalty = 0.5

        for node in all_nodes:
            scores = [act.get(node, 0.0) for act in all_activations]
            mean_score = statistics.mean(scores)
            std_dev = statistics.stdev(scores) if len(scores) > 1 else 0.0

            robust_score = mean_score - (lambda_penalty * std_dev)
            if robust_score > 0:
                final_scores[node] = round(robust_score, 4)

        return final_scores


class AdversarialReviewer:
    """
    "Deep Technical Review" agent.
    Critiques hypotheses by actively searching for contradictions.
    """

    def __init__(self, client: Optional[Any] = None):
        self.client = client
        if not self.client and anthropic:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def critique_hypothesis(
        self, hypothesis: str, evidence: List[str]
    ) -> Tuple[bool, str]:
        """
        Returns (passed_review: bool, critique_notes: str)
        """
        if not self.client:
            return True, "No reviewer agent available (skipped)."

        prompt = f"""Act as a skeptical senior scientist conducting a peer review.
        
        Hypothesis: "{hypothesis}"
        
        Evidence Provided:
        {json.dumps(evidence, indent=2)}
        
        Task:
        1. Identify logical gaps or potential hallucinations.
        2. Are the linked entities actually related in the way claimed?
        3. Is this "novelty" just a spurious connection?
        
        Return a JSON object:
        {{
            "verdict": "PASS" or "FAIL",
            "critique": "Short explanation of the flaw or strength",
            "confidence": 0.0 to 1.0
        }}
        """

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            # Simple parsing (robustness improvement needed in prod)
            # Extract JSON from potential wrapper text
            json_str = content
            if "{" in content:
                json_str = content[content.find("{") : content.rfind("}") + 1]

            result = json.loads(json_str)
            return result.get("verdict") == "PASS", result.get("critique", "")

        except Exception as e:
            logger.error(f"Adversarial review failed: {e}")
            return True, "Review failed (default pass)"


class NeuroSymbolicLoop:
    """
    Agentic Discovery Loop (The 'Deep Think' Insight).
    Iteratively refines queries and rankings to saturate reasoning.
    """

    def __init__(
        self,
        ranker: RobustRanker,
        reviewer: AdversarialReviewer,
        client: Optional[Any] = None,
    ):
        self.ranker = ranker
        self.reviewer = reviewer
        self.booster = CrossDomainBooster()
        self.client = client or ranker.client

    async def llm_reflect(
        self,
        current_results: Dict[str, float],
        context_history: List[Any],
        graph: nx.DiGraph,
    ) -> Tuple[str, str]:
        """
        Reflect on current graph activations and decide the next query step.
        """
        if not self.client:
            return "", "No LLM"

        # Get top nodes to show to LLM
        top_nodes = sorted(current_results.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]
        top_node_labels = []
        for nid, score in top_nodes:
            label = graph.nodes[nid].get("label", str(nid))
            top_node_labels.append(f"{label} ({score:.2f})")

        prompt = f"""You are driving a scientific discovery process.
        
        Current Iteration Top Results:
        {", ".join(top_node_labels)}
        
        Previous Queries: {[c[0] for c in context_history]}
        
        Task:
        1. Analyze the connections. Are we missing a mechanism?
        2. Formulate the NEXT search query to verify or expand the most promising hypothesis.
        3. If we have sufficient evidence, output "TERMINATE".
        
        Output format: JSON {{ "next_query": "...", "rationale": "..." }}
        """

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            json_str = content[content.find("{") : content.rfind("}") + 1]
            result = json.loads(json_str)
            return result.get("next_query", "TERMINATE"), result.get("rationale", "")
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return "TERMINATE", "Error"

    async def run_deep_think_stream(
        self, graph: nx.DiGraph, initial_query: str, max_steps: int = 3
    ):
        """
        Execute the Deep Think loop and yield status updates.
        This is an async generator.
        """
        context = []
        current_query = initial_query

        # Keep track of cumulative activations
        cumulative_activations = {}

        for step in range(max_steps):
            logger.info(f"Deep Think Step {step + 1}: {current_query}")

            yield {
                "type": "step_start",
                "step": step + 1,
                "query": current_query,
                "message": f"Deep Think Cycle {step + 1}: Investigating '{current_query}'",
            }

            # 1. Execute Robust Ranking
            yield {
                "type": "status",
                "message": f"Step {step + 1}: Robustified Ranking (Ensemble)...",
            }
            results = await self.ranker.rank_robust(graph, current_query)

            # 2. Cross-Domain Boosting
            yield {
                "type": "status",
                "message": f"Step {step + 1}: Cross-Domain Boosting...",
            }
            results = self.booster.boost(graph, results)

            # Merge into cumulative (simple max or sum)
            for n, s in results.items():
                cumulative_activations[n] = max(cumulative_activations.get(n, 0), s)

            # 3. Agentic Reflection
            yield {
                "type": "status",
                "message": f"Step {step + 1}: Reflecting on findings...",
            }
            next_query, rationale = await self.llm_reflect(results, context, graph)

            context.append(
                {
                    "query": current_query,
                    "top_nodes": list(results.keys())[:5],
                    "rationale": rationale,
                }
            )

            if next_query == "TERMINATE" or not next_query:
                yield {
                    "type": "status",
                    "message": "Reasoning saturated. Terminating loop.",
                }
                break

            current_query = next_query

        yield {
            "type": "result",
            "data": {"activations": cumulative_activations, "trace": context},
        }

    async def run_deep_think(
        self, graph: nx.DiGraph, initial_query: str, max_steps: int = 3
    ) -> Dict[str, Any]:
        """
        Execute the Deep Think loop (non-streaming wrapper).
        """
        result = None
        async for event in self.run_deep_think_stream(graph, initial_query, max_steps):
            if event["type"] == "result":
                result = event["data"]
        return result or {"activations": {}, "trace": []}
