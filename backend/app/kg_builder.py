"""
Rich Knowledge Graph Builder

Consumes GLiNER2 extraction output and builds a richly annotated
NetworkX graph with:
  - Color-coded nodes by entity type
  - Interactive edge metadata (relation label, confidence, direction)
  - Edge thickness proportional to confidence weight
  - Node importance scoring (degree centrality + confidence)
  - Cluster grouping for visual layout
  - Full serialisation to JSON with rendering hints for the frontend

Also merges OpenTargets API associations into the same graph so the
frontend renders a single, unified, richly-styled KG.
"""

import json
import networkx as nx
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

_DATA_DIR = Path(__file__).parent / "data"

def _load_pathway_data() -> Dict[str, Any]:
    path = _DATA_DIR / "pathways.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"gene_pathways": {}, "gene_cell_types": {}, "signaling_cascades": {}}

_PATHWAY_DATA = _load_pathway_data()

# ---------------------------------------------------------------------------
# Visual style constants
# ---------------------------------------------------------------------------

# Color palette for node types (hex)  -- also sent to frontend
NODE_COLORS: Dict[str, str] = {
    "gene": "#3b82f6",  # blue-500
    "disease": "#ef4444",  # red-500
    "drug": "#10b981",  # emerald-500
    "pathway": "#8b5cf6",  # violet-500
    "mutation": "#f59e0b",  # amber-500
    "cell_type": "#06b6d4",  # cyan-500
    "biomarker": "#ec4899",  # pink-500
    "mechanism": "#6366f1",  # indigo-500
    "anatomical_site": "#84cc16",  # lime-500
    "clinical_outcome": "#14b8a6",  # teal-500
    # fallbacks for OpenTargets types that arrive as capitalised
    "Gene": "#3b82f6",
    "Disease": "#ef4444",
    "Drug": "#10b981",
    "Pathway": "#8b5cf6",
    "CellType": "#06b6d4",
}

NODE_BORDER_COLORS: Dict[str, str] = {
    "gene": "#2563eb",
    "disease": "#dc2626",
    "drug": "#059669",
    "pathway": "#7c3aed",
    "mutation": "#d97706",
    "cell_type": "#0891b2",
    "biomarker": "#db2777",
    "mechanism": "#4f46e5",
    "anatomical_site": "#65a30d",
    "clinical_outcome": "#0d9488",
}

# Edge colours keyed by relation type
EDGE_COLORS: Dict[str, str] = {
    "targets": "#10b981",
    "associated_with": "#6366f1",
    "mutated_in": "#f59e0b",
    "participates_in": "#8b5cf6",
    "expressed_in": "#06b6d4",
    "resistant_to": "#ef4444",
    "biomarker_for": "#ec4899",
    "drives": "#f97316",
    "inhibits": "#64748b",
    "synergizes_with": "#22c55e",
    "driver": "#f97316",
}

# Human-readable labels for relation types
EDGE_LABELS: Dict[str, str] = {
    "targets": "targets",
    "associated_with": "assoc.",
    "mutated_in": "mutated in",
    "participates_in": "in pathway",
    "expressed_in": "expressed in",
    "resistant_to": "resistant to",
    "biomarker_for": "biomarker for",
    "drives": "drives",
    "inhibits": "inhibits",
    "synergizes_with": "synergy",
    "driver": "driver",
}

# Node radius scaling
BASE_RADIUS = 22
MAX_RADIUS = 38


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_type(raw: str) -> str:
    """Normalise entity types to lowercase singular form."""
    mapping = {
        "Gene": "gene",
        "Disease": "disease",
        "Drug": "drug",
        "Pathway": "pathway",
        "CellType": "cell_type",
        "Mutation": "mutation",
        "Biomarker": "biomarker",
        "Mechanism": "mechanism",
    }
    return mapping.get(raw, raw.lower().replace(" ", "_"))


def entity_text(item: Any) -> str:
    """Extract text string from various GLiNER2 output formats."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("text", str(item))
    return str(item)



def _entity_confidence(item: Any) -> float:
    """Extract confidence float from various GLiNER2 output formats."""
    if isinstance(item, dict):
        return item.get("confidence", 0.7)
    return 0.7  # default when only text is returned


# ---------------------------------------------------------------------------
# KG builder
# ---------------------------------------------------------------------------


class KnowledgeGraphBuilder:
    """
    Builds a rich, frontend-ready knowledge graph from GLiNER2
    extraction results, optionally merging OpenTargets associations.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Ingest GLiNER2 entities
    # ------------------------------------------------------------------

    def add_entities(self, entities: Dict[str, List[Any]]) -> int:
        """
        Add entities extracted by GLiNER2 to the graph.

        Args:
            entities: {type: [items]} where items are str or
                      {"text": ..., "confidence": ..., "start": ..., "end": ...}

        Returns:
            Number of nodes added.
        """
        added = 0
        for entity_type, items in entities.items():
            norm_type = _normalise_type(entity_type)
            for item in items:
                text = entity_text(item)
                conf = _entity_confidence(item)
                node_id = text  # use raw text as node id

                if self.graph.has_node(node_id):
                    # merge: keep highest confidence
                    existing_conf = self.graph.nodes[node_id].get("confidence", 0)
                    if conf > existing_conf:
                        self.graph.nodes[node_id]["confidence"] = conf
                else:
                    self.graph.add_node(
                        node_id,
                        type=norm_type,
                        label=text,
                        confidence=conf,
                        color=NODE_COLORS.get(norm_type, "#9ca3af"),
                        border_color=NODE_BORDER_COLORS.get(norm_type, "#6b7280"),
                        source="gliner2",
                    )
                    added += 1
        return added

    # ------------------------------------------------------------------
    # Ingest GLiNER2 relations
    # ------------------------------------------------------------------

    def add_relations(self, relations: Dict[str, List[Any]]) -> int:
        """
        Add relations extracted by GLiNER2 to the graph as directed edges.

        Args:
            relations: {rel_type: [tuples or dicts]}

        Returns:
            Number of edges added.
        """
        added = 0
        for rel_type, items in relations.items():
            edge_color = EDGE_COLORS.get(rel_type, "#94a3b8")
            edge_label = EDGE_LABELS.get(rel_type, rel_type.replace("_", " "))
            for item in items:
                head, tail, h_conf, t_conf = self._parse_relation_item(item)
                if not head or not tail:
                    continue

                avg_conf = (h_conf + t_conf) / 2.0

                # Ensure both nodes exist
                self._ensure_node(head)
                self._ensure_node(tail)

                # Add edge (or update if stronger)
                if self.graph.has_edge(head, tail):
                    existing = self.graph[head][tail].get("weight", 0)
                    if avg_conf > existing:
                        self.graph[head][tail]["weight"] = avg_conf
                        self.graph[head][tail]["relation"] = rel_type
                else:
                    self.graph.add_edge(
                        head,
                        tail,
                        weight=round(avg_conf, 3),
                        relation=rel_type,
                        label=edge_label,
                        color=edge_color,
                        source="gliner2",
                    )
                    added += 1
        return added

    # ------------------------------------------------------------------
    # Ingest OpenTargets associations (merge into same graph)
    # ------------------------------------------------------------------

    def add_opentargets_associations(
        self,
        seed_name: str,
        seed_type: str,
        neighbors: List[Dict[str, Any]],
    ):
        """Merge OpenTargets 1-hop associations into the graph."""
        norm_seed = _normalise_type(seed_type)
        if not self.graph.has_node(seed_name):
            self.graph.add_node(
                seed_name,
                type=norm_seed,
                label=seed_name,
                confidence=1.0,
                color=NODE_COLORS.get(norm_seed, "#9ca3af"),
                border_color=NODE_BORDER_COLORS.get(norm_seed, "#6b7280"),
                source="opentargets",
            )

        for n in neighbors:
            nid = n["id"]
            ntype = _normalise_type(n.get("type", "gene"))
            score = n.get("score", 0.5)

            if not self.graph.has_node(nid):
                self.graph.add_node(
                    nid,
                    type=ntype,
                    label=nid,
                    confidence=score,
                    color=NODE_COLORS.get(ntype, "#9ca3af"),
                    border_color=NODE_BORDER_COLORS.get(ntype, "#6b7280"),
                    source="opentargets",
                )

            if not self.graph.has_edge(seed_name, nid):
                rel = n.get("relation", "associated_with")
                self.graph.add_edge(
                    seed_name,
                    nid,
                    weight=round(score, 3),
                    relation=rel,
                    label=EDGE_LABELS.get(rel, rel),
                    color=EDGE_COLORS.get(rel, "#94a3b8"),
                    source="opentargets",
                )

    # ------------------------------------------------------------------
    # Add hard-coded pathway / cell-type enrichment (existing ark.py logic)
    # ------------------------------------------------------------------

    def add_pathway_enrichment(self, seed_gene: str):
        """
        Add known pathway associations, upstream activators, and downstream
        effectors for the seed gene. Provides directional signaling context
        for the Pathway view.
        """
        pathways = _PATHWAY_DATA.get("gene_pathways", {})
        cell_types = _PATHWAY_DATA.get("gene_cell_types", {})

        signaling = _PATHWAY_DATA.get("signaling_cascades", {})

        # --- Add pathway nodes/edges ---
        for p_name in pathways.get(seed_gene, []):
            if not self.graph.has_node(p_name):
                self.graph.add_node(
                    p_name,
                    type="pathway",
                    label=p_name,
                    confidence=0.85,
                    color=NODE_COLORS["pathway"],
                    border_color=NODE_BORDER_COLORS.get("pathway", "#6b7280"),
                    source="curated",
                )
            if not self.graph.has_edge(seed_gene, p_name):
                self.graph.add_edge(
                    seed_gene,
                    p_name,
                    weight=0.85,
                    relation="participates_in",
                    label="in pathway",
                    color=EDGE_COLORS["participates_in"],
                    source="curated",
                )

        # --- Add cell type nodes/edges ---
        for c_name in cell_types.get(seed_gene, []):
            if not self.graph.has_node(c_name):
                self.graph.add_node(
                    c_name,
                    type="cell_type",
                    label=c_name,
                    confidence=0.75,
                    color=NODE_COLORS["cell_type"],
                    border_color=NODE_BORDER_COLORS.get("cell_type", "#6b7280"),
                    source="curated",
                )
            if not self.graph.has_edge(seed_gene, c_name):
                self.graph.add_edge(
                    seed_gene,
                    c_name,
                    weight=0.75,
                    relation="expressed_in",
                    label="expressed in",
                    color=EDGE_COLORS["expressed_in"],
                    source="curated",
                )

        # --- Add upstream/downstream signaling nodes/edges ---
        sig = signaling.get(seed_gene, {})

        for activator, rel_label in sig.get("upstream", []):
            if not self.graph.has_node(activator):
                inferred_type = self._infer_type(activator)
                self.graph.add_node(
                    activator,
                    type=inferred_type,
                    label=activator,
                    confidence=0.8,
                    color=NODE_COLORS.get(inferred_type, "#9ca3af"),
                    border_color=NODE_BORDER_COLORS.get(inferred_type, "#6b7280"),
                    source="curated",
                    signal_role="upstream",
                )
            else:
                self.graph.nodes[activator]["signal_role"] = "upstream"

            if not self.graph.has_edge(activator, seed_gene):
                is_inhibitor = (
                    "inhibit" in rel_label.lower() or "repress" in rel_label.lower()
                )
                self.graph.add_edge(
                    activator,
                    seed_gene,
                    weight=0.8,
                    relation=rel_label,
                    label=rel_label,
                    color="#ef4444" if is_inhibitor else "#22c55e",
                    source="curated",
                    signal_direction="upstream",
                )

        for effector, rel_label in sig.get("downstream", []):
            if not self.graph.has_node(effector):
                inferred_type = self._infer_type(effector)
                self.graph.add_node(
                    effector,
                    type=inferred_type,
                    label=effector,
                    confidence=0.8,
                    color=NODE_COLORS.get(inferred_type, "#9ca3af"),
                    border_color=NODE_BORDER_COLORS.get(inferred_type, "#6b7280"),
                    source="curated",
                    signal_role="downstream",
                )
            else:
                self.graph.nodes[effector]["signal_role"] = "downstream"

            if not self.graph.has_edge(seed_gene, effector):
                is_inhibitor = (
                    "inhibit" in rel_label.lower() or "repress" in rel_label.lower()
                )
                self.graph.add_edge(
                    seed_gene,
                    effector,
                    weight=0.8,
                    relation=rel_label,
                    label=rel_label,
                    color="#ef4444" if is_inhibitor else "#22c55e",
                    source="curated",
                    signal_direction="downstream",
                )

        # Mark the seed gene itself
        if self.graph.has_node(seed_gene):
            self.graph.nodes[seed_gene]["signal_role"] = "target"

    # ------------------------------------------------------------------
    # Layout + serialisation
    # ------------------------------------------------------------------

    def compute_layout(
        self,
        width: float = 800,
        height: float = 600,
        padding: float = 60,
    ) -> Dict[str, Tuple[float, float]]:
        """
        Compute spring layout positions and return as {node_id: (x, y)}.
        Caches result based on graph fingerprint to avoid recomputation.
        """
        if self.graph.number_of_nodes() == 0:
            return {}

        cache_key = (
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
            width,
            height,
        )
        if hasattr(self, "_layout_cache") and self._layout_cache_key == cache_key:
            return self._layout_cache

        pos = nx.spring_layout(
            self.graph,
            seed=42,
            k=2.5 / math.sqrt(max(self.graph.number_of_nodes(), 1)),
            iterations=80,
        )

        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_range = x_max - x_min or 1
        y_range = y_max - y_min or 1

        scaled = {}
        for nid, (x, y) in pos.items():
            sx = padding + ((x - x_min) / x_range) * (width - 2 * padding)
            sy = padding + ((y - y_min) / y_range) * (height - 2 * padding)
            scaled[nid] = (round(sx, 1), round(sy, 1))

        self._layout_cache = scaled
        self._layout_cache_key = cache_key

        return scaled

    def serialise(
        self,
        width: float = 800,
        height: float = 600,
    ) -> Dict[str, Any]:
        """
        Serialise the graph to a rich JSON structure for the frontend.

        Returns:
        {
            "nodes": [{
                "id", "type", "label", "color", "border_color",
                "confidence", "radius", "x", "y", "degree",
                "source", "glow"
            }],
            "links": [{
                "source", "target", "relation", "label", "weight",
                "color", "thickness", "source_data", "animated"
            }],
            "stats": {
                "total_nodes", "total_edges", "entity_types",
                "relation_types", "sources"
            },
            "legend": [{
                "type", "color", "count", "label"
            }]
        }
        """
        if self.graph.number_of_nodes() == 0:
            return {
                "nodes": [],
                "links": [],
                "stats": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "entity_types": {},
                    "relation_types": {},
                    "sources": {},
                },
                "legend": [],
            }

        pos = self.compute_layout(width, height)
        centrality = nx.degree_centrality(self.graph)

        # --- Nodes ---
        nodes = []
        type_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}

        for nid, attrs in self.graph.nodes(data=True):
            ntype = attrs.get("type", "unknown")
            nsource = attrs.get("source", "unknown")
            conf = attrs.get("confidence", 0.5)
            cent = centrality.get(nid, 0)

            type_counts[ntype] = type_counts.get(ntype, 0) + 1
            source_counts[nsource] = source_counts.get(nsource, 0) + 1

            # Scale radius by importance (centrality + confidence)
            importance = 0.4 * cent + 0.6 * conf
            radius = BASE_RADIUS + (MAX_RADIUS - BASE_RADIUS) * importance

            x, y = pos.get(nid, (400, 300))

            node_data = {
                "id": nid,
                "type": ntype,
                "label": attrs.get("label", nid),
                "color": attrs.get("color", "#9ca3af"),
                "border_color": attrs.get("border_color", "#6b7280"),
                "confidence": round(conf, 3),
                "radius": round(radius, 1),
                "x": x,
                "y": y,
                "degree": self.graph.degree(nid),
                "source": nsource,
                "glow": conf > 0.8,  # high confidence nodes glow
            }
            # Include signaling role if present (upstream/downstream/target)
            signal_role = attrs.get("signal_role")
            if signal_role:
                node_data["signal_role"] = signal_role
            nodes.append(node_data)

        # --- Edges ---
        links = []
        rel_counts: Dict[str, int] = {}

        for src, tgt, attrs in self.graph.edges(data=True):
            rel = attrs.get("relation", "associated_with")
            rel_counts[rel] = rel_counts.get(rel, 0) + 1

            weight = attrs.get("weight", 0.5)
            # thickness: 1px at 0.0 -> 5px at 1.0
            thickness = 1.0 + weight * 4.0

            link_data = {
                "source": src,
                "target": tgt,
                "relation": rel,
                "label": attrs.get("label", rel.replace("_", " ")),
                "weight": round(weight, 3),
                "color": attrs.get("color", "#94a3b8"),
                "thickness": round(thickness, 1),
                "source_data": attrs.get("source", "unknown"),
                "animated": weight > 0.8,  # high-confidence edges pulse
            }
            # Include signal direction if present
            sig_dir = attrs.get("signal_direction")
            if sig_dir:
                link_data["signal_direction"] = sig_dir
            links.append(link_data)

        # --- Legend ---
        legend = []
        type_display = {
            "gene": "Gene / Target",
            "disease": "Disease",
            "drug": "Drug / Compound",
            "pathway": "Signaling Pathway",
            "mutation": "Mutation",
            "cell_type": "Cell Type",
            "biomarker": "Biomarker",
            "mechanism": "Mechanism",
            "anatomical_site": "Anatomical Site",
            "clinical_outcome": "Clinical Outcome",
        }
        for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            legend.append(
                {
                    "type": t,
                    "color": NODE_COLORS.get(t, "#9ca3af"),
                    "count": count,
                    "label": type_display.get(t, t.replace("_", " ").title()),
                }
            )

        # --- Stats ---
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "entity_types": type_counts,
            "relation_types": rel_counts,
            "sources": source_counts,
        }

        return {
            "nodes": nodes,
            "links": links,
            "stats": stats,
            "legend": legend,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_node(self, name: str):
        """Add a node if it doesn't exist yet (infer type from name patterns)."""
        if self.graph.has_node(name):
            return
        inferred = self._infer_type(name)
        self.graph.add_node(
            name,
            type=inferred,
            label=name,
            confidence=0.5,
            color=NODE_COLORS.get(inferred, "#9ca3af"),
            border_color=NODE_BORDER_COLORS.get(inferred, "#6b7280"),
            source="inferred",
        )

    @staticmethod
    def _infer_type(name: str) -> str:
        """Best-effort type inference from entity name."""
        upper = name.upper()
        # Gene-like: all-caps, 2-6 chars, possibly with digits
        if name.isupper() and 2 <= len(name) <= 8 and any(c.isalpha() for c in name):
            return "gene"
        # Mutation-like: letter-digit-letter pattern
        if len(name) <= 10 and any(c.isdigit() for c in name) and name[0].isalpha():
            return "mutation"
        # Disease keywords
        disease_kw = [
            "cancer",
            "carcinoma",
            "adenocarcinoma",
            "melanoma",
            "lymphoma",
            "leukemia",
            "sarcoma",
            "glioma",
            "tumor",
        ]
        if any(kw in name.lower() for kw in disease_kw):
            return "disease"
        # Pathway keywords
        pathway_kw = ["signaling", "pathway", "cascade", "transduction"]
        if any(kw in name.lower() for kw in pathway_kw):
            return "pathway"
        # Drug keywords
        drug_suffixes = ["ib", "ab", "mab", "nib", "lib", "sib", "zumab"]
        if any(name.lower().endswith(s) for s in drug_suffixes):
            return "drug"
        return "mechanism"

    @staticmethod
    def _parse_relation_item(item: Any) -> Tuple[str, str, float, float]:
        """
        Parse a relation item from GLiNER2 output.

        Handles both tuple format: ('head', 'tail')
        and dict format: {'head': {...}, 'tail': {...}}
        """
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            return str(item[0]), str(item[1]), 0.7, 0.7

        if isinstance(item, dict):
            head_raw = item.get("head", {})
            tail_raw = item.get("tail", {})

            if isinstance(head_raw, str):
                h_text, h_conf = head_raw, 0.7
            else:
                h_text = head_raw.get("text", "")
                h_conf = head_raw.get("confidence", 0.7)

            if isinstance(tail_raw, str):
                t_text, t_conf = tail_raw, 0.7
            else:
                t_text = tail_raw.get("text", "")
                t_conf = tail_raw.get("confidence", 0.7)

            return h_text, t_text, h_conf, t_conf

        return "", "", 0, 0
