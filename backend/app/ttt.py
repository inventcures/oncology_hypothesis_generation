from typing import List, Dict
import networkx as nx


class TTTAdapter:
    def __init__(self):
        self.learning_rate = 0.1
        self.steps = 5

    def adapt(self, graph: nx.DiGraph, query: str) -> List[str]:
        """
        Simulates Test-Time Training.
        1. Identifies 'support set' nodes from query terms.
        2. Propagates 'attention' (activations) through the graph to find hidden connections.
        3. Returns the top-k activated nodes (the 'adapted' focus area).
        """
        # 1. Self-Supervised Objective: Identify query terms in graph
        query_terms = query.lower().split()
        activated_nodes = {}

        # Initialize activations
        for node in graph.nodes():
            score = 0.0
            node_lower = node.lower()
            for term in query_terms:
                if term in node_lower:
                    score += 1.0  # Direct match
            activated_nodes[node] = score

        # 2. Gradient/Attention Propagation (Simulation of TTT updates)
        # We propagate activation to neighbors to "learn" the local context
        for step in range(self.steps):
            new_activations = activated_nodes.copy()
            for node in graph.nodes():
                if activated_nodes[node] > 0:
                    # Propagate to neighbors
                    for neighbor in graph.neighbors(node):
                        # Weight determines flow
                        edge_weight = graph[node][neighbor].get("weight", 0.5)
                        # Update neighbor activation (simulate gradient flow)
                        new_activations[neighbor] += (
                            activated_nodes[node] * edge_weight * self.learning_rate
                        )
            activated_nodes = new_activations

        # 3. Select top nodes (High novelty/relevance)
        # Sort by activation score
        sorted_nodes = sorted(activated_nodes.items(), key=lambda x: x[1], reverse=True)

        # Filter out zero activations
        relevant_nodes = [n for n, score in sorted_nodes if score > 0.1]

        return relevant_nodes[:10]  # Top 10 concepts
