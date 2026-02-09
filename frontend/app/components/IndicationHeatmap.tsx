"use client";

import React, { useState } from "react";
import { Target, TrendingUp, Activity, AlertTriangle } from "lucide-react";

interface Indication {
  disease: string;
  disease_id: string;
  score: number;
  entity_type: string;
}

interface IndicationHeatmapProps {
  data: { gene: string; indications: Indication[]; total: number } | null;
  loading: boolean;
  onFetch: () => void;
  gene?: string;
}

export default function IndicationHeatmap({ data, loading, onFetch, gene }: IndicationHeatmapProps) {
  const [sortBy, setSortBy] = useState<"score" | "name">("score");
  
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <div className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 max-w-md text-center">
          <div className="w-16 h-16 bg-violet-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <TrendingUp className="text-violet-600" size={32} />
          </div>
          <h3 className="text-xl font-bold text-slate-900 mb-2">Indication Explorer</h3>
          <p className="text-slate-500 mb-6 text-sm">
            Discover which diseases are most strongly associated with <strong>{gene || "your target"}</strong> across OpenTargets evidence.
          </p>
          <button 
            onClick={onFetch}
            disabled={loading}
            className="w-full py-3 bg-violet-600 hover:bg-violet-700 text-white rounded-xl font-medium transition-all shadow-md disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <><Activity className="animate-spin" size={18} />Searching...</>
            ) : (
              <><Target size={18} />Explore Indications</>
            )}
          </button>
        </div>
      </div>
    );
  }
  
  const sorted = [...(data.indications || [])].sort((a, b) =>
    sortBy === "score" ? b.score - a.score : a.disease.localeCompare(b.disease)
  );
  
  const maxScore = sorted.length > 0 ? sorted[0].score : 1;
  
  return (
    <div className="w-full h-full overflow-auto p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">
              Indication Expansion: <span className="text-violet-600">{data.gene}</span>
            </h2>
            <p className="text-sm text-slate-500">{data.total} associated diseases from OpenTargets</p>
          </div>
          <div className="flex gap-2 text-xs">
            <button 
              onClick={() => setSortBy("score")}
              className={`px-3 py-1.5 rounded-lg ${sortBy === "score" ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-500"}`}
            >By Evidence</button>
            <button 
              onClick={() => setSortBy("name")}
              className={`px-3 py-1.5 rounded-lg ${sortBy === "name" ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-500"}`}
            >Alphabetical</button>
          </div>
        </div>
        
        {/* Heatmap Grid */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="divide-y divide-slate-100">
            {sorted.map((ind, i) => {
              const intensity = maxScore > 0 ? ind.score / maxScore : 0;
              return (
                <div key={ind.disease_id || i} className="flex items-center gap-4 px-5 py-3 hover:bg-slate-50 transition-colors">
                  <span className="text-xs text-slate-400 w-6 text-right font-mono">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{ind.disease}</p>
                    <p className="text-[10px] text-slate-400">{ind.disease_id}</p>
                  </div>
                  <div className="w-48 h-4 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${intensity * 100}%`,
                        backgroundColor: intensity > 0.7 ? "#7c3aed" : intensity > 0.4 ? "#8b5cf6" : intensity > 0.2 ? "#a78bfa" : "#c4b5fd",
                      }}
                    />
                  </div>
                  <span className="text-xs font-mono text-slate-600 w-14 text-right">{(ind.score * 100).toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
