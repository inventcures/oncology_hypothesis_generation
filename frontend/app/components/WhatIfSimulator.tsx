"use client";

import React, { useState, useMemo } from "react";
import { Zap, Activity, ArrowDown, ArrowUp, Minus, Target, AlertTriangle, RotateCcw } from "lucide-react";

interface AffectedNode {
  id: string;
  label: string;
  type: string;
  effect: number;
  direction: string;
}

interface PathwayEffect {
  pathway: string;
  net_effect: number;
  description: string;
}

interface SimulationResult {
  target_node: string;
  perturbation_type: string;
  total_affected: number;
  affected_nodes: AffectedNode[];
  pathway_effects: PathwayEffect[];
  graph?: any;
}

interface WhatIfProps {
  result: SimulationResult | null;
  loading: boolean;
  availableNodes: { id: string; label: string; type: string }[];
  onSimulate: (targetNode: string, perturbationType: string) => void;
  onReset: () => void;
}

export default function WhatIfSimulator({ result, loading, availableNodes, onSimulate, onReset }: WhatIfProps) {
  const [selectedNode, setSelectedNode] = useState("");
  const [perturbationType, setPerturbationType] = useState<"inhibit" | "activate" | "knockout">("inhibit");
  
  const geneNodes = useMemo(() => 
    availableNodes.filter(n => n.type.toLowerCase() === "gene" || n.type.toLowerCase() === "target"),
    [availableNodes]
  );
  
  const handleRun = () => {
    if (selectedNode) {
      onSimulate(selectedNode, perturbationType);
    }
  };
  
  return (
    <div className="w-full h-full overflow-auto">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Controls */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2">
            <Zap className="text-amber-500" size={20} />
            What-If Perturbation Simulator
          </h3>
          <p className="text-sm text-slate-500 mb-4">
            Select a target gene and perturbation type to simulate downstream effects through the knowledge graph.
            This is a qualitative network analysis, not a quantitative ODE model.
          </p>
          
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="text-xs text-slate-500 block mb-1">Target Gene</label>
              <select
                value={selectedNode}
                onChange={(e) => setSelectedNode(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-amber-500 focus:border-transparent"
              >
                <option value="">Select a gene...</option>
                {geneNodes.map(n => (
                  <option key={n.id} value={n.id}>{n.label || n.id}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="text-xs text-slate-500 block mb-1">Perturbation</label>
              <div className="flex gap-1">
                {(["inhibit", "activate", "knockout"] as const).map(type => (
                  <button
                    key={type}
                    onClick={() => setPerturbationType(type)}
                    className={`px-3 py-2 text-xs rounded-lg font-medium capitalize transition-all ${
                      perturbationType === type
                        ? type === "inhibit" ? "bg-red-100 text-red-700 ring-1 ring-red-300"
                        : type === "activate" ? "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-300"
                        : "bg-slate-800 text-white"
                        : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>
            
            <button
              onClick={handleRun}
              disabled={!selectedNode || loading}
              className="px-6 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-medium text-sm transition-all disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? <Activity className="animate-spin" size={16} /> : <Zap size={16} />}
              Simulate
            </button>
            
            {result && (
              <button
                onClick={onReset}
                className="px-3 py-2 text-slate-500 hover:text-slate-700 transition-colors"
                title="Reset"
              >
                <RotateCcw size={16} />
              </button>
            )}
          </div>
        </div>
        
        {/* Results */}
        {result && (
          <>
            {/* Summary */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-semibold text-slate-700">
                  {result.perturbation_type === "inhibit" ? "Inhibiting" : result.perturbation_type === "activate" ? "Activating" : "Knocking out"}{" "}
                  <span className="text-amber-600">{result.target_node}</span>
                </h4>
                <span className="text-xs text-slate-400">{result.total_affected} nodes affected</span>
              </div>
              
              {/* Pathway Effects */}
              {result.pathway_effects.length > 0 && (
                <div className="mb-4">
                  <h5 className="text-xs font-semibold text-slate-500 uppercase mb-2">Pathway Impact</h5>
                  <div className="space-y-2">
                    {result.pathway_effects.map((pe, i) => (
                      <div key={i} className={`p-3 rounded-lg border text-sm ${
                        pe.net_effect < 0 ? "bg-red-50 border-red-200" : "bg-emerald-50 border-emerald-200"
                      }`}>
                        <div className="flex items-center gap-2">
                          {pe.net_effect < 0 ? <ArrowDown size={14} className="text-red-500" /> : <ArrowUp size={14} className="text-emerald-500" />}
                          <span className="font-medium text-slate-700">{pe.pathway}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">{pe.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            {/* Affected Nodes */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-slate-100">
                <h4 className="font-semibold text-slate-700 text-sm">Affected Nodes</h4>
              </div>
              <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
                {result.affected_nodes.map((node, i) => (
                  <div key={node.id} className="flex items-center gap-3 px-5 py-3">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                      node.effect < -0.3 ? "bg-red-100" : node.effect < 0 ? "bg-red-50" :
                      node.effect > 0.3 ? "bg-emerald-100" : "bg-emerald-50"
                    }`}>
                      {node.effect < 0 ? <ArrowDown size={12} className="text-red-500" /> : <ArrowUp size={12} className="text-emerald-500" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-800">{node.label}</p>
                      <p className="text-[10px] text-slate-400 capitalize">{node.type}</p>
                    </div>
                    <div className="w-24">
                      <div className="flex items-center gap-1">
                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden relative">
                          <div
                            className={`h-full rounded-full absolute ${node.effect < 0 ? "bg-red-400 right-1/2" : "bg-emerald-400 left-1/2"}`}
                            style={{ width: `${Math.abs(node.effect) * 50}%` }}
                          />
                          <div className="absolute left-1/2 top-0 w-px h-full bg-slate-300" />
                        </div>
                      </div>
                    </div>
                    <span className={`text-xs font-mono w-14 text-right ${
                      node.effect < 0 ? "text-red-600" : "text-emerald-600"
                    }`}>
                      {node.effect > 0 ? "+" : ""}{(node.effect * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
        
        {!result && !loading && (
          <div className="text-center py-12 text-slate-400">
            <AlertTriangle size={48} className="mx-auto mb-4 opacity-20" />
            <p className="text-sm">Select a gene target above and run a simulation</p>
            <p className="text-xs mt-1">Results will show predicted downstream effects</p>
          </div>
        )}
      </div>
    </div>
  );
}
