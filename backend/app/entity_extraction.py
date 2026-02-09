"""
GLiNER2-Powered Oncology Entity Extraction

Uses GLiNER2 (fastino/gliner2-base-v1) for zero-shot biomedical NER,
relation extraction, and structured clinical data extraction.

Features:
- Singleton model caching (load once, reuse across requests)
- Oncology-specific entity schemas with descriptions for accuracy
- Combined entity + relation extraction in single pass
- Confidence scores + span positions on all extractions
- Extraction result caching (LRU) for repeated/similar queries
"""

import hashlib
import threading
from typing import Dict, List, Any, Optional, Tuple
from collections import OrderedDict
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Oncology entity & relation schemas
# ---------------------------------------------------------------------------

# Entity labels with descriptions for higher accuracy on biomedical text
ONCOLOGY_ENTITY_SCHEMA = {
    "gene": "Human gene symbols such as KRAS, TP53, EGFR, BRAF, STK11, ALK, ROS1, MET",
    "disease": "Cancer types and diseases such as lung adenocarcinoma, melanoma, glioblastoma",
    "drug": "Therapeutic agents, inhibitors, antibodies such as sotorasib, pembrolizumab, osimertinib",
    "pathway": "Biological signaling pathways such as MAPK, PI3K-Akt, mTOR, Hippo, WNT, Notch",
    "mutation": "Genetic mutations such as G12C, V600E, T790M, L858R, exon 19 deletion",
    "cell_type": "Cell types such as T-cell, macrophage, fibroblast, epithelial cell, NK cell",
    "biomarker": "Biomarkers such as PD-L1 expression, TMB, MSI-H, HER2 status, BRCA1/2",
    "mechanism": "Biological mechanisms such as apoptosis, angiogenesis, immune evasion, EMT",
    "anatomical_site": "Body sites and organs such as lung, breast, colon, brain, liver, bone marrow",
    "clinical_outcome": "Treatment outcomes such as overall survival, progression-free survival, response rate",
}

# Relation types for knowledge graph edge creation
ONCOLOGY_RELATION_SCHEMA = {
    "targets": "A drug targets or inhibits a gene/protein",
    "associated_with": "A gene is associated with a disease or phenotype",
    "mutated_in": "A mutation occurs in a specific gene",
    "participates_in": "A gene participates in a signaling pathway",
    "expressed_in": "A gene or protein is expressed in a cell type or tissue",
    "resistant_to": "A gene mutation confers resistance to a drug",
    "biomarker_for": "A biomarker predicts response to a disease or treatment",
    "drives": "A gene or mutation drives a disease or mechanism",
    "inhibits": "A drug or mechanism inhibits a pathway or process",
    "synergizes_with": "A drug or gene synergizes with another for therapeutic effect",
}

# Structured extraction schema for clinical context
CLINICAL_EXTRACTION_SCHEMA = {
    "clinical_context": [
        "cancer_type::str::Specific cancer type or subtype",
        "stage::str::Cancer stage (I, II, III, IV) or early/advanced",
        "treatment_line::str::Line of therapy (first-line, second-line, adjuvant)",
        "molecular_subtype::str::Molecular subtype or classification",
    ]
}


# ---------------------------------------------------------------------------
# Extraction result caching
# ---------------------------------------------------------------------------


@dataclass
class ExtractionCacheEntry:
    """Cache entry for extraction results with TTL."""

    result: Dict[str, Any]
    timestamp: float
    ttl: float = 1800.0  # 30 min default

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl


class ExtractionCache:
    """Thread-safe LRU cache for extraction results."""

    def __init__(self, max_size: int = 500):
        self.cache: OrderedDict[str, ExtractionCacheEntry] = OrderedDict()
        self.max_size = max_size
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _make_key(self, text: str, mode: str) -> str:
        normalized = text.strip().lower()
        return f"{mode}:{hashlib.sha256(normalized.encode()).hexdigest()}"

    def get(self, text: str, mode: str) -> Optional[Dict[str, Any]]:
        key = self._make_key(text, mode)
        with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired:
                    self.cache.move_to_end(key)
                    self.hits += 1
                    return entry.result
                else:
                    del self.cache[key]
            self.misses += 1
            return None

    def set(self, text: str, mode: str, result: Dict[str, Any]):
        key = self._make_key(text, mode)
        with self._lock:
            self.cache[key] = ExtractionCacheEntry(result=result, timestamp=time.time())
            self.cache.move_to_end(key)
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total > 0 else 0,
            "size": len(self.cache),
            "max_size": self.max_size,
        }


# ---------------------------------------------------------------------------
# GLiNER2 singleton loader
# ---------------------------------------------------------------------------


class _GLiNER2Singleton:
    """
    Thread-safe singleton that loads the GLiNER2 model exactly once.
    Subsequent calls to .get() return the cached instance.
    """

    _instance: Optional[Any] = None
    _lock = threading.Lock()
    _model_name = "fastino/gliner2-base-v1"
    _load_time: Optional[float] = None

    @classmethod
    def get(cls) -> Any:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # double-check
                    logger.info(
                        "Loading GLiNER2 model '%s' (first request)...",
                        cls._model_name,
                    )
                    t0 = time.time()
                    from gliner2 import GLiNER2

                    cls._instance = GLiNER2.from_pretrained(cls._model_name)
                    cls._load_time = time.time() - t0
                    logger.info("GLiNER2 model loaded in %.2fs", cls._load_time)
        return cls._instance

    @classmethod
    def load_time(cls) -> Optional[float]:
        return cls._load_time

    @classmethod
    def is_loaded(cls) -> bool:
        return cls._instance is not None


def get_model():
    """Public accessor for the cached GLiNER2 model."""
    return _GLiNER2Singleton.get()


# ---------------------------------------------------------------------------
# Entity extractor class
# ---------------------------------------------------------------------------


class OncologyEntityExtractor:
    """
    High-level extractor that wraps GLiNER2 for oncology-specific
    entity extraction, relation extraction, and structured parsing.
    """

    def __init__(self):
        self._cache = ExtractionCache(max_size=500)

    # ------------------------------------------------------------------
    # Core: entity extraction
    # ------------------------------------------------------------------

    def extract_entities(
        self,
        text: str,
        entity_labels: Optional[Dict[str, str]] = None,
        threshold: float = 0.4,
        include_confidence: bool = True,
        include_spans: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract oncology entities from text using GLiNER2.

        Returns dict with structure:
        {
            "entities": {
                "gene": [{"text": "KRAS", "confidence": 0.95, "start": 0, "end": 4}],
                ...
            },
            "meta": {"model": ..., "threshold": ..., "extraction_time_ms": ...}
        }
        """
        cached = self._cache.get(text, "entities")
        if cached is not None:
            cached["meta"]["from_cache"] = True
            return cached

        labels = entity_labels or ONCOLOGY_ENTITY_SCHEMA
        model = get_model()

        t0 = time.time()
        result = model.extract_entities(
            text,
            labels,
            threshold=threshold,
            include_confidence=include_confidence,
            include_spans=include_spans,
        )
        elapsed = (time.time() - t0) * 1000

        output = {
            "entities": result.get("entities", {}),
            "meta": {
                "model": _GLiNER2Singleton._model_name,
                "threshold": threshold,
                "extraction_time_ms": round(elapsed, 1),
                "entity_count": sum(
                    len(v) for v in result.get("entities", {}).values()
                ),
                "from_cache": False,
            },
        }

        self._cache.set(text, "entities", output)
        return output

    # ------------------------------------------------------------------
    # Core: relation extraction
    # ------------------------------------------------------------------

    def extract_relations(
        self,
        text: str,
        relation_labels: Optional[Dict[str, str]] = None,
        include_confidence: bool = True,
        include_spans: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract oncology relations (gene->disease, drug->target, etc.)

        Returns dict with structure:
        {
            "relations": {
                "targets": [{"head": {...}, "tail": {...}}],
                ...
            },
            "meta": {...}
        }
        """
        cached = self._cache.get(text, "relations")
        if cached is not None:
            cached["meta"]["from_cache"] = True
            return cached

        labels = relation_labels or ONCOLOGY_RELATION_SCHEMA
        model = get_model()

        t0 = time.time()
        result = model.extract_relations(
            text,
            labels,
            include_confidence=include_confidence,
            include_spans=include_spans,
        )
        elapsed = (time.time() - t0) * 1000

        relations = result.get("relation_extraction", {})
        total_rels = sum(len(v) for v in relations.values())

        output = {
            "relations": relations,
            "meta": {
                "model": _GLiNER2Singleton._model_name,
                "extraction_time_ms": round(elapsed, 1),
                "relation_count": total_rels,
                "from_cache": False,
            },
        }

        self._cache.set(text, "relations", output)
        return output

    # ------------------------------------------------------------------
    # Combined: entities + relations + classification in one pass
    # ------------------------------------------------------------------

    def extract_all(
        self,
        text: str,
        entity_labels: Optional[Dict[str, str]] = None,
        relation_labels: Optional[Dict[str, str]] = None,
        include_confidence: bool = True,
        include_spans: bool = True,
    ) -> Dict[str, Any]:
        """
        Full extraction pipeline: entities, relations, and clinical context
        using GLiNER2's multi-task schema composition.

        This is the primary method used by the KG builder.
        """
        cached = self._cache.get(text, "all")
        if cached is not None:
            cached["meta"]["from_cache"] = True
            return cached

        e_labels = entity_labels or ONCOLOGY_ENTITY_SCHEMA
        r_labels = relation_labels or ONCOLOGY_RELATION_SCHEMA
        model = get_model()

        t0 = time.time()

        # Build a combined multi-task schema
        schema = (
            model.create_schema()
            .entities(e_labels)
            .relations(r_labels)
            .classification(
                "research_focus",
                [
                    "drug_resistance",
                    "target_discovery",
                    "biomarker_identification",
                    "combination_therapy",
                    "immunotherapy",
                    "precision_medicine",
                    "tumor_microenvironment",
                    "mechanistic_study",
                ],
                multi_label=True,
                cls_threshold=0.3,
            )
        )

        result = model.extract(
            text,
            schema,
            include_confidence=include_confidence,
            include_spans=include_spans,
        )
        elapsed = (time.time() - t0) * 1000

        entities = result.get("entities", {})
        relations = result.get("relation_extraction", {})
        classification = result.get("research_focus", [])

        total_entities = sum(len(v) for v in entities.values())
        total_relations = sum(len(v) for v in relations.values())

        output = {
            "entities": entities,
            "relations": relations,
            "research_focus": classification,
            "meta": {
                "model": _GLiNER2Singleton._model_name,
                "extraction_time_ms": round(elapsed, 1),
                "entity_count": total_entities,
                "relation_count": total_relations,
                "from_cache": False,
            },
        }

        self._cache.set(text, "all", output)
        return output

    # ------------------------------------------------------------------
    # Structured clinical data extraction
    # ------------------------------------------------------------------

    def extract_clinical_context(self, text: str) -> Dict[str, Any]:
        """Extract structured clinical context (cancer type, stage, etc.)."""
        cached = self._cache.get(text, "clinical")
        if cached is not None:
            return cached

        model = get_model()
        t0 = time.time()
        result = model.extract_json(text, CLINICAL_EXTRACTION_SCHEMA)
        elapsed = (time.time() - t0) * 1000

        output = {
            "clinical_context": result.get("clinical_context", []),
            "meta": {"extraction_time_ms": round(elapsed, 1)},
        }

        self._cache.set(text, "clinical", output)
        return output

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def cache_stats(self) -> Dict[str, Any]:
        return self._cache.stats()

    @staticmethod
    def model_info() -> Dict[str, Any]:
        return {
            "model_name": _GLiNER2Singleton._model_name,
            "is_loaded": _GLiNER2Singleton.is_loaded(),
            "load_time_seconds": _GLiNER2Singleton.load_time(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton instance
# ---------------------------------------------------------------------------

_extractor_instance: Optional[OncologyEntityExtractor] = None
_extractor_lock = threading.Lock()


def get_extractor() -> OncologyEntityExtractor:
    """Return a module-level singleton extractor."""
    global _extractor_instance
    if _extractor_instance is None:
        with _extractor_lock:
            if _extractor_instance is None:
                _extractor_instance = OncologyEntityExtractor()
    return _extractor_instance
