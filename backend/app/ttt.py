from typing import List, Dict, Tuple
import networkx as nx


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
            node_lower = node.lower()
            for term in query_terms:
                if term in node_lower:
                    score += 1.0
            activations[node] = score

        # 2. Propagate activations through graph edges
        for step in range(self.steps):
            new_acts = {n: a * self.decay for n, a in activations.items()}
            for node in graph.nodes():
                if activations[node] > 0:
                    for neighbor in graph.neighbors(node):
                        edge_weight = graph[node][neighbor].get("weight", 0.5)
                        new_acts[neighbor] += (
                            activations[node] * edge_weight * self.learning_rate
                        )
                    # Also propagate backwards (undirected spreading)
                    for predecessor in graph.predecessors(node):
                        edge_weight = graph[predecessor][node].get("weight", 0.5)
                        new_acts[predecessor] += (
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
        self, activations: Dict[str, float], query: str, k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Find nodes with high activation but NO direct query term match.
        These represent non-obvious connections discovered via propagation.
        """
        query_terms = set(query.lower().split())
        novel = []
        for node, score in activations.items():
            if score > 0.1:
                node_lower = node.lower()
                if not any(term in node_lower for term in query_terms):
                    novel.append((node, score))
        novel.sort(key=lambda x: x[1], reverse=True)
        return novel[:k]


# Backward-compatible alias
TTTAdapter = QueryAdaptiveRanker
