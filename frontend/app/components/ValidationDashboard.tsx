"use client";

import { useState } from "react";
import { 
  CheckCircle, XCircle, AlertTriangle, HelpCircle,
  ChevronDown, ChevronUp, Download, Copy,
  Activity, Heart, Pill, Users, Target, FileText,
  Shield, Microscope, Stethoscope, BookOpen, ExternalLink
} from "lucide-react";
import { ValidationData, ValidationCheck, FidelityLevel, ValidationMetric } from "../types";

// ... existing helper components ...

function FidelityBadge({ level }: { level: FidelityLevel }) {
  const config = {
    [FidelityLevel.L1_PLAUSIBILITY]: { icon: BookOpen, label: "L1: Plausibility", color: "text-slate-500", bg: "bg-slate-100" },
    [FidelityLevel.L2_TECHNICAL_FIT]: { icon: Microscope, label: "L2: Technical", color: "text-blue-500", bg: "bg-blue-100" },
    [FidelityLevel.L3_BIOLOGICAL_FIT]: { icon: Shield, label: "L3: Biological", color: "text-purple-500", bg: "bg-purple-100" },
    [FidelityLevel.L4_臨床_FIT]: { icon: Stethoscope, label: "L4: Clinical", color: "text-emerald-500", bg: "bg-emerald-100" },
  }[level] || { icon: HelpCircle, label: "Unknown", color: "text-slate-400", bg: "bg-slate-50" };

  const Icon = config.icon;
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-transparent shadow-sm ${config.bg} ${config.color}`}>
      <Icon size={14} />
      <span className="text-xs font-bold uppercase tracking-wider">{config.label}</span>
    </div>
  );
}

// ... existing ScoreRing ...

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
          {check.metrics?.length > 0 && (
            <div className="text-right">
              <p className="text-lg font-bold text-slate-800">{check.metrics[0].value}</p>
              <p className="text-[10px] text-slate-400">{check.metrics[0].name}</p>
            </div>
          )}
          {expanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>

      {/* Details - Expandable */}
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-slate-100 bg-slate-50/50">
          {/* All Metrics */}
          <div className="space-y-3">
            {check.metrics?.map((m, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <p className="text-xs text-slate-500">
                  <span className="font-bold text-slate-700">{m.name}:</span> {m.interpretation}
                </p>
                <FidelityBadge level={m.fidelity} />
              </div>
            ))}
          </div>

          {/* Additional details as key-value pairs */}
          {check.details && Object.keys(check.details).length > 0 && (
            <div className="grid grid-cols-2 gap-2 text-xs mt-3">
              {Object.entries(check.details).map(([key, value]) => {
                if (key === "chart_data" || key === "source" || key === "note") return null;
                const formattedKey = key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                return (
                  <div key={key} className="bg-white p-2 rounded border border-slate-100">
                    <span className="text-slate-500">{formattedKey}</span>
                    <p className="font-medium text-slate-700 truncate">{String(value)}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ... KaplanMeierMini, BoxPlotMini, BarChartMini components ...

// Main Dashboard Component
export default function ValidationDashboard({ data, loading, onRun, gene, disease }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (data?.synthesis) {
      navigator.clipboard.writeText(data.synthesis);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // ... Empty and Loading states ...

  // Results
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        
        {/* Header with overall score and fidelity */}
        <div className="flex items-center justify-between bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">
              {data?.gene} <span className="text-slate-400 font-normal">in</span> {data?.disease}
            </h2>
            <div className="flex items-center gap-3 mt-1">
              <p className="text-sm text-slate-500">Target Validation Report</p>
              {data && <FidelityBadge level={data.fidelity_reached} />}
            </div>
          </div>
          <div className="flex items-center gap-6">
            <ScoreRing score={data?.overall_score || 0} />
            <div className="text-right">
              <p className="text-sm text-slate-500">Overall Score</p>
              <StatusBadge status={data?.overall_status || "unknown"} />
            </div>
          </div>
        </div>

        {/* Validation Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data && Object.values(data.checks).map((check, idx) => (
            <ValidationCard key={idx} check={check} icon={Activity} />
          ))}
        </div>

        {/* Synthesis / Rationale */}
        {data?.synthesis && (
          <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-6 border border-blue-100">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-slate-800">Evidence-Grounded Rationale</h3>
                <p className="text-xs text-slate-500 uppercase tracking-tight">ADRS Reliable Verifier Output</p>
              </div>
              <div className="flex gap-2">
                <button onClick={handleCopy} className="p-2 hover:bg-white/50 rounded-lg">
                  <Copy size={16} className={copied ? "text-emerald-500" : "text-slate-500"} />
                </button>
              </div>
            </div>
            <p className="text-slate-700 leading-relaxed text-sm">
              {data.synthesis}
            </p>
            {data.evidence_links?.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {data.evidence_links.map((link, i) => (
                  <a key={i} href={link} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[10px] bg-white px-2 py-1 rounded border border-blue-200 text-blue-600 hover:bg-blue-50">
                    <ExternalLink size={10} />
                    View Data Source
                  </a>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

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
