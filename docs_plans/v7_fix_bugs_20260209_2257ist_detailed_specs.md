# v7 Bug Fix Specs — Literature Search + Stale View Data

**Date:** 2026-02-09 22:57 IST  
**Priority:** P0 (both bugs break core UX)  
**Files affected:** `backend/app/main.py`, `frontend/app/page.tsx`

---

## Bug #1: Literature / Paper Search Returns 0 Papers

### Symptoms

- The "Papers" tab is always empty after a search.
- `/generate` response contains `"papers": []` even though the Semantic Scholar API is healthy and returns valid results when called directly.

### Root Cause

The `asyncio.gather()` call in `/generate` (backend/app/main.py:354-358) runs three tasks concurrently:

```python
_, papers, atlas_data = await asyncio.gather(
    req_graph.build_from_query(query.text),      # Task 1: KG build
    lit_agent.search_papers(query.text, limit=6), # Task 2: Literature
    asyncio.to_thread(atlas_agent.fetch_tumor_atlas, tissue_type, 300),  # Task 3: Atlas
)
```

**Problem:** `asyncio.gather()` without `return_exceptions=True` raises the **first exception** from any task and discards **all** results. If Task 1 (KG build) or Task 3 (Atlas) throws an exception, the papers result from Task 2 is lost entirely — even if Task 2 succeeded.

The Atlas agent (`backend/app/atlas.py`) uses `cellxgene_census.open_soma()` which:
1. Requires the `cellxgene-census` package to be importable (heavy dependency, may fail on Railway)
2. Opens a network connection to a remote SOMA database (can timeout)
3. Any exception propagates up through `asyncio.to_thread` → `asyncio.gather` → kills all results

**Secondary issue:** We removed the hardcoded S2 API key in the previous commit (`S2_API_KEY = os.getenv("S2_API_KEY", "")`), and the Railway deployment has no `S2_API_KEY` env var set. Without an API key, Semantic Scholar rate-limits to 100 requests per 5 minutes. This won't cause 0 papers for occasional requests, but will under load. However, even if S2 returns papers successfully, the `asyncio.gather` exception from atlas kills the entire result.

### Fix Plan

#### Fix 1a: Add `return_exceptions=True` and handle partial failures

**File:** `backend/app/main.py`, lines 354-358

Replace:
```python
_, papers, atlas_data = await asyncio.gather(
    req_graph.build_from_query(query.text),
    lit_agent.search_papers(query.text, limit=6),
    asyncio.to_thread(atlas_agent.fetch_tumor_atlas, tissue_type, 300),
)
```

With:
```python
kg_result, papers_result, atlas_result = await asyncio.gather(
    req_graph.build_from_query(query.text),
    lit_agent.search_papers(query.text, limit=6),
    asyncio.to_thread(atlas_agent.fetch_tumor_atlas, tissue_type, 300),
    return_exceptions=True,
)

# Handle partial failures gracefully — each task's failure is independent
if isinstance(papers_result, BaseException):
    logger.error("Literature search failed: %s", papers_result)
    papers_result = []

if isinstance(atlas_result, BaseException):
    logger.error("Atlas fetch failed: %s", atlas_result)
    atlas_result = {"cells": [], "error": str(atlas_result)}

if isinstance(kg_result, BaseException):
    logger.error("KG build failed: %s", kg_result)
    # KG build failure is critical but we still return what we have

papers = papers_result
atlas_data = atlas_result
```

**Rationale:** Each of the three concurrent tasks is independent. A failure in the atlas (common — heavy external dependency) should not prevent papers from being returned. A failure in literature search should not prevent the knowledge graph from being returned.

#### Fix 1b: Set the S2_API_KEY on Railway

**Action:** Run `railway variables set S2_API_KEY=5Jpny5JJeT5huCtZZRnnl1RCZULBJrcn7hvhTv3T` on the backend service (or use the Railway dashboard). This restores the higher rate limit (100 req/sec instead of 100 req/5min).

**Note:** The key should NOT be in source code (we correctly removed it). It should live only in Railway environment variables.

#### Fix 1c: Add import for logger in main.py

**File:** `backend/app/main.py`

Add at the top of the file (after existing imports):
```python
import logging

logger = logging.getLogger(__name__)
```

This is needed for the error logging in Fix 1a.

---

## Bug #2: Stale Data in Validation / Deep Research Tabs on New Search

### Symptoms

- User searches "STK11 in lung adenocarcinoma" → views Validate tab → sees STK11 validation data.
- User then searches "role of TP53 in cancer" → Validate tab still shows STK11 data.
- Same issue affects Deep Research tab — previous query's data persists.

### Root Cause

The `handleSubmit` function (`frontend/app/page.tsx:338-378`) resets some state but **not all**:

```typescript
const handleSubmit = useCallback(async (e?: React.FormEvent, overrideQuery?: string) => {
    // ...
    setLoading(true);
    setHasSearched(true);
    setHypotheses([]);      // ✅ Reset
    setGraphData(null);     // ✅ Reset
    setPapers([]);          // ✅ Reset
    setStatus("Analyzing your question...");
    // ...
```

**Missing resets:**
- `setDrData(null)` — Deep Research data from previous query persists
- `setDrError(null)` — Deep Research error from previous query persists  
- `setValidationData(null)` — Validation data from previous query persists
- `setViewMode("graph")` — User may be on "validate" tab viewing old data; should return to graph view on new search
- `setHoveredEdge(null)` — Graph hover state from previous query persists
- `setHoveredNode(null)` — Graph hover state from previous query persists
- `setSelectedNode(null)` — Graph selection state from previous query persists

### Fix Plan

#### Fix 2a: Reset all view-specific state in handleSubmit

**File:** `frontend/app/page.tsx`, inside `handleSubmit`, after the existing reset lines (around line 345-349)

Add these reset calls:
```typescript
setLoading(true);
setHasSearched(true);
setHypotheses([]);
setGraphData(null);
setPapers([]);
// --- Reset all secondary view state ---
setDrData(null);
setDrError(null);
setValidationData(null);
setHoveredEdge(null);
setHoveredNode(null);
setSelectedNode(null);
setViewMode("graph");  // Return to default view on new search
setStatus("Analyzing your question...");
```

**Rationale:** When a user initiates a new search, ALL state from the previous search must be cleared. The Validation and Deep Research views are computed lazily (user clicks a tab, which triggers an API call using the current `graphData`). But if old data is still in state, the UI will render it until the user manually re-triggers. Clearing it forces a clean slate.

#### Fix 2b: Guard Validation/Deep Research renders against query mismatch

As a defense-in-depth measure, the Deep Research and Validation data should be tagged with the query that produced them. If the current query doesn't match, the data is stale and should be discarded.

**File:** `frontend/app/page.tsx`

In the `DeepResearchData` type, add a `query` field:
```typescript
type DeepResearchData = {
  struct: StructureResult;
  patent: PatentResult;
  models: ModelResult;
  proto: ProtocolResult;
  target: string;
  mutation: string | null;
  tissue: string;
  query: string;  // <-- NEW: track which query produced this data
};
```

In `handleDeepResearch`, include the query when setting state:
```typescript
setDrData({ struct, patent, models, proto, target: targetNode.id, mutation, tissue, query });
```

In the render, check staleness:
```typescript
{viewMode === "deep_research" && (
    <div className="w-full h-full p-12 overflow-auto bg-slate-50/50">
        {(!drData || drData.query !== query) ? (
            // Show "Run Deep Research" prompt (existing UI)
```

Similarly for validation — add a `validationQuery` state variable:
```typescript
const [validationQuery, setValidationQuery] = useState<string>("");
```

In `handleValidation`:
```typescript
setValidationQuery(query);
```

In render:
```typescript
{viewMode === "validate" && validationData && validationQuery === query ? (
    <ValidationDashboard ... />
) : (
    // Show "Run Validation" prompt or loading state
)}
```

---

## Implementation Order

| Step | Priority | Bug | What | File(s) | LOC |
|------|----------|-----|------|---------|-----|
| 1 | P0 | #1 | Add `return_exceptions=True` + handle partial failures | `backend/app/main.py` | ~15 |
| 2 | P0 | #1 | Add `import logging` + `logger` to main.py | `backend/app/main.py` | 2 |
| 3 | P0 | #1 | Set `S2_API_KEY` env var on Railway | Railway dashboard | 0 |
| 4 | P0 | #2 | Reset all secondary state in `handleSubmit` | `frontend/app/page.tsx` | 7 |
| 5 | P1 | #2 | Tag DR/Validation data with source query | `frontend/app/page.tsx` | ~12 |
| 6 | — | — | Verify: `python3 -c "import ast; ..."` + `npx next build` | — | 0 |
| 7 | — | — | Deploy both services to Railway | — | 0 |

**Total estimated LOC changed:** ~36  
**Estimated time:** 15-20 minutes

---

## Verification Plan

### Bug #1 Verification
1. Deploy backend with Fix 1a.
2. `curl -s "https://backend-production-baa6.up.railway.app/generate" -X POST -H "Content-Type: application/json" -d '{"text":"role of tp53 in cancer"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('Papers:', len(d.get('papers',[])))"`
3. Expected: `Papers: 6` (or similar non-zero count).
4. If atlas fails, papers should still be returned, and `atlas.cells` should be `[]` with an error message.

### Bug #2 Verification
1. Deploy frontend with Fix 2a.
2. Search "STK11 in lung adenocarcinoma".
3. Click Validate tab → see STK11 validation data.
4. Search "role of TP53 in cancer".
5. Validate tab should be empty (showing "Run Validation" prompt, not STK11 data).
6. Deep Research tab should also be empty (not showing STK11 data).
7. View mode should reset to "graph" on new search.

---

## Risk Assessment

| Fix | Risk | Mitigation |
|-----|------|------------|
| 1a: `return_exceptions=True` | Low — well-documented asyncio pattern | `isinstance(result, BaseException)` check is robust |
| 1b: Set S2 key on Railway | None — env var only | Key already exists in Railway's secret store pattern |
| 2a: Reset state in handleSubmit | Very low — additive change only | No existing behavior depends on stale state persisting |
| 2b: Query tagging | Low — additive type change | Backward compatible; old data without `query` field triggers re-fetch |
