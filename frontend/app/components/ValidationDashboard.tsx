"use client";

import { useState } from "react";
import { 
  CheckCircle, XCircle, AlertTriangle, HelpCircle,
  ChevronDown, ChevronUp, Download, Copy,
  Activity, Heart, Pill, Users, Target, FileText
} from "lucide-react";

/**
 * ValidationDashboard - v2 Features UI
 * 
 * Design principles (from Saloni's guide):
 * - Horizontal text only
 * - Direct labeling (no separate legends)
 * - Colors match meaning (green=good, red=bad, yellow=caution)
 * - Progressive disclosure (summary → details)
 * - Standalone context (each card explains itself)
 */

interface ValidationCheck {
  status: "pass" | "caution" | "fail" | "unknown";
  score: number;
  title: string;
  subtitle?: string;
  summary: string;
  metric?: {
    name: string;
    value: number | string;
    interpretation: string;
  };
  details?: Record<string, any>;
}

interface ValidationData {
  gene: string;
  disease: string;
  overall_score: number;
  overall_status: string;
  checks: {
    essentiality: ValidationCheck;
    survival: ValidationCheck;
    toxicity: ValidationCheck;
    drugability: ValidationCheck;
    biomarker: ValidationCheck;
    competition: ValidationCheck;
  };
  synthesis: {
    text: string;
    generated_by: string;
    exportable: boolean;
  };
}

interface Props {
  data: ValidationData | null;
  loading: boolean;
  onRun: () => void;
  gene?: string;
  disease?: string;
}

// Status badge component with semantic colors
function StatusBadge({ status }: { status: string }) {
  const config = {
    pass: { bg: "bg-emerald-100", text: "text-emerald-700", icon: CheckCircle, label: "Pass" },
    caution: { bg: "bg-amber-100", text: "text-amber-700", icon: AlertTriangle, label: "Caution" },
    fail: { bg: "bg-red-100", text: "text-red-700", icon: XCircle, label: "Concern" },
    unknown: { bg: "bg-slate-100", text: "text-slate-500", icon: HelpCircle, label: "Unknown" },
  }[status] || { bg: "bg-slate-100", text: "text-slate-500", icon: HelpCircle, label: "Unknown" };

  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      <Icon size={12} />
      {config.label}
    </span>
  );
}

// Score ring visualization
function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  
  const color = score >= 70 ? "#10b981" : score >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="6"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-2xl font-bold text-slate-800">{score}</span>
      </div>
    </div>
  );
}

// Individual validation card with expandable details
function ValidationCard({ 
  check, 
  icon: Icon,
  defaultExpanded = false 
}: { 
  check: ValidationCheck; 
  icon: React.ElementType;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const borderColor = {
    pass: "border-l-emerald-500",
    caution: "border-l-amber-500",
    fail: "border-l-red-500",
    unknown: "border-l-slate-300",
  }[check.status];

  return (
    <div className={`bg-white rounded-lg border border-slate-200 border-l-4 ${borderColor} overflow-hidden`}>
      {/* Header - Always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-slate-100 rounded-lg">
            <Icon size={18} className="text-slate-600" />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-slate-800 text-sm">{check.title}</h4>
              <StatusBadge status={check.status} />
            </div>
            <p className="text-xs text-slate-500 mt-0.5">{check.summary}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {check.metric && (
            <div className="text-right">
              <p className="text-lg font-bold text-slate-800">{check.metric.value}</p>
              <p className="text-[10px] text-slate-400">{check.metric.name}</p>
            </div>
          )}
          {expanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>

      {/* Details - Expandable */}
      {expanded && check.details && (
        <div className="px-4 pb-4 pt-2 border-t border-slate-100 bg-slate-50/50">
          {/* Metric interpretation */}
          {check.metric && (
            <p className="text-xs text-slate-500 mb-3">
              <span className="font-medium">Interpretation:</span> {check.metric.interpretation}
            </p>
          )}

          {/* Chart data - render if available */}
          {check.details.chart_data && (
            <div className="mb-3">
              {check.details.chart_data.type === "kaplan_meier" && (
                <KaplanMeierMini data={check.details.chart_data} />
              )}
              {check.details.chart_data.type === "boxplot" && (
                <BoxPlotMini data={check.details.chart_data} />
              )}
              {check.details.chart_data.type === "bar" && (
                <BarChartMini data={check.details.chart_data} />
              )}
            </div>
          )}

          {/* Additional details as key-value pairs */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(check.details).map(([key, value]) => {
              if (key === "chart_data" || key === "source" || key === "note") return null;
              if (typeof value === "object" && !Array.isArray(value)) return null;
              
              const displayValue = Array.isArray(value) 
                ? value.slice(0, 3).join(", ") + (value.length > 3 ? "..." : "")
                : String(value);
              
              const formattedKey = key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
              
              return (
                <div key={key} className="bg-white p-2 rounded border border-slate-100">
                  <span className="text-slate-500">{formattedKey}</span>
                  <p className="font-medium text-slate-700 truncate" title={displayValue}>{displayValue}</p>
                </div>
              );
            })}
          </div>

          {/* Source note */}
          {(check.details.source || check.details.note) && (
            <p className="text-[10px] text-slate-400 mt-2 italic">
              {check.details.source || check.details.note}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// Mini Kaplan-Meier chart (following Saloni's direct labeling principle)
function KaplanMeierMini({ data }: { data: any }) {
  const width = 280;
  const height = 120;
  const padding = { top: 10, right: 80, bottom: 25, left: 35 };
  
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  return (
    <div className="bg-white p-2 rounded border border-slate-100">
      <svg width={width} height={height} className="overflow-visible">
        {/* Y axis */}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#e2e8f0" />
        <text x={padding.left - 5} y={padding.top} textAnchor="end" className="text-[9px] fill-slate-400">100%</text>
        <text x={padding.left - 5} y={height - padding.bottom} textAnchor="end" className="text-[9px] fill-slate-400">0%</text>
        
        {/* X axis */}
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#e2e8f0" />
        <text x={width / 2} y={height - 5} textAnchor="middle" className="text-[9px] fill-slate-400">
          {data.x_label || "Time"}
        </text>

        {/* Curves with direct labels */}
        {data.curves?.map((curve: any, i: number) => {
          const points = curve.data.map((d: any, j: number) => {
            const x = padding.left + (d.time / 60) * innerWidth;
            const y = padding.top + ((100 - d.survival) / 100) * innerHeight;
            return `${j === 0 ? 'M' : 'L'} ${x} ${y}`;
          }).join(' ');

          const lastPoint = curve.data[curve.data.length - 1];
          const labelX = padding.left + (lastPoint.time / 60) * innerWidth + 5;
          const labelY = padding.top + ((100 - lastPoint.survival) / 100) * innerHeight;

          return (
            <g key={i}>
              <path d={points} fill="none" stroke={curve.color} strokeWidth="2" />
              {/* Direct label instead of legend */}
              <text 
                x={labelX} 
                y={labelY} 
                className="text-[9px] font-medium"
                fill={curve.color}
              >
                {curve.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// Mini box plot
function BoxPlotMini({ data }: { data: any }) {
  return (
    <div className="bg-white p-2 rounded border border-slate-100">
      <div className="flex items-end gap-4 h-20">
        {data.groups?.map((group: any, i: number) => {
          const values = group.values || [];
          const median = values.length ? values.sort((a: number, b: number) => a - b)[Math.floor(values.length / 2)] : 0;
          const normalizedHeight = Math.min(100, Math.max(10, Math.abs(median) * 30 + 50));
          
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <div 
                className="w-full rounded-t"
                style={{ 
                  height: `${normalizedHeight}%`,
                  backgroundColor: group.color 
                }}
              />
              <span className="text-[9px] text-slate-600 text-center">{group.name}</span>
            </div>
          );
        })}
      </div>
      {data.reference_line && (
        <p className="text-[9px] text-slate-400 mt-1 text-center">
          Threshold: {data.reference_line.value} ({data.reference_line.label})
        </p>
      )}
    </div>
  );
}

// Mini horizontal bar chart (for toxicity)
function BarChartMini({ data }: { data: any }) {
  const maxValue = Math.max(...(data.data?.map((d: any) => d.value) || [10]));
  
  return (
    <div className="bg-white p-2 rounded border border-slate-100 space-y-1">
      {data.data?.slice(0, 6).map((item: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-[9px] text-slate-500 w-20 truncate text-right" title={item.tissue}>
            {item.tissue}
          </span>
          <div className="flex-1 h-3 bg-slate-100 rounded overflow-hidden">
            <div 
              className="h-full rounded"
              style={{ 
                width: `${(item.value / maxValue) * 100}%`,
                backgroundColor: item.color 
              }}
            />
          </div>
          <span className="text-[9px] text-slate-600 w-8">{item.value}</span>
        </div>
      ))}
      {data.threshold && (
        <p className="text-[9px] text-slate-400 mt-1">
          Red = vital tissue above threshold ({data.threshold.value} TPM)
        </p>
      )}
    </div>
  );
}

// Main Dashboard Component
export default function ValidationDashboard({ data, loading, onRun, gene, disease }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (data?.synthesis?.text) {
      navigator.clipboard.writeText(data.synthesis.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Empty state
  if (!data && !loading) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-100 to-purple-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Target className="w-10 h-10 text-blue-600" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-2">Target Validation</h3>
          <p className="text-slate-500 mb-6">
            Run comprehensive validation checks to assess if your target is essential, clinically relevant, safe, and tractable.
          </p>
          <button
            onClick={onRun}
            disabled={!gene}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl font-medium transition-all shadow-lg shadow-blue-500/20 disabled:shadow-none flex items-center gap-2 mx-auto"
          >
            <Activity size={18} />
            Run Validation
          </button>
          {!gene && (
            <p className="text-xs text-slate-400 mt-3">Search for a target first</p>
          )}
        </div>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-600 font-medium">Running validation checks...</p>
          <p className="text-xs text-slate-400 mt-1">Querying DepMap, TCGA, GTEx, ClinicalTrials.gov</p>
        </div>
      </div>
    );
  }

  // Results
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        
        {/* Header with overall score */}
        <div className="flex items-center justify-between bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">
              {data?.gene} <span className="text-slate-400 font-normal">in</span> {data?.disease}
            </h2>
            <p className="text-slate-500 mt-1">Target Validation Report</p>
          </div>
          <div className="flex items-center gap-6">
            <ScoreRing score={data?.overall_score || 0} />
            <div className="text-right">
              <p className="text-sm text-slate-500">Overall Score</p>
              <StatusBadge status={data?.overall_status || "unknown"} />
            </div>
          </div>
        </div>

        {/* Quick Summary - Traffic Light Row */}
        <div className="grid grid-cols-6 gap-2">
          {[
            { key: "essentiality", label: "Essential", icon: "E" },
            { key: "survival", label: "Prognostic", icon: "S" },
            { key: "toxicity", label: "Safe", icon: "T" },
            { key: "drugability", label: "Druggable", icon: "D" },
            { key: "biomarker", label: "Context", icon: "B" },
            { key: "competition", label: "Novel", icon: "C" },
          ].map(({ key, label }) => {
            const check = data?.checks?.[key as keyof typeof data.checks];
            const bgColor = {
              pass: "bg-emerald-500",
              caution: "bg-amber-500",
              fail: "bg-red-500",
              unknown: "bg-slate-300",
            }[check?.status || "unknown"];

            return (
              <div key={key} className="text-center">
                <div className={`w-full h-2 rounded-full ${bgColor}`} />
                <p className="text-[10px] text-slate-500 mt-1">{label}</p>
              </div>
            );
          })}
        </div>

        {/* Validation Cards - 2 columns */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data?.checks?.essentiality && (
            <ValidationCard check={data.checks.essentiality} icon={Target} />
          )}
          {data?.checks?.survival && (
            <ValidationCard check={data.checks.survival} icon={Activity} />
          )}
          {data?.checks?.toxicity && (
            <ValidationCard check={data.checks.toxicity} icon={Heart} />
          )}
          {data?.checks?.drugability && (
            <ValidationCard check={data.checks.drugability} icon={Pill} />
          )}
          {data?.checks?.biomarker && (
            <ValidationCard check={data.checks.biomarker} icon={FileText} />
          )}
          {data?.checks?.competition && (
            <ValidationCard check={data.checks.competition} icon={Users} />
          )}
        </div>

        {/* Synthesis / Rationale */}
        {data?.synthesis && (
          <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-6 border border-blue-100">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-slate-800">Scientific Rationale</h3>
                <p className="text-xs text-slate-500">
                  {data.synthesis.generated_by === "LLM" ? "AI-Generated Summary" : "Template-Based Summary"}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCopy}
                  className="p-2 hover:bg-white/50 rounded-lg transition-colors"
                  title="Copy to clipboard"
                >
                  <Copy size={16} className={copied ? "text-emerald-500" : "text-slate-500"} />
                </button>
                <button
                  className="p-2 hover:bg-white/50 rounded-lg transition-colors"
                  title="Export as PDF"
                >
                  <Download size={16} className="text-slate-500" />
                </button>
              </div>
            </div>
            <p className="text-slate-700 leading-relaxed">
              {data.synthesis.text}
            </p>
          </div>
        )}

        {/* Re-run button */}
        <div className="text-center pt-4">
          <button
            onClick={onRun}
            className="text-sm text-slate-500 hover:text-blue-600 transition-colors"
          >
            Re-run validation with updated parameters
          </button>
        </div>
      </div>
    </div>
  );
}
