"use client";

import React, { useState, useMemo } from "react";
import { Activity, Scale, TrendingUp, Users, ExternalLink, AlertTriangle, BarChart3, Target } from "lucide-react";

interface CompetitiveDashboardProps {
  trialsData: any;
  patentData: any;
  gene?: string;
  disease?: string;
}

export default function CompetitiveDashboard({ trialsData, patentData, gene, disease }: CompetitiveDashboardProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "trials" | "patents" | "whitespace">("overview");
  
  const trials = trialsData?.trials || [];
  const trialsSummary = trialsData?.summary || {};
  const patents = patentData || {};
  
  // Compute combined metrics
  const totalTrials = trialsSummary.total_count || 0;
  const totalPatents = patents.total_hits || 0;
  const scoopedScore = patents.scooped_score || 0;
  const topSponsors = trialsSummary.top_sponsors || [];
  const topCompetitors = patents.top_competitors || [];
  
  // Merge competitors from both sources
  const allCompetitors = useMemo(() => {
    const map = new Map<string, { trials: number; patents: number }>();
    topSponsors.forEach((s: any) => {
      const name = s.name.toLowerCase().split(' ')[0]; // normalize
      const existing = map.get(name) || { trials: 0, patents: 0 };
      existing.trials += s.count;
      map.set(name, existing);
    });
    topCompetitors.forEach((c: any) => {
      const name = c.name.toLowerCase().split(' ')[0];
      const existing = map.get(name) || { trials: 0, patents: 0 };
      existing.patents += c.count;
      map.set(name, existing);
    });
    return Array.from(map.entries())
      .map(([name, data]) => ({ name, ...data, total: data.trials + data.patents }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  }, [topSponsors, topCompetitors]);
  
  // White space analysis: modalities with no trials
  const knownModalities = ["Small Molecule", "Antibody", "ADC", "Cell Therapy", "Gene Therapy", "Vaccine", "Degrader/PROTAC", "Bispecific"];
  const trialModalities = new Set(
    trials.flatMap((t: any) => (t.interventions || []).map((i: any) => i.type))
  );
  const whiteSpaces = knownModalities.filter(m => !trialModalities.has(m));
  
  // Phase distribution
  const phaseData = trialsSummary.by_phase || {};
  
  // Competitive density score (0-100)
  const competitiveDensity = Math.min(100, Math.round(
    (totalTrials * 1.5 + totalPatents * 0.5 + scoopedScore * 0.3)
  ));
  
  if (!trialsData && !patentData) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-slate-400">
          <BarChart3 size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm">Run Trials and Feasibility analyses first</p>
          <p className="text-xs mt-1">Then return here for competitive intelligence</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="w-full h-full overflow-auto">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">
            Competitive Landscape: <span className="text-blue-600">{gene}</span> {disease ? `in ${disease}` : ""}
          </h2>
          <p className="text-sm text-slate-500">Combined clinical trials and patent intelligence</p>
        </div>
        
        {/* Key Metrics Row */}
        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="Active Trials" value={totalTrials} icon={<Activity className="text-cyan-500" size={20} />} color="cyan" />
          <MetricCard label="Patents Filed" value={totalPatents} icon={<Scale className="text-amber-500" size={20} />} color="amber" />
          <MetricCard label="Competitors" value={allCompetitors.length} icon={<Users className="text-violet-500" size={20} />} color="violet" />
          <MetricCard
            label="Competition"
            value={`${competitiveDensity}/100`}
            icon={<TrendingUp className={competitiveDensity > 60 ? "text-red-500" : competitiveDensity > 30 ? "text-amber-500" : "text-emerald-500"} size={20} />}
            color={competitiveDensity > 60 ? "red" : competitiveDensity > 30 ? "amber" : "emerald"}
          />
        </div>
        
        {/* Tab Navigation */}
        <div className="flex gap-1 bg-white rounded-lg border border-slate-200 p-1">
          {(["overview", "trials", "patents", "whitespace"] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors capitalize ${
                activeTab === tab ? "bg-blue-50 text-blue-600 shadow-sm" : "text-slate-500 hover:bg-slate-50"
              }`}
            >
              {tab === "whitespace" ? "White Space" : tab}
            </button>
          ))}
        </div>
        
        {/* Tab Content */}
        {activeTab === "overview" && (
          <div className="grid grid-cols-2 gap-6">
            {/* Phase Distribution */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-700 mb-4">Trial Phase Distribution</h3>
              <div className="space-y-3">
                {Object.entries(phaseData).map(([phase, count]: [string, any]) => {
                  const maxCount = Math.max(...Object.values(phaseData).map(Number));
                  return (
                    <div key={phase} className="flex items-center gap-3">
                      <span className="text-xs text-slate-500 w-20">{phase}</span>
                      <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${(count / maxCount) * 100}%` }} />
                      </div>
                      <span className="text-xs font-mono text-slate-600 w-8">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
            
            {/* Top Competitors */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-700 mb-4">Top Competitors</h3>
              <div className="space-y-2">
                {allCompetitors.slice(0, 8).map((comp, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0">
                    <span className="text-sm text-slate-700 capitalize">{comp.name}</span>
                    <div className="flex gap-3 text-xs">
                      {comp.trials > 0 && <span className="text-cyan-600">{comp.trials} trials</span>}
                      {comp.patents > 0 && <span className="text-amber-600">{comp.patents} patents</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Patent Heatmap */}
            {patents.heatmap && patents.heatmap.length > 0 && (
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm col-span-2">
                <h3 className="font-semibold text-slate-700 mb-4">Patent Filing Activity</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr>
                        <th className="text-left p-2 text-slate-500">Assignee</th>
                        {patents.heatmap[0]?.data?.map((d: any) => (
                          <th key={d.year} className="text-center p-2 text-slate-500 w-12">{d.year.slice(2)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {patents.heatmap.map((row: any, i: number) => (
                        <tr key={i}>
                          <td className="p-2 text-slate-600 truncate max-w-[100px]" title={row.name}>{row.name}</td>
                          {row.data.map((cell: any, j: number) => {
                            const intensity = Math.min(1, cell.count / 5);
                            return (
                              <td key={j} className="p-1">
                                <div className="w-full h-7 rounded flex items-center justify-center text-[10px] font-medium"
                                  style={{ backgroundColor: intensity > 0 ? `rgba(245, 158, 11, ${0.15 + intensity * 0.85})` : '#f1f5f9', color: intensity > 0.5 ? 'white' : '#64748b' }}>
                                  {cell.count > 0 ? cell.count : ''}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
        
        {activeTab === "trials" && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="max-h-[500px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 sticky top-0">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs text-slate-500">Trial</th>
                    <th className="text-left px-4 py-3 text-xs text-slate-500">Phase</th>
                    <th className="text-left px-4 py-3 text-xs text-slate-500">Status</th>
                    <th className="text-left px-4 py-3 text-xs text-slate-500">Sponsor</th>
                    <th className="text-left px-4 py-3 text-xs text-slate-500">Enrolled</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trials.slice(0, 30).map((trial: any) => (
                    <tr key={trial.nct_id} className="hover:bg-slate-50">
                      <td className="px-4 py-3">
                        <a href={trial.url} target="_blank" rel="noopener" className="text-blue-600 hover:underline text-xs font-medium flex items-center gap-1">
                          {trial.nct_id} <ExternalLink size={10} />
                        </a>
                        <p className="text-xs text-slate-500 truncate max-w-xs" title={trial.title}>{trial.title}</p>
                      </td>
                      <td className="px-4 py-3 text-xs">{trial.phase}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          trial.status?.includes("Recruiting") ? "bg-emerald-100 text-emerald-700" :
                          trial.status?.includes("Completed") ? "bg-blue-100 text-blue-700" :
                          "bg-slate-100 text-slate-600"
                        }`}>{trial.status}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600 truncate max-w-[120px]">{trial.sponsor}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{trial.enrollment || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        
        {activeTab === "patents" && (
          <div className="space-y-4">
            <div className={`p-6 rounded-xl border-2 ${
              scoopedScore > 70 ? 'bg-red-50 border-red-200' :
              scoopedScore > 40 ? 'bg-amber-50 border-amber-200' :
              'bg-green-50 border-green-200'
            }`}>
              <div className="flex justify-between items-center mb-2">
                <span className="font-medium text-slate-700">IP Competition Score</span>
                <span className={`text-3xl font-bold ${
                  scoopedScore > 70 ? 'text-red-600' : scoopedScore > 40 ? 'text-amber-600' : 'text-green-600'
                }`}>{scoopedScore}<span className="text-sm">/100</span></span>
              </div>
              <div className="h-3 bg-white/50 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${scoopedScore > 70 ? 'bg-red-500' : scoopedScore > 40 ? 'bg-amber-500' : 'bg-green-500'}`}
                  style={{ width: `${scoopedScore}%` }} />
              </div>
              <p className="text-xs text-slate-500 mt-2">{patents.risk_label}: {patents.risk_assessment || patents.message}</p>
            </div>
            
            {patents.sample_patents && patents.sample_patents.length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                <h3 className="font-semibold text-slate-700 mb-3">Recent Patent Filings</h3>
                <div className="space-y-2">
                  {patents.sample_patents.map((p: any, i: number) => (
                    <div key={i} className="p-3 bg-slate-50 rounded-lg">
                      <p className="text-sm text-slate-700">{p.title}</p>
                      <p className="text-xs text-slate-400 mt-1">{p.assignee} | {p.date}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        
        {activeTab === "whitespace" && (
          <div className="space-y-4">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-700 mb-2 flex items-center gap-2">
                <Target className="text-emerald-500" size={20} />
                First-in-Class Opportunities
              </h3>
              <p className="text-xs text-slate-500 mb-4">Modalities with no active clinical trials for {gene} in {disease}</p>
              
              {whiteSpaces.length > 0 ? (
                <div className="grid grid-cols-2 gap-3">
                  {whiteSpaces.map(modality => (
                    <div key={modality} className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                        <span className="font-medium text-emerald-800 text-sm">{modality}</span>
                      </div>
                      <p className="text-xs text-emerald-600">No active trials found</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-center">
                  <AlertTriangle className="text-amber-500 mx-auto mb-2" size={24} />
                  <p className="text-sm text-amber-700">Crowded space — all major modalities are being explored</p>
                </div>
              )}
            </div>
            
            {/* Modalities in play */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-700 mb-3">Active Modalities</h3>
              <div className="flex flex-wrap gap-2">
                {Array.from(trialModalities).map((mod: any) => (
                  <span key={mod} className="px-3 py-1.5 bg-cyan-50 text-cyan-700 rounded-full text-xs font-medium">{mod}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon, color }: { label: string; value: number | string; icon: React.ReactNode; color: string }) {
  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        {icon}
        <span className={`text-2xl font-bold text-${color}-600`}>{value}</span>
      </div>
      <span className="text-xs text-slate-500">{label}</span>
    </div>
  );
}
