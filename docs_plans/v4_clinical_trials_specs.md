# V4: Clinical Trials Tab — Specification

## Overview
Add a 7th tab ("Trials") to the results toolbar that queries ClinicalTrials.gov v2 API for active/completed trials related to the gene + disease extracted from the user's query.

## Backend

### Module: `backend/app/clinical_trials.py`
- **Class**: `ClinicalTrialsClient`
- **Method**: `search_trials(gene, disease, status, phase, page_size)` → dict
- **API**: ClinicalTrials.gov v2 (`https://clinicaltrials.gov/api/v2/studies`)
- **Query strategy**: `query.cond` for disease, `query.intr` for gene/drug (NOT `query.term` which is too broad)
- **Fields**: 18 selected fields to minimize payload
- **Per-trial parsing**: nct_id, title, official_title, status, phase, sponsor, start_date, completion_date, enrollment, conditions, interventions, locations, primary_outcomes, summary, url
- **Summary stats**: `_compute_summary()` → by_phase, by_status, top_sponsors, top_interventions, enrollment_total, year_distribution, top_countries
- **Fallback**: Curated static data for 5 common queries (KRAS/lung, TP53/cancer, EGFR/NSCLC, BRCA/breast, PD-1/melanoma)

### Endpoint: `GET /clinical_trials`
- **Query params**: `gene` (required), `disease` (optional, default "cancer"), `status` (optional), `phase` (optional), `page_size` (optional, default 20)
- **Response**: `{ trials: [...], summary: {...}, query: {...}, total: N, source: "api"|"fallback" }`

## Frontend

### Component: `ClinicalTrialsDashboard.tsx` (~480 lines)
- **Types**: ClinicalTrial, TrialsSummary, ClinicalTrialsData
- **Sub-components**: StatCard, PhaseBar (stacked horizontal), YearChart (SVG vertical bars), SponsorList, TrialCard (expandable)
- **States**: empty (search prompt), loading (spinner), results (full dashboard)
- **Export**: CSV download + Copy Summary to clipboard
- **Fallback warning**: Yellow banner when `source === "fallback"`
- **Accent color**: Cyan throughout

### Integration in `page.tsx`
- viewMode union type extended with `"trials"`
- State: `trialsData`, `trialsLoading`, `trialsQuery`
- Reset on new query in `handleSubmit`
- `handleTrialsSearch` callback: extracts gene/disease from graph nodes, calls backend
- Toolbar: 7th button with Activity icon, cyan accent, separator before it
- Render: `ClinicalTrialsDashboard` component in trials view block

## Data Flow
1. User searches → graph generated → "Trials" tab appears in toolbar
2. User clicks "Trials" → sees empty state with "Search Clinical Trials" CTA
3. Click CTA → `handleTrialsSearch` fires → extracts gene+disease from graph → calls `GET /clinical_trials`
4. Backend queries ClinicalTrials.gov v2 API (or returns fallback if API fails)
5. Dashboard renders: stat cards, phase distribution bar, year chart, sponsor list, expandable trial cards
6. User can export CSV or copy summary

## Design Decisions
- **v2 API**: Uses the newer ClinicalTrials.gov v2 API (not legacy v1)
- **Structured query**: `query.cond` + `query.intr` avoids noise from `query.term`
- **Fallback data**: Ensures demo always works even if ClinicalTrials.gov is unreachable
- **No pagination**: First page only (up to 20 trials) — sufficient for overview
- **Cyan accent**: Distinguishes from other tabs (blue=graph, emerald=validate, purple=feasibility)
