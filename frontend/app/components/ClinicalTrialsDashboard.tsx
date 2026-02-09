"use client";

import React, { useState } from "react";
import {
  Activity,
  ExternalLink,
  Download,
  Copy,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Search,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ClinicalTrial {
  nct_id: string;
  title: string;
  official_title: string;
  status: string;
  phase: string;
  sponsor: string;
  start_date: string;
  completion_date: string;
  enrollment: number;
  conditions: string[];
  interventions: { name: string; type: string }[];
  locations: { city: string; state: string; country: string }[];
  primary_outcomes: string[];
  summary: string;
  url: string;
}

interface TrialsSummary {
  total_count: number;
  by_phase: Record<string, number>;
  by_status: Record<string, number>;
  top_sponsors: { name: string; count: number }[];
  top_interventions: { name: string; type: string; count: number }[];
  enrollment_total: number;
  year_distribution: Record<string, number>;
  top_countries: { country: string; count: number }[];
}

export interface ClinicalTrialsData {
  query: {
    gene: string;
    disease: string;
    status_filter: string;
    phase_filter: string;
  };
  summary: TrialsSummary;
  trials: ClinicalTrial[];
  source: "live" | "fallback";
}

interface ClinicalTrialsDashboardProps {
  data: ClinicalTrialsData | null;
  loading: boolean;
  onSearch: () => void;
  gene?: string;
  disease?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const PHASE_COLORS: Record<string, string> = {
  "Early Phase 1": "#38bdf8",
  "Phase 1": "#0ea5e9",
  "Phase 2": "#3b82f6",
  "Phase 3": "#4f46e5",
  "Phase 4": "#7c3aed",
  "N/A": "#94a3b8",
};

const STATUS_COLORS: Record<string, string> = {
  Recruiting: "#10b981",
  "Active, not recruiting": "#f59e0b",
  Completed: "#6b7280",
  "Not yet recruiting": "#06b6d4",
  "Enrolling by invitation": "#8b5cf6",
  Terminated: "#ef4444",
  Withdrawn: "#dc2626",
  Suspended: "#f97316",
};

function formatNumber(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toLocaleString();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 text-center">
      <div
        className="text-2xl font-bold"
        style={{ color: accent || "#0ea5e9" }}
      >
        {typeof value === "number" ? formatNumber(value) : value}
      </div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}

function PhaseBar({ byPhase }: { byPhase: Record<string, number> }) {
  const total = Object.values(byPhase).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const entries = Object.entries(byPhase).filter(([, c]) => c > 0);

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-slate-700 mb-3">
        Phase Distribution
      </h4>
      {/* Stacked bar */}
      <div className="flex rounded-md overflow-hidden h-8 mb-3">
        {entries.map(([phase, count]) => (
          <div
            key={phase}
            style={{
              width: `${(count / total) * 100}%`,
              backgroundColor: PHASE_COLORS[phase] || "#94a3b8",
            }}
            className="flex items-center justify-center text-white text-xs font-medium min-w-[2rem]"
            title={`${phase}: ${count}`}
          >
            {count}
          </div>
        ))}
      </div>
      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {entries.map(([phase, count]) => (
          <div key={phase} className="flex items-center gap-1.5 text-xs">
            <div
              className="w-2.5 h-2.5 rounded-sm"
              style={{
                backgroundColor: PHASE_COLORS[phase] || "#94a3b8",
              }}
            />
            <span className="text-slate-600">
              {phase} ({count})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function YearChart({
  yearDist,
}: {
  yearDist: Record<string, number>;
}) {
  const entries = Object.entries(yearDist).sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return null;
  const maxCount = Math.max(...entries.map(([, c]) => c), 1);
  const barWidth = Math.max(20, Math.min(40, 300 / entries.length));
  const chartW = entries.length * (barWidth + 8) + 40;
  const chartH = 140;
  const barAreaH = 100;

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-slate-700 mb-3">
        Trial Start Year
      </h4>
      <svg
        viewBox={`0 0 ${chartW} ${chartH}`}
        className="w-full"
        style={{ maxHeight: "160px" }}
      >
        {entries.map(([year, count], i) => {
          const x = 20 + i * (barWidth + 8);
          const h = (count / maxCount) * barAreaH;
          const y = barAreaH - h + 10;
          return (
            <g key={year}>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={h}
                rx={3}
                fill="#0ea5e9"
                opacity={0.85}
              />
              <text
                x={x + barWidth / 2}
                y={y - 4}
                textAnchor="middle"
                fill="#334155"
                fontSize={9}
                fontWeight={600}
              >
                {count}
              </text>
              <text
                x={x + barWidth / 2}
                y={chartH - 5}
                textAnchor="middle"
                fill="#64748b"
                fontSize={8}
              >
                {year.slice(-2)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function SponsorList({
  sponsors,
}: {
  sponsors: { name: string; count: number }[];
}) {
  if (sponsors.length === 0) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-slate-700 mb-3">
        Top Sponsors
      </h4>
      <div className="space-y-2">
        {sponsors.slice(0, 8).map((s, i) => (
          <div key={s.name} className="flex items-center text-xs">
            <span className="text-slate-400 w-5 font-medium">{i + 1}.</span>
            <span className="text-slate-700 flex-1 truncate">{s.name}</span>
            <span className="text-cyan-600 font-semibold ml-2">
              {s.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrialCard({ trial }: { trial: ClinicalTrial }) {
  const [expanded, setExpanded] = useState(false);
  const statusColor = STATUS_COLORS[trial.status] || "#6b7280";
  const phaseColor = PHASE_COLORS[trial.phase] || "#94a3b8";

  const locationSummary =
    trial.locations.length > 0
      ? trial.locations
          .slice(0, 3)
          .map((l) => l.city || l.country)
          .filter(Boolean)
          .join(", ") +
        (trial.locations.length > 3
          ? ` (+${trial.locations.length - 3} more)`
          : "")
      : null;

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 hover:border-cyan-200 transition-colors">
      {/* Header row */}
      <div className="flex items-start gap-2 mb-2">
        {/* Phase pill */}
        <span
          className="text-[10px] font-bold px-2 py-0.5 rounded text-white whitespace-nowrap"
          style={{ backgroundColor: phaseColor }}
        >
          {trial.phase}
        </span>
        {/* Status pill */}
        <span
          className="text-[10px] font-bold px-2 py-0.5 rounded text-white whitespace-nowrap"
          style={{ backgroundColor: statusColor }}
        >
          {trial.status}
        </span>
        <span className="text-[10px] text-slate-400 ml-auto whitespace-nowrap">
          {trial.nct_id}
        </span>
      </div>

      {/* Title */}
      <h5 className="text-sm font-semibold text-slate-800 leading-snug line-clamp-2 mb-1.5">
        {trial.title}
      </h5>

      {/* Sponsor */}
      <p className="text-xs text-slate-500 mb-2">{trial.sponsor}</p>

      {/* Key stats */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 mb-2">
        {trial.enrollment > 0 && (
          <span>
            Enrolled: <strong className="text-slate-700">{trial.enrollment.toLocaleString()}</strong>
          </span>
        )}
        {trial.start_date && (
          <span>
            Started: <strong className="text-slate-700">{trial.start_date}</strong>
          </span>
        )}
        {trial.completion_date && (
          <span>
            Est. completion: <strong className="text-slate-700">{trial.completion_date}</strong>
          </span>
        )}
      </div>

      {/* Interventions */}
      {trial.interventions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {trial.interventions.map((iv, j) => (
            <span
              key={j}
              className="text-[10px] bg-cyan-50 text-cyan-700 border border-cyan-200 px-1.5 py-0.5 rounded"
            >
              {iv.name}
            </span>
          ))}
        </div>
      )}

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-cyan-600 hover:text-cyan-800 flex items-center gap-1 mt-1"
      >
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {expanded ? "Less" : "More details"}
      </button>

      {/* Expanded section */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-slate-100 space-y-2">
          {trial.primary_outcomes.length > 0 && (
            <div>
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                Primary Outcome
              </span>
              <p className="text-xs text-slate-600 mt-0.5">
                {trial.primary_outcomes.join("; ")}
              </p>
            </div>
          )}
          {locationSummary && (
            <div>
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                Locations
              </span>
              <p className="text-xs text-slate-600 mt-0.5">
                {locationSummary}
              </p>
            </div>
          )}
          {trial.summary && (
            <div>
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                Summary
              </span>
              <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">
                {trial.summary}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ClinicalTrials.gov link */}
      <a
        href={trial.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-xs text-cyan-600 hover:text-cyan-800 mt-2"
      >
        View on ClinicalTrials.gov <ExternalLink size={10} />
      </a>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function ClinicalTrialsDashboard({
  data,
  loading,
  onSearch,
  gene,
  disease,
}: ClinicalTrialsDashboardProps) {
  // --- Loading state ---
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 py-20">
        <div className="relative">
          <Activity size={32} className="text-cyan-500 animate-pulse" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-slate-700">
            Searching ClinicalTrials.gov...
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Querying condition: {disease || "cancer"}, intervention:{" "}
            {gene || "gene"}
          </p>
        </div>
      </div>
    );
  }

  // --- Empty state ---
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 py-20">
        <div className="w-14 h-14 rounded-full bg-cyan-50 flex items-center justify-center">
          <Search size={24} className="text-cyan-500" />
        </div>
        <div className="text-center max-w-sm">
          <p className="text-sm font-medium text-slate-700">
            Clinical Trials Explorer
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Search ClinicalTrials.gov for trials relevant to your hypothesis.
            {gene && (
              <>
                {" "}
                Ready to search for <strong>{gene}</strong>
                {disease && disease !== "cancer" && (
                  <>
                    {" "}
                    in <strong>{disease}</strong>
                  </>
                )}
                .
              </>
            )}
          </p>
        </div>
        <button
          onClick={onSearch}
          disabled={!gene}
          className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-300 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Search Trials
        </button>
      </div>
    );
  }

  // --- Results state ---
  const { summary, trials, source, query: q } = data;

  const recruitingCount = summary.by_status["Recruiting"] || 0;
  const uniqueSponsors = summary.top_sponsors.length;

  // CSV export
  const handleExportCSV = () => {
    const header =
      "NCT ID,Title,Phase,Status,Sponsor,Enrollment,Start Date,Interventions,URL\n";
    const rows = trials
      .map(
        (t) =>
          `"${t.nct_id}","${t.title.replace(/"/g, '""')}","${t.phase}","${t.status}","${t.sponsor}",${t.enrollment},"${t.start_date}","${t.interventions.map((i) => i.name).join("; ")}","${t.url}"`
      )
      .join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `clinical_trials_${q.gene}_${q.disease}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Copy summary
  const handleCopySummary = () => {
    const text = `Clinical Trials Summary for ${q.gene} in ${q.disease}:
${summary.total_count} total trials found.
${recruitingCount} currently recruiting.
${summary.enrollment_total.toLocaleString()} total enrollment.
Top sponsors: ${summary.top_sponsors.slice(0, 5).map((s) => s.name).join(", ")}.
Phase distribution: ${Object.entries(summary.by_phase).map(([p, c]) => `${p}: ${c}`).join(", ")}.
Source: ClinicalTrials.gov (${source})`;
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Activity size={20} className="text-cyan-500" />
            Clinical Trials
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {summary.total_count} trials for{" "}
            <strong>{q.gene}</strong> in <strong>{q.disease}</strong>
            {trials.length < summary.total_count && (
              <> &middot; Showing {trials.length} most recent</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {source === "fallback" && (
            <span className="flex items-center gap-1 text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-2 py-1 rounded">
              <AlertTriangle size={10} />
              Curated reference data
            </span>
          )}
          <button
            onClick={onSearch}
            className="text-xs text-cyan-600 hover:text-cyan-800 font-medium"
          >
            Re-search
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Total Trials" value={summary.total_count} />
        <StatCard
          label="Recruiting"
          value={recruitingCount}
          accent="#10b981"
        />
        <StatCard
          label="Total Enrollment"
          value={summary.enrollment_total}
        />
        <StatCard
          label="Sponsors"
          value={uniqueSponsors}
          accent="#7c3aed"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <PhaseBar byPhase={summary.by_phase} />
        <YearChart yearDist={summary.year_distribution} />
      </div>

      {/* Sponsors + Interventions row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <SponsorList sponsors={summary.top_sponsors} />
        {summary.top_interventions.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-slate-700 mb-3">
              Top Interventions
            </h4>
            <div className="space-y-2">
              {summary.top_interventions.slice(0, 8).map((iv, i) => (
                <div key={iv.name} className="flex items-center text-xs">
                  <span className="text-slate-400 w-5 font-medium">
                    {i + 1}.
                  </span>
                  <span className="text-slate-700 flex-1 truncate">
                    {iv.name}
                  </span>
                  <span className="text-[10px] text-slate-400 mr-2">
                    {iv.type}
                  </span>
                  <span className="text-cyan-600 font-semibold">
                    {iv.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Trial cards */}
      <div>
        <h4 className="text-sm font-semibold text-slate-700 mb-3">
          Individual Trials
        </h4>
        <div className="space-y-3">
          {trials.map((t) => (
            <TrialCard key={t.nct_id} trial={t} />
          ))}
        </div>
      </div>

      {/* Export actions */}
      <div className="flex items-center gap-3 pt-2 border-t border-slate-200">
        <button
          onClick={handleExportCSV}
          className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-cyan-600 font-medium"
        >
          <Download size={12} />
          Export CSV
        </button>
        <button
          onClick={handleCopySummary}
          className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-cyan-600 font-medium"
        >
          <Copy size={12} />
          Copy Summary
        </button>
      </div>
    </div>
  );
}
