import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import seaborn as sns

# Set style for "Saloni's Guidelines" (Minimalist, Grey Backgrounds, Direct Labeling)
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.facecolor"] = "#f4f4f4"  # Soft grey background
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.color"] = "white"
plt.rcParams["grid.linewidth"] = 1.5
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["axes.prop_cycle"] = plt.cycler(
    color=["#3b82f6", "#ef4444", "#10b981", "#8b5cf6"]
)  # Tailwind colors


def generate_performance_chart():
    """Generates Figure 2: Performance Comparison"""
    categories = ["Novelty Score", "Validity Score", "User Satisfaction"]
    onco_ttt = [0.85, 0.92, 0.88]
    gpt4 = [0.60, 0.75, 0.65]
    static_rag = [0.55, 0.80, 0.60]

    x = np.arange(len(categories))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    rects1 = ax.bar(x - width, onco_ttt, width, label="Onco-TTT", color="#3b82f6")
    rects2 = ax.bar(x, gpt4, width, label="GPT-4 Baseline", color="#9ca3af")
    rects3 = ax.bar(x + width, static_rag, width, label="Static RAG", color="#d1d5db")

    ax.set_ylabel("Score (0-1)")
    ax.set_title("Benchmarking Hypothesis Quality")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend(frameon=False)
    ax.set_ylim(0, 1.1)

    # Direct Labeling
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(
                f"{height:.2f}",
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color="#374151",
            )

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    plt.tight_layout()
    plt.savefig("docs_plans/fig_performance.png", dpi=300)
    print("Generated fig_performance.png")


def generate_graph_traversal():
    """Generates Figure 3: Knowledge Graph Traversal"""
    G = nx.DiGraph()
    # Central Query
    G.add_node("Query: KRAS", type="query", color="#1e293b")

    # Relevant Nodes (TTT Activated)
    relevant = ["YAP1", "STK11", "MAPK", "Resistance"]
    for n in relevant:
        G.add_node(n, type="relevant", color="#3b82f6")
        G.add_edge("Query: KRAS", n, weight=0.9, color="#cbd5e1")

    # Irrelevant Nodes (Filtered)
    irrelevant = ["TP53", "EGFR", "B-RAF"]
    for n in irrelevant:
        G.add_node(n, type="irrelevant", color="#e2e8f0")
        G.add_edge("Query: KRAS", n, weight=0.1, color="#f1f5f9")

    # Layout
    pos = nx.spring_layout(G, seed=42, k=0.5)

    plt.figure(figsize=(8, 6))
    ax = plt.gca()
    ax.set_facecolor("white")  # Graph usually looks better on white

    # Draw Edges
    weights = [G[u][v]["weight"] * 2 for u, v in G.edges()]
    edge_colors = [G[u][v]["color"] for u, v in G.edges()]
    nx.draw_networkx_edges(
        G, pos, width=weights, edge_color=edge_colors, alpha=0.8, arrows=True
    )

    # Draw Nodes
    node_colors = [nx.get_node_attributes(G, "color")[n] for n in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_size=1000, node_color=node_colors, alpha=1.0)

    # Labels
    nx.draw_networkx_labels(G, pos, font_size=8, font_color="white", font_weight="bold")

    plt.title("Adaptive Graph Traversal (TTT Focus)", fontsize=12, pad=20)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig("docs_plans/fig_graph.png", dpi=300)
    print("Generated fig_graph.png")


def generate_confidence_dist():
    """Generates Figure 4: Confidence Distribution (Small Multiples)"""
    cancer_types = ["Lung Adeno.", "Melanoma", "Colorectal", "Pancreatic"]

    fig, axes = plt.subplots(1, 4, figsize=(12, 3), sharey=True)
    fig.suptitle("Hypothesis Confidence Distribution by Cancer Type", y=1.05)

    for i, cancer in enumerate(cancer_types):
        # Generate synthetic bimodal data
        data = np.concatenate(
            [np.random.normal(0.3, 0.1, 30), np.random.normal(0.8, 0.1, 70)]
        )
        data = np.clip(data, 0, 1)

        ax = axes[i]
        sns.kdeplot(data, ax=ax, fill=True, color="#8b5cf6", alpha=0.2, linewidth=2)
        ax.set_title(cancer, fontsize=10)
        ax.set_xlabel("Confidence")
        if i == 0:
            ax.set_ylabel("Density")

        # Add mean line
        mean_val = np.mean(data)
        ax.axvline(mean_val, color="#ef4444", linestyle="--", alpha=0.5)
        ax.text(
            mean_val,
            0.5,
            f"μ={mean_val:.2f}",
            color="#ef4444",
            rotation=90,
            va="center",
            ha="right",
            fontsize=8,
        )

    plt.tight_layout()
    plt.savefig("docs_plans/fig_confidence.png", dpi=300)
    print("Generated fig_confidence.png")


if __name__ == "__main__":
    generate_performance_chart()
    generate_graph_traversal()
    generate_confidence_dist()
