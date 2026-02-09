"use client";

import React, { useState } from "react";
import {
  Target, Shield, Dna, Scale, Activity, Microscope, FileText,
  ChevronDown, ChevronUp, Download, Copy, CheckCircle, XCircle,
  AlertTriangle, TrendingUp, Zap
} from "lucide-react";

interface DossierProps {
  data: any;
  loading: boolean;
  onGenerate: () => void;
  gene?: string;
  disease?: string;
}

// Go/No-Go Score Circle
function ScoreGauge({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const circumference = 2 * Math.PI * 54;
  const dashoffset = circumference * (1 - score);
  const color = score > 0.75 ? "#10b981" : score > 0.6 ? "#3b82f6" : score > 0.45 ? "#f59e0b" : "#ef4444";
  
  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="140" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="54" fill="none" stroke="#e2e8f0" strokeWidth="8" />
        <circle cx="60" cy="60" r="54" fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circumference} strokeDashoffset={dashoffset}
          strokeLinecap="round" transform="rotate(-90 60 60)" className="transition-all duration-1000" />
        <text x="60" y="55" textAnchor="middle" className="text-3xl font-bold" fill={color}>{pct}</text>
        <text x="60" y="72" textAnchor="middle" className="text-[10px] font-medium" fill="#64748b">/ 100</text>
      </svg>
      <span className={`mt-2 px-3 py-1 rounded-full text-sm font-bold ${
        score > 0.75 ? "bg-emerald-100 text-emerald-700" :
        score > 0.6 ? "bg-blue-100 text-blue-700" :
        score > 0.45 ? "bg-amber-100 text-amber-700" :
        "bg-red-100 text-red-700"
      }`}>{label}</span>
    </div>
  );
}

function ScoreBar({ name, score, weight }: { name: string; score: number; weight: number }) {
  const pct = Math.round(score * 100);
  const color = score > 0.7 ? "bg-emerald-500" : score > 0.5 ? "bg-blue-500" : score > 0.3 ? "bg-amber-500" : "bg-red-500";
  
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-500 w-32 text-right capitalize">{name.replace(/_/g, " ")}</span>
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-600 w-10">{pct}%</span>
      <span className="text-[10px] text-slate-400 w-8">{Math.round(weight * 100)}%w</span>
    </div>
  );
}

export default function TargetDossier({ data, loading, onGenerate, gene, disease }: DossierProps) {
  const [copied, setCopied] = useState(false);
  
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <div className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 max-w-md text-center">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <Target className="text-blue-600" size={32} />
          </div>
          <h3 className="text-xl font-bold text-slate-900 mb-2">Target Dossier</h3>
          <p className="text-slate-500 mb-2 text-sm">
            Generate a comprehensive Go/No-Go report for <strong>{gene || "your target"}</strong> in <strong>{disease || "cancer"}</strong>.
          </p>
          <p className="text-xs text-slate-400 mb-6">
            Runs all analyses in parallel: validation, structure, patents, trials, models, and literature.
          </p>
          <button 
            onClick={onGenerate}
            disabled={loading}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-all shadow-md disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <><Activity className="animate-spin" size={18} />Generating Dossier...</>
            ) : (
              <><Zap size={18} />Generate Target Dossier</>
            )}
          </button>
        </div>
      </div>
    );
  }
  
  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <div className="w-full h-full overflow-auto p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">
              Target Dossier: <span className="text-blue-600">{data.gene}</span>
            </h2>
            <p className="text-sm text-slate-500">{data.disease} {data.mutation ? `| ${data.mutation}` : ""}</p>
          </div>
          <button onClick={handleCopy} className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 hover:border-blue-400 rounded-lg text-sm text-slate-600 hover:text-blue-600 transition-all">
            {copied ? <CheckCircle size={14} className="text-emerald-500" /> : <Copy size={14} />}
            {copied ? "Copied" : "Export JSON"}
          </button>
        </div>
        
        {/* Go/No-Go Score */}
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-start gap-8">
            <ScoreGauge score={data.go_no_go_score} label={data.go_no_go_label} />
            <div className="flex-1 space-y-3">
              <h3 className="font-bold text-slate-700 mb-4">Score Breakdown</h3>
              {(data.score_breakdown || []).map((item: any) => (
                <ScoreBar key={item.name} name={item.name} score={item.score} weight={item.weight} />
              ))}
            </div>
          </div>
        </div>
        
        {/* Section Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Validation */}
          {data.sections?.validation && (
            <SectionCard
              icon={<Shield className="text-emerald-500" size={20} />}
              title="Hypothesis Validation"
              score={data.sections.validation.overall_score}
              status={data.sections.validation.overall_status}
            >
              <div className="grid grid-cols-3 gap-2 text-xs">
                {Object.entries(data.sections.validation.checks || {}).map(([key, check]: [string, any]) => (
                  <div key={key} className="bg-slate-50 p-2 rounded text-center">
                    <div className={`text-xs font-bold ${
                      check.status === "pass" ? "text-emerald-600" :
                      check.status === "caution" ? "text-amber-600" : "text-red-600"
                    }`}>{check.status}</div>
                    <div className="text-[10px] text-slate-500 capitalize">{key}</div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
          
          {/* Structure */}
          {data.sections?.structure && (
            <SectionCard
              icon={<Dna className="text-blue-500" size={20} />}
              title="Structural Druggability"
              score={data.sections.structure.druggability_score}
            >
              <div className="text-xs text-slate-600 space-y-1">
                <p>Binding pockets: {data.sections.structure.pockets?.length || 0}</p>
                {data.sections.structure.analysis && (
                  <p>Residues: {data.sections.structure.analysis.residue_count} | pLDDT: {data.sections.structure.analysis.avg_plddt?.toFixed(1)}</p>
                )}
              </div>
            </SectionCard>
          )}
          
          {/* Patents */}
          {data.sections?.patents && (
            <SectionCard
              icon={<Scale className="text-amber-500" size={20} />}
              title="IP Landscape"
              score={1 - (data.sections.patents.scooped_score || 0) / 100}
              status={data.sections.patents.risk_label}
            >
              <div className="text-xs text-slate-600 space-y-1">
                <p>Total patents: {data.sections.patents.total_hits || 0}</p>
                <p>Recent (5yr): {data.sections.patents.recent_filings_5y || 0}</p>
                <p>Competitors: {data.sections.patents.top_competitors?.length || 0}</p>
              </div>
            </SectionCard>
          )}
          
          {/* Trials */}
          {data.sections?.trials && (
            <SectionCard
              icon={<Activity className="text-cyan-500" size={20} />}
              title="Clinical Validation"
              score={Math.min(1, (data.sections.trials.summary?.total_count || 0) / 20)}
            >
              <div className="text-xs text-slate-600 space-y-1">
                <p>Total trials: {data.sections.trials.summary?.total_count || 0}</p>
                {data.sections.trials.summary?.by_phase && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {Object.entries(data.sections.trials.summary.by_phase).map(([phase, count]: [string, any]) => (
                      <span key={phase} className="px-1.5 py-0.5 bg-cyan-50 text-cyan-700 rounded text-[10px]">{phase}: {count}</span>
                    ))}
                  </div>
                )}
              </div>
            </SectionCard>
          )}
          
          {/* Models */}
          {data.sections?.models && (
            <SectionCard
              icon={<Microscope className="text-emerald-500" size={20} />}
              title="Model Availability"
              score={(data.sections.models.top_pick?.match_score || 50) / 100}
            >
              <div className="text-xs text-slate-600 space-y-1">
                {data.sections.models.top_pick && (
                  <p>Top pick: <strong>{data.sections.models.top_pick.name}</strong> ({data.sections.models.top_pick.match_score}%)</p>
                )}
                <p>Total found: {data.sections.models.total_found || 0}</p>
              </div>
            </SectionCard>
          )}
          
          {/* Literature */}
          {data.sections?.papers && (
            <SectionCard
              icon={<FileText className="text-indigo-500" size={20} />}
              title="Literature Coverage"
              score={Math.min(1, (data.sections.papers.length || 0) / 6)}
            >
              <div className="text-xs text-slate-600 space-y-1">
                <p>{data.sections.papers.length || 0} relevant papers found</p>
                {data.sections.papers.slice(0, 2).map((p: any, i: number) => (
                  <p key={i} className="text-[10px] text-slate-400 truncate">{p.title}</p>
                ))}
              </div>
            </SectionCard>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionCard({ icon, title, score, status, children }: {
  icon: React.ReactNode;
  title: string;
  score?: number;
  status?: string;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(true);
  const pct = score !== undefined ? Math.round(score * 100) : null;
  
  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between mb-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-2">
          {icon}
          <h4 className="font-semibold text-slate-700 text-sm">{title}</h4>
        </div>
        <div className="flex items-center gap-2">
          {pct !== null && (
            <span className={`text-xs font-bold ${pct > 70 ? "text-emerald-600" : pct > 50 ? "text-blue-600" : pct > 30 ? "text-amber-600" : "text-red-600"}`}>
              {pct}%
            </span>
          )}
          {status && (
            <span className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded capitalize">{status}</span>
          )}
          {expanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
        </div>
      </div>
      {expanded && <div className="mt-2">{children}</div>}
    </div>
  );
}
