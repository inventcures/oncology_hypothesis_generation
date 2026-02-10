# V8 — Visual Feedback, Progress System & Typography Coherence

> **Goal**: Replace the near-invisible "small blue text" status with a clear, real-time, multi-stage progress experience that keeps the user informed and engaged throughout the 10-20s processing window. Additionally, unify font sizes and types across all module screens/tabs for a coherent visual identity.

---

## Part A: Progress & Visual Feedback

### 1. Current State — What's Broken

| Problem | Where | Details |
|---------|-------|---------|
| **Status text is invisible** | Sidebar, `page.tsx:864` | `text-xs text-blue-600 font-mono animate-pulse` — 12px pulsing blue text tucked behind "Live Feed" header. Easy to miss. |
| **Header dots are broken** | Header, `page.tsx:698-711` | Dots check for substrings like `"genes"`, `"Identifying"` — but SSE sends `"Extracting biological entities..."`. **No match = all dots show green immediately.** |
| **Progress values go unused** | `page.tsx:617` | Backend sends `progress: 0.1, 0.4, 0.5, 0.7, 0.8, 0.9, 1.0` — frontend reads `event.message` but **never reads `event.progress`**. |
| **Main canvas is blank during loading** | `page.tsx:2273-2285` | Shows static "Ready to Explore" placeholder with a microscope icon. No spinner. No indication anything is happening. |
| **No elapsed time** | Nowhere | User has no sense of how long they've been waiting or how long remains. |
| **No partial results** | `page.tsx:619-624` | Everything arrives in one `complete` event. User sees nothing for ~15s, then everything at once. |

---

### 2. Design — Pipeline Stepper + Progress Bar

#### 2.1 Architecture

Replace the scattered status indicators with a **single, prominent Pipeline Stepper** component that lives in the **main canvas area** (center of screen) during loading, then disappears when results arrive.

```
┌─────────────────────────────────────────────────────────────┐
│ Header  [compact spinner + "52% — Searching literature..."] │
├──────────┬──────────────────────────────────────────────────┤
│          │  ┌──────────────────────────────────────────┐    │
│ Sidebar  │  │       PIPELINE STEPPER (during load)     │    │
│          │  │                                          │    │
│ [mini    │  │  ✓ Entity Extraction             2.1s    │    │
│  progress│  │  ✓ Knowledge Graph               4.3s    │    │
│  bar]    │  │  ◉ Literature & Atlas        ██░░░ 52%   │    │
│          │  │  ○ Node Ranking                          │    │
│          │  │  ○ Hypothesis Generation                 │    │
│          │  │                                          │    │
│          │  │  ━━━━━━━━━━━━━━━━░░░░░░░  52%     12s    │    │
│          │  │                                          │    │
│          │  └──────────────────────────────────────────┘    │
│          │                                                  │
├──────────┴──────────────────────────────────────────────────┤
```

#### 2.2 Pipeline Steps (mapped to actual backend SSE events)

| Step # | Label | SSE trigger | Icon | progress range |
|--------|-------|-------------|------|----------------|
| 1 | Entity Extraction | `progress: 0.1` (event: `status`, msg: `"Extracting biological entities..."`) | `Dna` | 0% → 10% |
| 2 | Knowledge Graph | `progress: 0.4` (event: `kg_complete`) | `Network` | 10% → 40% |
| 3 | Literature & Atlas | `progress: 0.7` (event: `papers_complete`) | `FileText` | 40% → 70% |
| 4 | Node Ranking | `progress: 0.8` (event: `status`, msg: `"Ranking nodes..."`) | `Sparkles` | 70% → 80% |
| 5 | Hypothesis Generation | `progress: 1.0` (event: `complete`) | `Lightbulb` | 80% → 100% |

#### 2.3 Step States

Each step has one of four visual states:

| State | Visual | Meaning |
|-------|--------|---------|
| `pending` | Gray circle `○`, muted text | Not started yet |
| `active` | Pulsing colored circle `◉`, bold text, spinner | Currently processing |
| `done` | Green checkmark `✓`, elapsed time + detail shown | Completed |
| `error` | Red `✗`, error message | Failed (non-blocking) |

#### 2.4 Global Progress Bar

Below the steps, a horizontal progress bar:

- **Width**: Spans full stepper width
- **Fill**: Smooth animated fill using CSS `transition: width 300ms ease`
- **Color**: Gradient from indigo-500 (start) to emerald-500 (end)
- **Label**: `{percent}%` on left, elapsed time `{elapsed}s` on right
- **Between events**: Bar smoothly interpolates between known progress values (e.g., if at 40% waiting for 70%, slowly creep toward ~65% over time, then snap to 70% when event arrives). Prevents the bar from appearing frozen.

---

### 3. Implementation Plan

#### 3.1 New Frontend State

Add to `page.tsx` state declarations (~line 266):

```typescript
const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
const [progress, setProgress] = useState(0);       // 0-100
const [pipelineStartTime, setPipelineStartTime] = useState<number | null>(null);
```

Type definition:

```typescript
type StepStatus = 'pending' | 'active' | 'done' | 'error';

interface PipelineStep {
  id: string;
  label: string;
  icon: string;
  status: StepStatus;
  startedAt?: number;
  completedAt?: number;
  detail?: string;       // e.g. "Found 6 papers", "12 nodes, 18 edges"
  errorMsg?: string;
}
```

Initial steps (set on submit):

```typescript
const PIPELINE_STEPS: PipelineStep[] = [
  { id: 'ner',        label: 'Entity Extraction',      icon: 'Dna',       status: 'pending' },
  { id: 'kg',         label: 'Knowledge Graph',         icon: 'Network',   status: 'pending' },
  { id: 'lit',        label: 'Literature & Atlas',      icon: 'FileText',  status: 'pending' },
  { id: 'rank',       label: 'Node Ranking',            icon: 'Sparkles',  status: 'pending' },
  { id: 'hypothesis', label: 'Hypothesis Generation',   icon: 'Lightbulb', status: 'pending' },
];
```

#### 3.2 SSE Event → Step Mapping

In the SSE reader loop (`page.tsx:613-626`), replace `setStatus(event.message)` with structured updates:

```typescript
if (event.progress !== undefined) {
  setProgress(Math.round(event.progress * 100));
}

switch (event.type) {
  case 'status':
    if (event.progress <= 0.1) advanceStep('ner');
    else if (event.progress <= 0.5) advanceStep('lit');
    else if (event.progress <= 0.8) advanceStep('rank');
    else if (event.progress <= 0.9) advanceStep('hypothesis');
    break;
  case 'kg_complete':
    completeStep('ner');
    completeStep('kg', `${event.data?.node_count} nodes, ${event.data?.edge_count} edges`);
    advanceStep('lit');
    break;
  case 'papers_complete':
    completeStep('lit', `Found ${event.data?.paper_count} papers`);
    advanceStep('rank');
    break;
  case 'complete':
    completeAllSteps();
    break;
  case 'error':
    errorStep(event.step, event.message);
    break;
}
```

Helper functions:

```typescript
function advanceStep(stepId: string) {
  setPipelineSteps(prev => prev.map(s =>
    s.id === stepId && s.status === 'pending'
      ? { ...s, status: 'active', startedAt: Date.now() }
      : s
  ));
}

function completeStep(stepId: string, detail?: string) {
  setPipelineSteps(prev => prev.map(s =>
    s.id === stepId
      ? { ...s, status: 'done', completedAt: Date.now(), detail }
      : s
  ));
}
```

#### 3.3 New Component: `PipelineStepper.tsx`

Create `frontend/app/components/PipelineStepper.tsx`.

**Props:**
```typescript
interface PipelineStepperProps {
  steps: PipelineStep[];
  progress: number;        // 0-100
  startTime: number | null;
}
```

**Layout:**
- Centered card in the main canvas area (`max-w-lg mx-auto`)
- White card with subtle shadow, rounded corners
- Vertical step list with connecting line between steps
- Global progress bar at bottom
- Elapsed time counter (updates every second via `useEffect` + `setInterval`)

**Visual hierarchy:**
- Card title: "Analyzing Your Query" with a subtle animated gradient border
- Each step row: icon + label + status indicator + detail/timing
- Active step: slightly larger, indigo background highlight, spinning loader icon
- Completed step: green check, muted text, timing in gray
- Pending step: gray circle, muted text
- Progress bar: full width, rounded, gradient fill, percentage + elapsed labels

#### 3.4 Render in Main Canvas

In `page.tsx`, inside the main canvas `<div>` (~line 1043), add conditional render:

```tsx
{loading && !graphData && (
  <div className="flex items-center justify-center w-full h-full">
    <PipelineStepper
      steps={pipelineSteps}
      progress={progress}
      startTime={pipelineStartTime}
    />
  </div>
)}
```

This replaces the static "Ready to Explore" microscope icon during loading.

#### 3.5 Progress Interpolation (smooth fill between events)

Prevent the progress bar from appearing frozen between SSE events:

```typescript
useEffect(() => {
  if (!loading || progress >= 100) return;

  const targets = [10, 38, 68, 78, 88, 98];
  const nextTarget = targets.find(t => t > progress) ?? progress;

  const interval = setInterval(() => {
    setProgress(prev => {
      if (prev >= nextTarget) return prev;
      return prev + 0.5;  // Slow creep: +0.5% per 200ms
    });
  }, 200);

  return () => clearInterval(interval);
}, [loading, progress]);
```

When a real SSE event arrives, `setProgress` snaps to the real value, overriding the interpolation.

#### 3.6 Fix the Header

**Remove the broken header dots** (lines 698-711). Replace with compact inline progress:

```tsx
{hasSearched && loading && (
  <div className="flex items-center gap-2 text-sm text-slate-500">
    <Loader2 size={14} className="animate-spin text-blue-500" />
    <span>{progress}% — {status}</span>
  </div>
)}
{hasSearched && !loading && graphData && (
  <ExportReport ... />
)}
```

#### 3.7 Fix the Sidebar Status

Replace the tiny `text-xs text-blue-600` with a compact mini-progress bar:

```tsx
{loading && (
  <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
    <div className="flex items-center justify-between mb-2">
      <span className="text-xs font-semibold text-blue-700">Processing</span>
      <span className="text-xs text-blue-500 font-mono">{progress}%</span>
    </div>
    <div className="w-full bg-blue-100 rounded-full h-1.5">
      <div
        className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
        style={{ width: `${progress}%` }}
      />
    </div>
    <p className="text-xs text-blue-600 mt-1.5">{status}</p>
  </div>
)}
```

#### 3.8 Fallback Mode (non-SSE)

When SSE fails and frontend falls back to regular POST (`page.tsx:635-658`), drive the same stepper with synthetic timings:

```typescript
setTimeout(() => { advanceStep('ner'); setProgress(10); }, 300);
setTimeout(() => { completeStep('ner'); advanceStep('kg'); setProgress(30); }, 800);
setTimeout(() => { completeStep('kg'); advanceStep('lit'); setProgress(50); }, 1800);
setTimeout(() => { completeStep('lit'); advanceStep('rank'); setProgress(70); }, 2800);
setTimeout(() => { completeStep('rank'); advanceStep('hypothesis'); setProgress(85); }, 3500);
```

---

### 4. Backend Changes

#### 4.1 More Granular SSE Events

**Recommended for v8:** Add 1-2 additional SSE yields in `main.py` by surfacing sub-steps from the KG build:

```python
yield sse('status', 'Extracting biological entities...', 0.1)
kg_result = await req_graph.build_from_query(query.text)
yield sse('status', 'Enriching with OpenTargets associations...', 0.25)
subgraph_data = req_graph.get_subgraph_data()
yield sse('kg_complete', 'Knowledge graph built', 0.4, {...})
```

#### 4.2 Add Elapsed Timing to SSE Events

Add `elapsed_ms` field so frontend can compute accurate per-step durations:

```python
import time
start = time.monotonic()

yield f"data: {json.dumps({
    'type': 'status',
    'message': 'Extracting biological entities...',
    'progress': 0.1,
    'elapsed_ms': int((time.monotonic() - start) * 1000)
})}\n\n"
```

---

## Part B: Typography & Visual Coherence Across Tabs

### 5. Current State — Font Inconsistencies

| View / Component | Title style | Body text | Padding | File |
|-----------------|-------------|-----------|---------|------|
| **WhatIfSimulator** | `font-bold text-slate-700` (h3) | `text-xs text-slate-500` | `p-8` | `WhatIfSimulator.tsx:57-62` |
| **CompetitiveDashboard** | `text-2xl font-bold text-slate-800` (h2) | `text-sm text-slate-500` | `p-8` | `CompetitiveDashboard.tsx:79-82` |
| **Table view** | N/A (data table) | Mixed | `p-12` | `page.tsx:~1337` |
| **Metrics view** | N/A | Mixed | `p-12` | `page.tsx:~1416` |
| **Papers view** | N/A | Mixed | `p-12` | `page.tsx:~1491` |
| **Validate view** | No padding wrapper | Component internal | `h-full` | `page.tsx:~1544` |
| **Pathway view** | N/A | N/A | `p-4` | `page.tsx:~1571` |
| **Deep Research** | N/A | Mixed | `p-12` | `page.tsx:~1580` |
| **Trials view** | N/A | N/A | `p-6` | `page.tsx:~2201` |
| **Dossier** | Component internal | Mixed | No wrapper padding | `page.tsx:~2228` |
| **Indications** | Component internal | Mixed | No wrapper padding | `page.tsx:~2239` |

**Problems:**
- Wrapper padding varies: `p-4`, `p-6`, `p-8`, `p-12`, or none
- Title hierarchy inconsistent: some use `h2`, some `h3`, some have no title
- Body text sizes vary: `text-xs`, `text-sm`, `text-base` across views
- Subtitle/description style varies per component
- Card internal padding varies per component

### 6. Design Tokens — Unified Typography Scale

Define a consistent typography system for all tab/view content:

#### 6.1 View Layout Tokens

All views rendered inside the canvas should follow this structure:

```
┌─────────────────────────────────────────┐
│  pt-16 px-8 pb-8                        │  ← Unified padding (pt-16 clears toolbar)
│                                         │
│  View Title (h2)          text-xl       │
│  Subtitle                 text-sm       │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ Card                   p-6      │    │
│  │ Card Title (h3)   text-base     │    │
│  │ Card Body         text-sm       │    │
│  │ Card Detail       text-xs       │    │
│  └─────────────────────────────────┘    │
│                                         │
└─────────────────────────────────────────┘
```

#### 6.2 Token Table

| Token | Class | Usage |
|-------|-------|-------|
| **View container** | `w-full h-full overflow-auto pt-6 px-8 pb-8` | Every view wrapper in page.tsx |
| **View max-width** | `max-w-6xl mx-auto` | Content constraint (all views) |
| **View title** | `text-xl font-bold text-slate-800` | Primary heading per view (h2) |
| **View subtitle** | `text-sm text-slate-500 mt-1` | Description below title |
| **Section gap** | `space-y-6` | Between cards/sections |
| **Card** | `bg-white p-6 rounded-xl border border-slate-200 shadow-sm` | Every card container |
| **Card title** | `text-base font-semibold text-slate-700` | Card heading (h3) |
| **Card body** | `text-sm text-slate-600 leading-relaxed` | Primary content text |
| **Card detail** | `text-xs text-slate-400` | Metadata, timestamps, secondary info |
| **Metric value** | `text-2xl font-bold text-slate-800` | Large numbers in metric cards |
| **Metric label** | `text-xs font-medium text-slate-500 uppercase tracking-wider` | Label above/below metrics |
| **Badge/tag** | `text-xs font-medium px-2 py-0.5 rounded-full` | Entity tags, status badges |
| **Table header** | `text-xs font-semibold text-slate-500 uppercase tracking-wider` | All table headers |
| **Table cell** | `text-sm text-slate-700` | All table body cells |
| **Empty state** | `text-sm text-slate-400 text-center py-12` | "No data" placeholders |

#### 6.3 Font Family

Already set globally via `inter.className` in `layout.tsx`. No changes needed — but ensure no component overrides with `font-mono` except for code/data values.

`font-mono` usage should be **restricted to**:
- Progress percentages
- Numeric IDs (NCT numbers, patent IDs)
- Code snippets (gRNA sequences, protocol commands)

### 7. Implementation — Per-View Changes

#### 7.1 Wrapper Normalization in `page.tsx`

Every view's wrapper `<div>` should use identical padding. Current wrappers to normalize:

| View | Current wrapper | Change to |
|------|----------------|-----------|
| table (~1337) | `p-12` | `pt-6 px-8 pb-8` |
| metrics (~1416) | `p-12` | `pt-6 px-8 pb-8` |
| papers (~1491) | `p-12` | `pt-6 px-8 pb-8` |
| validate (~1544) | `h-full` (no padding) | `pt-6 px-8 pb-8 h-full` |
| pathway (~1571) | `p-4` | `pt-6 px-8 pb-8` |
| deep_research (~1580) | `p-12` | `pt-6 px-8 pb-8` |
| trials (~2201) | `p-6` | `pt-6 px-8 pb-8` |
| dossier (~2228) | none | `pt-6 px-8 pb-8` |
| indications (~2239) | none | `pt-6 px-8 pb-8` |
| whatif (~2250) | component internal `p-8` | Remove component padding, use wrapper `pt-6 px-8 pb-8` |
| competitive (~2262) | component internal `p-8` | Remove component padding, use wrapper `pt-6 px-8 pb-8` |

#### 7.2 Component Internal Fixes

**WhatIfSimulator.tsx:**
- Change root `p-8` → `space-y-6` (padding comes from wrapper)
- Change h3 `font-bold text-slate-700` → `text-xl font-bold text-slate-800` (view title)
- Change description `text-xs text-slate-500` → `text-sm text-slate-500` (view subtitle)
- Change card padding to `p-6`

**CompetitiveDashboard.tsx:**
- Change root `p-8` → `space-y-6` (padding comes from wrapper)
- Title `text-2xl font-bold text-slate-800` → `text-xl font-bold text-slate-800` (consistent)
- Subtitle already `text-sm text-slate-500` — correct

**ValidationDashboard (inline in page.tsx):**
- Audit card styles to match token table
- Normalize section titles to `text-base font-semibold text-slate-700`

**TrialsDashboard, DossierView, IndicationsView:**
- Same audit: titles, body text, card styles per token table

---

## 8. Files to Change

| File | Changes |
|------|---------|
| `frontend/app/components/PipelineStepper.tsx` | **NEW** — main pipeline stepper component |
| `frontend/app/page.tsx` | Add pipeline state + progress; rewrite SSE handler; replace canvas loading state with stepper; fix header (remove broken dots); fix sidebar status; normalize ALL view wrapper padding |
| `frontend/app/components/WhatIfSimulator.tsx` | Remove internal padding; normalize title/body typography to tokens |
| `frontend/app/components/CompetitiveDashboard.tsx` | Remove internal padding; normalize title size to tokens |
| `backend/app/main.py` | Add `elapsed_ms` to SSE events; optionally add 1-2 more granular KG sub-step events |

---

## 9. Acceptance Criteria

### Progress System
- [ ] Centered, prominent step-by-step pipeline stepper in main canvas during loading
- [ ] Each step transitions `pending → active → done` with clear visual distinction
- [ ] Progress bar fills smoothly 0% → 100% (no frozen states between events)
- [ ] Elapsed time counter ticks every second
- [ ] Completed steps show per-step timing and detail (e.g., "12 nodes, 18 edges")
- [ ] Stepper disappears when results arrive
- [ ] Header shows compact spinner + percentage during loading
- [ ] Sidebar shows mini progress bar during loading
- [ ] Error states render clearly with red indicator
- [ ] Fallback (non-SSE) mode drives same stepper with synthetic timings

### Typography Coherence
- [ ] All view wrappers use identical padding (`pt-6 px-8 pb-8`)
- [ ] All view titles use `text-xl font-bold text-slate-800`
- [ ] All view subtitles use `text-sm text-slate-500`
- [ ] All cards use `p-6 rounded-xl border border-slate-200 shadow-sm`
- [ ] All card titles use `text-base font-semibold text-slate-700`
- [ ] All body text uses `text-sm text-slate-600`
- [ ] All detail/meta text uses `text-xs text-slate-400`
- [ ] `font-mono` only appears on numeric/code values
- [ ] Visual spot-check: switching between any two tabs feels like the same app

---

## 10. Out of Scope (Future)

- Streaming partial results (show graph as it builds, papers as they arrive)
- Cancellation (abort processing mid-stream)
- Per-step retry
- Persistent progress history across page reloads
- Dark mode typography variants
