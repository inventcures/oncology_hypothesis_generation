"""
Clinical Trials module — dedicated ClinicalTrials.gov v2 API client.

Provides richer trial data than the validation module's check_competition,
including interventions, locations, enrollment, outcomes, and aggregated
summary statistics (phase distribution, sponsor breakdown, year timeline).
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ClinicalTrials.gov v2 API constants
# ---------------------------------------------------------------------------
CT_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

CT_FIELDS = ",".join(
    [
        "NCTId",
        "BriefTitle",
        "OfficialTitle",
        "OverallStatus",
        "Phase",
        "StartDate",
        "PrimaryCompletionDate",
        "LeadSponsorName",
        "Condition",
        "InterventionName",
        "InterventionType",
        "EnrollmentInfo",
        "BriefSummary",
        "LocationCity",
        "LocationState",
        "LocationCountry",
        "PrimaryOutcomeMeasure",
        "StudyType",
    ]
)

STATUS_MAP = {
    "RECRUITING": "RECRUITING,ENROLLING_BY_INVITATION,NOT_YET_RECRUITING",
    "ACTIVE": "RECRUITING,ACTIVE_NOT_RECRUITING",
    "COMPLETED": "COMPLETED",
}

PHASE_MAP = {
    "PHASE1": "EARLY_PHASE1,PHASE1",
    "PHASE2": "PHASE2",
    "PHASE3": "PHASE3",
    "PHASE4": "PHASE4",
}

PHASE_DISPLAY = {
    "EARLY_PHASE1": "Early Phase 1",
    "PHASE1": "Phase 1",
    "PHASE2": "Phase 2",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "N/A",
}

STATUS_DISPLAY = {
    "RECRUITING": "Recruiting",
    "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
    "COMPLETED": "Completed",
    "NOT_YET_RECRUITING": "Not yet recruiting",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "TERMINATED": "Terminated",
    "WITHDRAWN": "Withdrawn",
    "SUSPENDED": "Suspended",
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class ClinicalTrialsClient:
    """Async client for ClinicalTrials.gov v2 API with fallback data."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._external = client is not None
        self.client = client or httpx.AsyncClient(timeout=15.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def search_trials(
        self,
        gene: str,
        disease: str = "cancer",
        status: str = "ALL",
        phase: str = "ALL",
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Search ClinicalTrials.gov and return trials + summary stats."""
        params: Dict[str, Any] = {
            "format": "json",
            "countTotal": "true",
            "pageSize": min(page_size, 100),
            "sort": "LastUpdatePostDate:desc",
            "fields": CT_FIELDS,
        }

        if disease:
            params["query.cond"] = disease
        if gene:
            params["query.intr"] = gene

        status_upper = status.upper()
        if status_upper in STATUS_MAP:
            params["filter.overallStatus"] = STATUS_MAP[status_upper]

        phase_upper = phase.upper()
        if phase_upper in PHASE_MAP:
            params["filter.phase"] = PHASE_MAP[phase_upper]

        trials: List[Dict[str, Any]] = []
        total_count = 0
        source = "live"

        try:
            resp = await self.client.get(CT_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            total_count = data.get("totalCount", 0)
            trials = [self._parse_study(s) for s in data.get("studies", [])]
        except Exception as exc:
            logger.warning("ClinicalTrials.gov API error: %s", exc)
            fb = self._get_fallback(gene, disease)
            if fb:
                trials = fb
                total_count = len(fb)
                source = "fallback"

        summary = self._compute_summary(trials, total_count)

        return {
            "query": {
                "gene": gene,
                "disease": disease,
                "status_filter": status,
                "phase_filter": phase,
            },
            "summary": summary,
            "trials": trials,
            "source": source,
        }

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_study(s: Dict) -> Dict[str, Any]:
        proto = s.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
        desc = proto.get("descriptionModule", {})
        cond_mod = proto.get("conditionsModule", {})
        arms = proto.get("armsInterventionsModule", {})
        outcomes = proto.get("outcomesModule", {})
        contacts = proto.get("contactsLocationsModule", {})

        nct_id = ident.get("nctId", "")

        phases = design.get("phases", [])
        phase_raw = phases[0] if phases else "NA"
        phase = PHASE_DISPLAY.get(phase_raw, phase_raw)

        status_raw = status_mod.get("overallStatus", "")
        status = STATUS_DISPLAY.get(status_raw, status_raw)

        enrollment_info = design.get("enrollmentInfo", {})

        interventions_raw = arms.get("interventions", [])
        interventions = [
            {"name": iv.get("name", ""), "type": iv.get("type", "")}
            for iv in interventions_raw[:10]
        ]

        locations_raw = contacts.get("locations", [])
        locations = [
            {
                "city": loc.get("city", ""),
                "state": loc.get("state", ""),
                "country": loc.get("country", ""),
            }
            for loc in locations_raw[:5]
        ]

        primary_outcomes_raw = outcomes.get("primaryOutcomes", [])
        primary_outcomes = [o.get("measure", "") for o in primary_outcomes_raw[:3]]

        summary_text = desc.get("briefSummary", "")
        if len(summary_text) > 500:
            summary_text = summary_text[:497] + "..."

        return {
            "nct_id": nct_id,
            "title": ident.get("briefTitle", ""),
            "official_title": ident.get("officialTitle", ""),
            "status": status,
            "phase": phase,
            "sponsor": sponsor_mod.get("leadSponsor", {}).get("name", ""),
            "start_date": (status_mod.get("startDateStruct") or {}).get("date", ""),
            "completion_date": (
                status_mod.get("primaryCompletionDateStruct") or {}
            ).get("date", ""),
            "enrollment": enrollment_info.get("count", 0) or 0,
            "conditions": cond_mod.get("conditions", []),
            "interventions": interventions,
            "locations": locations,
            "primary_outcomes": primary_outcomes,
            "summary": summary_text,
            "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
        }

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_summary(trials: List[Dict], total_count: int) -> Dict[str, Any]:
        phase_counter: Counter = Counter()
        status_counter: Counter = Counter()
        sponsor_counter: Counter = Counter()
        intervention_map: Dict[str, str] = {}  # name -> type
        intervention_counter: Counter = Counter()
        country_counter: Counter = Counter()
        year_counter: Counter = Counter()
        enrollment_total = 0

        for t in trials:
            phase_counter[t["phase"]] += 1
            status_counter[t["status"]] += 1
            if t["sponsor"]:
                sponsor_counter[t["sponsor"]] += 1
            enrollment_total += t.get("enrollment", 0) or 0

            for iv in t.get("interventions", []):
                name = iv.get("name", "")
                if name:
                    intervention_counter[name] += 1
                    intervention_map[name] = iv.get("type", "")

            for loc in t.get("locations", []):
                country = loc.get("country", "")
                if country:
                    country_counter[country] += 1

            start = t.get("start_date", "")
            if start and len(start) >= 4:
                year_counter[start[:4]] += 1

        return {
            "total_count": total_count,
            "by_phase": dict(phase_counter.most_common()),
            "by_status": dict(status_counter.most_common()),
            "top_sponsors": [
                {"name": n, "count": c} for n, c in sponsor_counter.most_common(10)
            ],
            "top_interventions": [
                {"name": n, "type": intervention_map.get(n, ""), "count": c}
                for n, c in intervention_counter.most_common(10)
            ],
            "enrollment_total": enrollment_total,
            "year_distribution": dict(sorted(year_counter.items())),
            "top_countries": [
                {"country": n, "count": c} for n, c in country_counter.most_common(5)
            ],
        }

    # ------------------------------------------------------------------
    # Fallback data
    # ------------------------------------------------------------------
    @staticmethod
    def _get_fallback(gene: str, disease: str) -> Optional[List[Dict]]:
        gene_upper = gene.upper()
        disease_lower = disease.lower()

        key = None
        if "KRAS" in gene_upper and (
            "lung" in disease_lower or "nsclc" in disease_lower
        ):
            key = "kras_lung"
        elif "TP53" in gene_upper or "P53" in gene_upper:
            key = "tp53_cancer"
        elif "EGFR" in gene_upper:
            key = "egfr_nsclc"
        elif "BRCA" in gene_upper and "breast" in disease_lower:
            key = "brca_breast"
        elif (
            "PD-1" in gene_upper
            or "PEMBROLIZUMAB" in gene_upper
            or "NIVOLUMAB" in gene_upper
        ):
            key = "pd1_melanoma"

        if key is None:
            return None

        return _FALLBACK_DATA.get(key, None)


# ---------------------------------------------------------------------------
# Curated fallback trials (abbreviated, representative)
# ---------------------------------------------------------------------------
def _make_trial(
    nct: str,
    title: str,
    phase: str,
    status: str,
    sponsor: str,
    start: str,
    enrollment: int,
    interventions: List[Dict],
    conditions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "nct_id": nct,
        "title": title,
        "official_title": title,
        "status": status,
        "phase": phase,
        "sponsor": sponsor,
        "start_date": start,
        "completion_date": "",
        "enrollment": enrollment,
        "conditions": conditions or [],
        "interventions": interventions,
        "locations": [],
        "primary_outcomes": ["Progression Free Survival"],
        "summary": f"A {phase} study of {interventions[0]['name'] if interventions else 'investigational agent'} in patients with {conditions[0] if conditions else 'cancer'}.",
        "url": f"https://clinicaltrials.gov/study/{nct}",
    }


_FALLBACK_DATA: Dict[str, List[Dict]] = {
    "kras_lung": [
        _make_trial(
            "NCT04303780",
            "CodeBreaK 200: Sotorasib vs Docetaxel in KRAS G12C NSCLC",
            "Phase 3",
            "Active, not recruiting",
            "Amgen",
            "2020-04-15",
            345,
            [{"name": "Sotorasib", "type": "DRUG"}],
            ["Non-Small Cell Lung Cancer"],
        ),
        _make_trial(
            "NCT04685135",
            "KRYSTAL-7: Adagrasib + Pembrolizumab in KRAS G12C NSCLC",
            "Phase 2",
            "Recruiting",
            "Mirati Therapeutics",
            "2021-01-20",
            250,
            [
                {"name": "Adagrasib", "type": "DRUG"},
                {"name": "Pembrolizumab", "type": "BIOLOGICAL"},
            ],
            ["Non-Small Cell Lung Cancer"],
        ),
        _make_trial(
            "NCT05132075",
            "Divarasib (GDC-6036) in KRAS G12C Solid Tumors",
            "Phase 1",
            "Recruiting",
            "Genentech",
            "2021-12-01",
            400,
            [{"name": "Divarasib", "type": "DRUG"}],
            ["KRAS G12C Solid Tumors"],
        ),
        _make_trial(
            "NCT05252390",
            "Sotorasib + Panitumumab in KRAS G12C CRC and NSCLC",
            "Phase 2",
            "Recruiting",
            "Amgen",
            "2022-03-10",
            160,
            [
                {"name": "Sotorasib", "type": "DRUG"},
                {"name": "Panitumumab", "type": "BIOLOGICAL"},
            ],
            ["KRAS G12C Colorectal Cancer", "KRAS G12C NSCLC"],
        ),
        _make_trial(
            "NCT06347861",
            "JDQ443 + TNO155 in KRAS G12C NSCLC",
            "Phase 1",
            "Recruiting",
            "Novartis",
            "2024-02-01",
            120,
            [{"name": "JDQ443", "type": "DRUG"}, {"name": "TNO155", "type": "DRUG"}],
            ["Non-Small Cell Lung Cancer"],
        ),
    ],
    "tp53_cancer": [
        _make_trial(
            "NCT03745716",
            "APR-246 + Azacitidine in TP53-Mutant MDS/AML",
            "Phase 3",
            "Active, not recruiting",
            "Aprea Therapeutics",
            "2018-11-15",
            154,
            [
                {"name": "Eprenetapopt (APR-246)", "type": "DRUG"},
                {"name": "Azacitidine", "type": "DRUG"},
            ],
            ["Myelodysplastic Syndromes", "Acute Myeloid Leukemia"],
        ),
        _make_trial(
            "NCT04419389",
            "PC14586 (Rezatapopt) in TP53 Y220C Solid Tumors",
            "Phase 1",
            "Recruiting",
            "PMV Pharmaceuticals",
            "2020-07-01",
            200,
            [{"name": "Rezatapopt", "type": "DRUG"}],
            ["TP53 Y220C Solid Tumors"],
        ),
        _make_trial(
            "NCT05406531",
            "Arsenic Trioxide in TP53-Mutant Cancers",
            "Phase 2",
            "Recruiting",
            "NCI",
            "2022-06-01",
            90,
            [{"name": "Arsenic Trioxide", "type": "DRUG"}],
            ["TP53-Mutant Solid Tumors"],
        ),
    ],
    "egfr_nsclc": [
        _make_trial(
            "NCT04129502",
            "Amivantamab + Lazertinib in EGFR-Mutant NSCLC",
            "Phase 3",
            "Active, not recruiting",
            "Janssen",
            "2019-11-01",
            1014,
            [
                {"name": "Amivantamab", "type": "BIOLOGICAL"},
                {"name": "Lazertinib", "type": "DRUG"},
            ],
            ["EGFR-Mutant Non-Small Cell Lung Cancer"],
        ),
        _make_trial(
            "NCT02296125",
            "Osimertinib vs Comparator in EGFR T790M NSCLC (AURA3)",
            "Phase 3",
            "Completed",
            "AstraZeneca",
            "2014-12-01",
            419,
            [{"name": "Osimertinib", "type": "DRUG"}],
            ["EGFR T790M NSCLC"],
        ),
        _make_trial(
            "NCT04487080",
            "Furmonertinib in EGFR-Mutant NSCLC",
            "Phase 3",
            "Recruiting",
            "Allist Pharmaceuticals",
            "2020-08-01",
            358,
            [{"name": "Furmonertinib", "type": "DRUG"}],
            ["EGFR-Mutant NSCLC"],
        ),
    ],
    "brca_breast": [
        _make_trial(
            "NCT02032823",
            "Olaparib vs Chemotherapy in gBRCA Breast Cancer (OlympiAD)",
            "Phase 3",
            "Completed",
            "AstraZeneca",
            "2014-04-01",
            302,
            [{"name": "Olaparib", "type": "DRUG"}],
            ["BRCA-Mutated Breast Cancer"],
        ),
        _make_trial(
            "NCT03150576",
            "Talazoparib + Enzalutamide in BRCA-Deficient Breast Cancer",
            "Phase 2",
            "Recruiting",
            "Pfizer",
            "2017-09-01",
            220,
            [
                {"name": "Talazoparib", "type": "DRUG"},
                {"name": "Enzalutamide", "type": "DRUG"},
            ],
            ["BRCA-Mutated Breast Cancer"],
        ),
    ],
    "pd1_melanoma": [
        _make_trial(
            "NCT01866319",
            "Pembrolizumab vs Ipilimumab in Melanoma (KEYNOTE-006)",
            "Phase 3",
            "Completed",
            "Merck Sharp & Dohme",
            "2013-09-01",
            834,
            [{"name": "Pembrolizumab", "type": "BIOLOGICAL"}],
            ["Melanoma"],
        ),
        _make_trial(
            "NCT03068455",
            "Nivolumab + Relatlimab in Melanoma (RELATIVITY-047)",
            "Phase 3",
            "Active, not recruiting",
            "Bristol-Myers Squibb",
            "2017-04-01",
            714,
            [
                {"name": "Nivolumab", "type": "BIOLOGICAL"},
                {"name": "Relatlimab", "type": "BIOLOGICAL"},
            ],
            ["Melanoma"],
        ),
    ],
}
