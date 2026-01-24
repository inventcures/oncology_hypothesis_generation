"use client";

import { useState } from "react";
import { Send, Activity, Brain, ShieldCheck, Microscope, BarChart3, Network, Table as TableIcon, FileText, Sparkles, Search, ArrowRight } from "lucide-react";

type Hypothesis = {
  id: string;
  title: string;
  description: string;
  confidence: number;
  verified: boolean;
  novelty_score: number;
};

type Paper = {
  id: string;
  title: string;
  abstract: string;
  authors: string;
  year: number;
  citations: number;
  journal: string;
  url: string;
  source: string;
};

type GraphNode = {
  id: string;
  type: string;
  x: number;
  y: number;
};

type GraphLink = {
  source: string;
  target: string;
  relation: string;
  weight: number;
};

export default function Home() {
  const [query, setQuery] = useState("");
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [status, setStatus] = useState("Idle");
  const [viewMode, setViewMode] = useState<"graph" | "table" | "metrics" | "papers">("graph");

  const handleSubmit = async (e?: React.FormEvent, overrideQuery?: string) => {
    if (e) e.preventDefault();
    const textToSearch = overrideQuery || query;
    if (!textToSearch) return;

    if (overrideQuery) setQuery(overrideQuery);
    
    setLoading(true);
    setHasSearched(true);
    setHypotheses([]);
    setGraphData(null);
    setPapers([]);
    setStatus("Initializing TTT Adaptation...");

    try {
      // Simulate TTT phases
      setTimeout(() => setStatus("ARK Exploring Knowledge Graph..."), 1000);
      setTimeout(() => setStatus("LitAgent Searching Papers..."), 2500);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiUrl}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textToSearch }),
      });
      
      if (!res.ok) throw new Error(`API Error: ${res.statusText}`);

      const data = await res.json();
      setHypotheses(data.hypotheses);
      setGraphData(data.graph_context);
      setPapers(data.papers || []);
      setStatus("Complete");
    } catch (error) {
      console.error(error);
      setStatus("Error: " + String(error));
    } finally {
      setLoading(false);
    }
  };

  const handleExampleClick = (text: string) => {
    handleSubmit(undefined, text);
  };

  const getNodeColor = (type: string) => {
    switch (type) {
      case "Gene": return "#3b82f6"; // Blue
      case "Disease": return "#ef4444"; // Red
      case "Drug": return "#10b981"; // Green
      case "Mechanism": return "#8b5cf6"; // Purple
      default: return "#9ca3af";
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-slate-50 text-slate-900 font-sans">
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-4 bg-white border-b border-slate-200 shadow-sm z-20 sticky top-0">
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => setHasSearched(false)}>
          <div className="bg-blue-600 p-1.5 rounded-lg">
             <Activity className="text-white w-5 h-5" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-800">Onco-TTT</h1>
        </div>
        
        {hasSearched && (
            <div className="flex gap-6 text-sm font-medium">
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${status.includes("ARK") ? "bg-blue-500 animate-pulse" : "bg-green-500"}`}></div>
                <span className="text-slate-600">ARK Agent</span>
            </div>
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${status.includes("MEDEA") ? "bg-amber-500 animate-pulse" : "bg-green-500"}`}></div>
                <span className="text-slate-600">MEDEA Verifier</span>
            </div>
            </div>
        )}
      </header>

      {!hasSearched ? (
        // --- HERO SECTION (Initial View) ---
        <div className="flex-1 flex flex-col items-center justify-center p-6 -mt-20">
            <div className="w-full max-w-3xl text-center space-y-8">
                
                <div className="space-y-4">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-sm font-medium border border-blue-100">
                        <Sparkles size={14} />
                        <span>Powered by Test-Time Training & OpenTargets</span>
                    </div>
                    <h2 className="text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        Discover Hidden <br/> 
                        <span className="text-blue-600">Oncology Mechanisms</span>
                    </h2>
                    <p className="text-lg text-slate-500 max-w-2xl mx-auto">
                        An AI agent that adapts to your specific query in real-time. 
                        Generate verified hypotheses, visualize pathways, and validate with literature.
                    </p>
                </div>

                {/* Big Search Bar */}
                <div className="relative max-w-2xl mx-auto group">
                    <div className="absolute inset-0 bg-blue-500 rounded-2xl blur opacity-20 group-hover:opacity-30 transition-opacity"></div>
                    <div className="relative bg-white rounded-2xl shadow-xl border border-slate-200 flex items-center p-2 transition-all ring-1 ring-slate-900/5 focus-within:ring-2 focus-within:ring-blue-500">
                        <Search className="ml-4 text-slate-400" size={24} />
                        <input 
                            type="text" 
                            className="flex-1 bg-transparent border-none focus:ring-0 text-lg p-4 placeholder:text-slate-400 text-slate-800"
                            placeholder="Describe a clinical phenomenon or resistance pattern..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                            autoFocus
                        />
                        <button 
                            onClick={() => handleSubmit()}
                            disabled={!query}
                            className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <ArrowRight size={20} />
                        </button>
                    </div>
                </div>

                {/* Suggested Queries */}
                <div className="pt-8">
                    <p className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Try exploring</p>
                    <div className="flex flex-wrap justify-center gap-3">
                        {[
                            "KRAS G12C resistance mechanisms",
                            "STK11 loss in Lung Adenocarcinoma",
                            "Role of YAP1 in immunotherapy failure",
                            "EGFR T790M bypass tracks"
                        ].map((q) => (
                            <button
                                key={q}
                                onClick={() => handleExampleClick(q)}
                                className="px-4 py-2 bg-white border border-slate-200 hover:border-blue-400 hover:text-blue-600 rounded-full text-sm font-medium text-slate-600 transition-all shadow-sm hover:shadow-md"
                            >
                                {q}
                            </button>
                        ))}
                    </div>
                </div>

            </div>
        </div>
      ) : (
        // --- MAIN APP (Split View) ---
        <div className="flex flex-1 overflow-hidden">
        {/* Sidebar / Feed */}
        <aside className="w-[350px] bg-white border-r border-slate-200 flex flex-col z-10 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
          <div className="p-4 border-b border-slate-100">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Refine Query</h2>
            <form onSubmit={(e) => handleSubmit(e)}>
              <div className="relative group">
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Refine your research question..."
                  className="w-full h-24 p-3 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:outline-none resize-none transition-all"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="absolute bottom-2 right-2 p-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-all shadow-sm"
                >
                  <Send size={14} />
                </button>
              </div>
            </form>
          </div>

          <div className="flex-1 overflow-y-auto p-4 bg-slate-50/50">
            <div className="flex items-center justify-between mb-4">
                 <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Live Feed
                </h3>
                {status !== "Idle" && status !== "Complete" && (
                  <span className="text-xs text-blue-600 font-mono animate-pulse">{status}</span>
                )}
            </div>

            {status.startsWith("Error") && (
                 <div className="p-4 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm mb-4">
                    {status}
                 </div>
            )}

            <div className="space-y-4">
              {hypotheses.map((h) => (
                <div
                  key={h.id}
                  className="group relative p-5 rounded-xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition-all cursor-pointer overflow-hidden"
                >
                  <div className="absolute top-0 left-0 w-1 h-full bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"/>
                  
                  <div className="flex justify-between items-start mb-3">
                    <h4 className="font-semibold text-slate-800 leading-snug pr-2">{h.title}</h4>
                    {h.verified ? (
                      <ShieldCheck className="text-emerald-500 shrink-0" size={18} />
                    ) : (
                      <Brain className="text-amber-500 shrink-0" size={18} />
                    )}
                  </div>
                  
                  <p className="text-sm text-slate-600 leading-relaxed mb-4">
                    {h.description}
                  </p>
                  
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{width: `${h.confidence * 100}%`}} />
                    </div>
                    <span className="text-xs font-medium text-slate-500">{(h.confidence * 100).toFixed(0)}% Conf.</span>
                  </div>
                </div>
              ))}
              
              {hypotheses.length === 0 && !loading && (
                <div className="text-center py-12">
                   <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Microscope className="text-slate-300" size={32} />
                   </div>
                   <p className="text-sm text-slate-400">
                     Awaiting input to begin exploration.
                   </p>
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Main Canvas Area */}
        <section className="flex-1 flex flex-col relative bg-white">
            {/* Toolbar */}
            <div className="absolute top-4 left-6 z-10 flex gap-1 bg-white/80 backdrop-blur-md border border-slate-200 p-1 rounded-lg shadow-sm">
                <button 
                    onClick={() => setViewMode("graph")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "graph" ? "bg-blue-50 text-blue-600 shadow-sm" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <Network size={16} />
                    <span>Graph</span>
                </button>
                <div className="w-px bg-slate-200 my-1 mx-1"></div>
                <button 
                    onClick={() => setViewMode("table")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "table" ? "bg-blue-50 text-blue-600 shadow-sm" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <TableIcon size={16} />
                    <span>Table</span>
                </button>
                <button 
                    onClick={() => setViewMode("metrics")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "metrics" ? "bg-blue-50 text-blue-600 shadow-sm" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <BarChart3 size={16} />
                    <span>Metrics</span>
                </button>
                <button 
                    onClick={() => setViewMode("papers")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "papers" ? "bg-blue-50 text-blue-600 shadow-sm" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <FileText size={16} />
                    <span>Papers</span>
                </button>
            </div>

            <div className="flex-1 relative overflow-hidden flex items-center justify-center bg-slate-50/30">
                {/* Background Grid */}
                <div className="absolute inset-0 grid grid-cols-[repeat(40,minmax(0,1fr))] opacity-[0.03] pointer-events-none">
                    {Array.from({ length: 1600 }).map((_, i) => (
                    <div key={i} className="border-r border-b border-slate-900" />
                    ))}
                </div>
            
                {graphData ? (
                    <>
                        {viewMode === "graph" && (
                            <svg className="w-full h-full" viewBox="0 0 800 600">
                                <defs>
                                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="28" refY="3.5" orient="auto">
                                    <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />
                                </marker>
                                </defs>
                                {/* Links with Labels */}
                                {graphData.links.map((link, i) => {
                                const source = graphData.nodes.find(n => n.id === link.source);
                                const target = graphData.nodes.find(n => n.id === link.target);
                                if (!source || !target) return null;
                                return (
                                    <g key={i}>
                                    <line
                                        x1={source.x}
                                        y1={source.y}
                                        x2={target.x}
                                        y2={target.y}
                                        stroke="#cbd5e1"
                                        strokeWidth={1.5}
                                        markerEnd="url(#arrowhead)"
                                    />
                                    {/* Edge Label Background */}
                                    <rect 
                                        x={(source.x + target.x)/2 - 20} 
                                        y={(source.y + target.y)/2 - 10} 
                                        width="40" 
                                        height="14" 
                                        rx="4" 
                                        fill="white" 
                                        opacity="0.8"
                                    />
                                    {/* Edge Label Text */}
                                    <text 
                                        x={(source.x + target.x)/2} 
                                        y={(source.y + target.y)/2} 
                                        textAnchor="middle" 
                                        dominantBaseline="middle"
                                        className="text-[9px] fill-slate-400 font-mono"
                                    >
                                        {(link.weight * 100).toFixed(0)}%
                                    </text>
                                    </g>
                                );
                                })}
                                {/* Nodes with Tooltips */}
                                {graphData.nodes.map((node) => (
                                <g key={node.id} transform={`translate(${node.x},${node.y})`} className="group relative">
                                    <circle
                                    r={24}
                                    fill={getNodeColor(node.type)}
                                    className="cursor-pointer transition-all duration-300 drop-shadow-md group-hover:drop-shadow-xl"
                                    stroke="white"
                                    strokeWidth={3}
                                    />
                                    
                                    {/* Node Label */}
                                    <text
                                    dy={45}
                                    textAnchor="middle"
                                    className="text-[10px] font-bold fill-slate-500 uppercase tracking-wider pointer-events-none select-none"
                                    >
                                    {node.id}
                                    </text>
                                    
                                    {/* Icon / Type Label */}
                                    <text
                                    dy={5}
                                    textAnchor="middle"
                                    fill="white"
                                    fontSize="11"
                                    fontWeight="bold"
                                    pointer-events="none"
                                    >
                                    {node.type.slice(0, 2).toUpperCase()}
                                    </text>

                                    {/* Tooltip (Pure CSS/SVG Implementation) */}
                                    <foreignObject x="-80" y="-80" width="160" height="60" className="opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                        <div className="bg-slate-800 text-white text-xs rounded-lg py-2 px-3 shadow-xl text-center">
                                            <p className="font-bold mb-0.5">{node.id}</p>
                                            <p className="text-slate-300 text-[10px]">{node.type}</p>
                                            <div className="absolute bottom-[-4px] left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-800 rotate-45"></div>
                                        </div>
                                    </foreignObject>
                                </g>
                                ))}
                            </svg>
                        )}

                        {viewMode === "table" && (
                            <div className="w-full h-full p-12 overflow-auto">
                                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden max-w-5xl mx-auto">
                                    <div className="p-6 border-b border-slate-100 bg-slate-50/50">
                                        <h3 className="text-lg font-bold text-slate-800">Entity Evidence Table</h3>
                                        <p className="text-sm text-slate-500 mt-1">
                                            Below are the biological entities (Genes, Diseases, Drugs) identified by the <strong>ARK Agent</strong> as relevant to your query. 
                                            The coordinates represent their position in the TTT embedding space.
                                        </p>
                                    </div>
                                    <table className="w-full text-sm text-left">
                                        <thead className="bg-slate-50 border-b border-slate-200">
                                            <tr>
                                                <th className="px-6 py-4 font-semibold text-slate-700 w-1/3">Entity Name</th>
                                                <th className="px-6 py-4 font-semibold text-slate-700 w-1/4">Type</th>
                                                <th className="px-6 py-4 font-semibold text-slate-700">Relevance Context</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {graphData.nodes.map((n) => (
                                                <tr key={n.id} className="hover:bg-slate-50/50 transition-colors">
                                                    <td className="px-6 py-4 font-medium text-slate-900">{n.id}</td>
                                                    <td className="px-6 py-4">
                                                        <span 
                                                            className="px-2.5 py-1 rounded-full text-xs font-semibold text-white shadow-sm"
                                                            style={{backgroundColor: getNodeColor(n.type)}}
                                                        >
                                                            {n.type}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 text-slate-500 text-xs">
                                                        {/* Contextual help based on type */}
                                                        {n.type === 'Gene' && `Potential driver or target in ${query.split(' ')[0]} context.`}
                                                        {n.type === 'Disease' && `Clinical condition associated with retrieved targets.`}
                                                        {n.type === 'Drug' && `Therapeutic agent interacting with this pathway.`}
                                                        {n.type === 'Mechanism' && `Biological process implicated in resistance.`}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {viewMode === "metrics" && (
                            <div className="w-full h-full p-24 flex items-center justify-center">
                                <div className="grid grid-cols-2 gap-6 w-full max-w-4xl">
                                    <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
                                        <h3 className="text-lg font-bold text-slate-800 mb-6">Hypothesis Confidence</h3>
                                        <div className="space-y-4">
                                            {hypotheses.map(h => (
                                                <div key={h.id}>
                                                    <div className="flex justify-between text-sm mb-1">
                                                        <span className="font-medium text-slate-700">{h.title}</span>
                                                        <span className="text-slate-500">{(h.confidence * 100).toFixed(0)}%</span>
                                                    </div>
                                                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                                        <div className="h-full bg-blue-600 rounded-full" style={{width: `${h.confidence * 100}%`}} />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
                                        <h3 className="text-lg font-bold text-slate-800 mb-6">Novelty Scores</h3>
                                        <div className="space-y-4">
                                            {hypotheses.map(h => (
                                                <div key={h.id}>
                                                    <div className="flex justify-between text-sm mb-1">
                                                        <span className="font-medium text-slate-700">{h.title}</span>
                                                        <span className="text-slate-500">{(h.novelty_score * 100).toFixed(0)}%</span>
                                                    </div>
                                                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                                        <div className="h-full bg-purple-600 rounded-full" style={{width: `${h.novelty_score * 100}%`}} />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {viewMode === "papers" && (
                            <div className="w-full h-full p-12 overflow-auto">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">
                                    {papers.map((p) => (
                                        <div key={p.id} className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow flex flex-col h-full">
                                            <div className="mb-4">
                                                <span className="inline-block px-2 py-1 mb-2 text-xs font-semibold text-blue-600 bg-blue-50 rounded-md">
                                                    {p.year}
                                                </span>
                                                <h3 className="text-md font-bold text-slate-900 leading-snug line-clamp-2" title={p.title}>
                                                    {p.title}
                                                </h3>
                                                <p className="text-xs text-slate-500 mt-1">{p.authors}</p>
                                            </div>
                                            
                                            <p className="text-sm text-slate-600 mb-4 line-clamp-4 flex-1">
                                                {p.abstract}
                                            </p>
                                            
                                            <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                                                <span className="font-medium text-slate-700 truncate max-w-[120px]" title={p.journal}>{p.journal}</span>
                                                <div className="flex gap-3">
                                                    <span className="text-slate-500">{p.citations} Cites</span>
                                                    {p.url && (
                                                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-medium">
                                                            Read PDF
                                                        </a>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                    {papers.length === 0 && (
                                        <div className="col-span-full text-center py-20 text-slate-400">
                                            <FileText size={48} className="mx-auto mb-4 opacity-20" />
                                            <p>No papers found. Try a different query.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="text-center">
                        <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
                            <Microscope size={40} className="text-slate-300" />
                        </div>
                        <h3 className="text-xl font-semibold text-slate-900 mb-2">Ready to Explore</h3>
                        <p className="text-slate-500 max-w-sm mx-auto">
                            Enter a query on the left to activate the TTT engine and visualize the discovery process.
                        </p>
                    </div>
                )}
            </div>
        </section>
      </div>
      )}
    </main>
  );
}
