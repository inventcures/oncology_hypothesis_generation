"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { Send, Activity, Brain, ShieldCheck, Microscope, BarChart3, Network, Table as TableIcon, FileText, Sparkles, Search, ArrowRight, FlaskConical, Scale, Dna, FileEdit, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

// Dynamically import MolstarViewer to avoid SSR issues
const MolstarViewer = dynamic(() => import("./components/MolstarViewer"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-slate-900 rounded-lg">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-slate-400 text-sm">Loading 3D Viewer...</p>
      </div>
    </div>
  ),
});

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
  const [viewMode, setViewMode] = useState<"graph" | "table" | "metrics" | "papers" | "deep_research">("graph");
  const [drData, setDrData] = useState<any>(null);
  const [drLoading, setDrLoading] = useState(false);

  const handleDeepResearch = async () => {
    if (!graphData || graphData.nodes.length === 0) return;
    
    // Naive heuristic: Pick the first Gene node as the target
    const targetNode = graphData.nodes.find(n => n.type === 'Gene') || graphData.nodes[0];
    const diseaseNode = graphData.nodes.find(n => n.type === 'Disease') || { id: "Cancer" };
    
    // Extract mutation from query if present (e.g., "G12C", "V600E")
    const mutationMatch = query.match(/([A-Z]\d+[A-Z])/i);
    const mutation = mutationMatch ? mutationMatch[1].toUpperCase() : null;
    
    setDrLoading(true);
    try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://backend-production-baa6.up.railway.app";
        
        // Build structure URL with mutation if present
        const structureUrl = mutation 
            ? `${apiUrl}/structure/${targetNode.id}?mutation=${mutation}`
            : `${apiUrl}/structure/${targetNode.id}`;
        
        // Parallel Fetching
        const [structRes, patentRes, modelRes, protoRes] = await Promise.all([
            fetch(structureUrl),
            fetch(`${apiUrl}/patents/check?gene=${targetNode.id}&disease=${diseaseNode.id}`),
            fetch(`${apiUrl}/models/recommend?tissue=Lung&mutation=${mutation || targetNode.id}`),
            fetch(`${apiUrl}/protocols/generate?method=crispr&gene=${targetNode.id}&cell_line=A549`)
        ]);

        const struct = await structRes.json();
        const patent = await patentRes.json();
        const models = await modelRes.json();
        const proto = await protoRes.json();

        setDrData({ struct, patent, models, proto, target: targetNode.id, mutation });
    } catch (e) {
        console.error("Deep Research Failed", e);
    } finally {
        setDrLoading(false);
    }
  };

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

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://backend-production-baa6.up.railway.app";
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
                <div className="w-px bg-slate-200 my-1 mx-1"></div>
                <button 
                    onClick={() => setViewMode("deep_research")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "deep_research" ? "bg-purple-50 text-purple-600 shadow-sm border border-purple-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <FlaskConical size={16} />
                    <span>Deep Research</span>
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
                            <>
                                {/* Graph Legend */}
                                <div className="absolute top-4 right-6 bg-white/90 p-3 rounded-lg border border-slate-200 shadow-sm text-xs space-y-2 z-10">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                                        <span className="text-slate-600 font-medium">Gene / Target</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-red-500"></span>
                                        <span className="text-slate-600 font-medium">Disease / Phenotype</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="w-8 h-[2px] bg-slate-300"></span>
                                        <span className="text-slate-600 font-medium">Assoc. Strength</span>
                                    </div>
                                </div>

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
                            <div className="w-full h-full p-12 flex flex-col items-center justify-center">
                                <div className="max-w-4xl w-full mb-8 text-center">
                                    <h3 className="text-2xl font-bold text-slate-800 mb-2">Hypothesis Evaluation Metrics</h3>
                                    <p className="text-slate-500">
                                        Comparison of generated hypotheses based on two key metrics: 
                                        <strong> Confidence</strong> (Probability of biological validity based on known evidence) and 
                                        <strong> Novelty</strong> (Degree of un-exploration in current literature).
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 gap-8 w-full max-w-5xl">
                                    {/* Confidence Card */}
                                    <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
                                        <div className="absolute top-0 right-0 p-4 opacity-5">
                                            <ShieldCheck size={120} />
                                        </div>
                                        <h3 className="text-lg font-bold text-slate-800 mb-2 flex items-center gap-2">
                                            <ShieldCheck className="text-blue-500" size={20} />
                                            Biological Confidence
                                        </h3>
                                        <p className="text-xs text-slate-400 mb-6">
                                            How strongly is this supported by existing knowledge graphs (OpenTargets) and expression data?
                                        </p>
                                        <div className="space-y-6">
                                            {hypotheses.map(h => (
                                                <div key={h.id}>
                                                    <div className="flex justify-between text-sm mb-2 font-medium">
                                                        <span className="text-slate-700 truncate pr-4">{h.title}</span>
                                                        <span className="text-blue-600">{(h.confidence * 100).toFixed(0)}%</span>
                                                    </div>
                                                    <div className="h-3 bg-slate-100 rounded-full overflow-hidden relative">
                                                        <div 
                                                            className="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full transition-all duration-1000" 
                                                            style={{width: `${h.confidence * 100}%`}} 
                                                        />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Novelty Card */}
                                    <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
                                        <div className="absolute top-0 right-0 p-4 opacity-5">
                                            <Sparkles size={120} />
                                        </div>
                                        <h3 className="text-lg font-bold text-slate-800 mb-2 flex items-center gap-2">
                                            <Sparkles className="text-purple-500" size={20} />
                                            Novelty Score
                                        </h3>
                                        <p className="text-xs text-slate-400 mb-6">
                                            How surprising or unexplored is this link? High scores indicate potential for new discovery.
                                        </p>
                                        <div className="space-y-6">
                                            {hypotheses.map(h => (
                                                <div key={h.id}>
                                                    <div className="flex justify-between text-sm mb-2 font-medium">
                                                        <span className="text-slate-700 truncate pr-4">{h.title}</span>
                                                        <span className="text-purple-600">{(h.novelty_score * 100).toFixed(0)}%</span>
                                                    </div>
                                                    <div className="h-3 bg-slate-100 rounded-full overflow-hidden relative">
                                                        <div 
                                                            className="h-full bg-gradient-to-r from-purple-400 to-purple-600 rounded-full transition-all duration-1000" 
                                                            style={{width: `${h.novelty_score * 100}%`}} 
                                                        />
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

                        {viewMode === "deep_research" && (
                            <div className="w-full h-full p-12 overflow-auto bg-slate-50/50">
                                {!drData ? (
                                    <div className="flex flex-col items-center justify-center h-full">
                                        <div className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 max-w-md text-center">
                                            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-6">
                                                <FlaskConical className="text-purple-600" size={32} />
                                            </div>
                                            <h3 className="text-xl font-bold text-slate-900 mb-2">Deep Feasibility Check</h3>
                                            <p className="text-slate-500 mb-8">
                                                Analyze structural druggability, patent landscape, and cell line availability for the identified targets.
                                            </p>
                                            <button 
                                                onClick={handleDeepResearch}
                                                disabled={drLoading}
                                                className="w-full py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium transition-all shadow-md disabled:opacity-50 flex items-center justify-center gap-2"
                                            >
                                                {drLoading ? (
                                                    <>
                                                        <Activity className="animate-spin" size={18} />
                                                        Running Analysis...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Sparkles size={18} />
                                                        Run Deep Research
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="max-w-7xl mx-auto space-y-6">
                                        <div className="flex items-center justify-between">
                                            <h2 className="text-2xl font-bold text-slate-800">Feasibility Report: <span className="text-blue-600">{drData.target}</span></h2>
                                            <button onClick={() => setDrData(null)} className="text-sm text-slate-500 hover:text-slate-800">Reset Analysis</button>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                            {/* Module A: Structure */}
                                            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm col-span-2">
                                                <div className="flex items-center justify-between mb-4">
                                                    <div className="flex items-center gap-2">
                                                        <Dna className="text-blue-500" />
                                                        <h3 className="font-bold text-slate-700">Virtual Structural Biologist</h3>
                                                    </div>
                                                    {drData.struct.uniprot_id && (
                                                        <a 
                                                            href={drData.struct.pdb_url} 
                                                            target="_blank" 
                                                            className="text-xs text-blue-600 hover:underline"
                                                        >
                                                            Download PDB
                                                        </a>
                                                    )}
                                                </div>
                                                
                                                <div className="grid grid-cols-2 gap-4">
                                                    {/* 3D Viewer */}
                                                    <div className="aspect-square bg-slate-900 rounded-lg overflow-hidden">
                                                        {drData.struct.pdb_content ? (
                                                            <MolstarViewer
                                                                pdbContent={drData.struct.pdb_content}
                                                                pockets={drData.struct.pockets || []}
                                                                mutationAnalysis={drData.struct.mutation_analysis}
                                                                bindingResidues={drData.struct.binding_site_residues || []}
                                                            />
                                                        ) : drData.struct.error ? (
                                                            <div className="w-full h-full flex items-center justify-center">
                                                                <div className="text-center p-4">
                                                                    <XCircle className="w-12 h-12 text-red-400 mx-auto mb-2" />
                                                                    <p className="text-red-400 text-sm">{drData.struct.error}</p>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            <div className="w-full h-full flex items-center justify-center">
                                                                <p className="text-slate-500">No structure data</p>
                                                            </div>
                                                        )}
                                                    </div>
                                                    
                                                    {/* Analysis Panel */}
                                                    <div className="space-y-4">
                                                        {/* Druggability Score */}
                                                        <div className="bg-slate-50 p-4 rounded-lg">
                                                            <div className="flex justify-between items-center mb-2">
                                                                <span className="text-sm font-medium text-slate-600">Overall Druggability</span>
                                                                <span className={`px-2 py-1 text-xs font-bold rounded-md ${
                                                                    drData.struct.druggability_score > 0.7 
                                                                        ? 'bg-green-100 text-green-700' 
                                                                        : drData.struct.druggability_score > 0.5 
                                                                            ? 'bg-blue-100 text-blue-700'
                                                                            : 'bg-amber-100 text-amber-700'
                                                                }`}>
                                                                    {(drData.struct.druggability_score * 100).toFixed(0)}%
                                                                </span>
                                                            </div>
                                                            <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                                                                <div 
                                                                    className={`h-full rounded-full ${
                                                                        drData.struct.druggability_score > 0.7 
                                                                            ? 'bg-green-500' 
                                                                            : drData.struct.druggability_score > 0.5 
                                                                                ? 'bg-blue-500'
                                                                                : 'bg-amber-500'
                                                                    }`}
                                                                    style={{ width: `${drData.struct.druggability_score * 100}%` }}
                                                                />
                                                            </div>
                                                        </div>
                                                        
                                                        {/* Binding Pockets */}
                                                        <div>
                                                            <h4 className="text-sm font-semibold text-slate-700 mb-2">
                                                                Predicted Binding Pockets ({drData.struct.pockets?.length || 0})
                                                            </h4>
                                                            <div className="space-y-2 max-h-32 overflow-y-auto">
                                                                {drData.struct.pockets?.slice(0, 3).map((pocket: any, i: number) => (
                                                                    <div key={pocket.id} className="flex items-center justify-between p-2 bg-slate-50 rounded text-xs">
                                                                        <div className="flex items-center gap-2">
                                                                            <span 
                                                                                className="w-3 h-3 rounded-full" 
                                                                                style={{ backgroundColor: pocket.color }}
                                                                            />
                                                                            <span className="text-slate-600">{pocket.name}</span>
                                                                        </div>
                                                                        <span className={`font-medium ${
                                                                            pocket.druggability_label === 'High' ? 'text-green-600' :
                                                                            pocket.druggability_label === 'Medium' ? 'text-blue-600' : 'text-amber-600'
                                                                        }`}>
                                                                            {pocket.druggability_label}
                                                                        </span>
                                                                    </div>
                                                                ))}
                                                                {(!drData.struct.pockets || drData.struct.pockets.length === 0) && (
                                                                    <p className="text-xs text-slate-400 italic">No binding pockets detected</p>
                                                                )}
                                                            </div>
                                                        </div>
                                                        
                                                        {/* Mutation Analysis */}
                                                        {drData.struct.mutation_analysis && (
                                                            <div className="bg-red-50 p-3 rounded-lg border border-red-100">
                                                                <h4 className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-1">
                                                                    <AlertTriangle className="w-4 h-4" />
                                                                    Mutation: {drData.mutation}
                                                                </h4>
                                                                {drData.struct.mutation_analysis.found ? (
                                                                    <div className="space-y-1 text-xs">
                                                                        <p className="text-slate-600">
                                                                            Position: Residue {drData.struct.mutation_analysis.position}
                                                                        </p>
                                                                        <p className={`font-medium ${
                                                                            drData.struct.mutation_analysis.in_binding_pocket 
                                                                                ? 'text-red-600' 
                                                                                : 'text-slate-600'
                                                                        }`}>
                                                                            {drData.struct.mutation_analysis.impact_assessment}
                                                                        </p>
                                                                        <div className="flex items-center gap-2 mt-2">
                                                                            <span className="text-slate-500">Impact Score:</span>
                                                                            <div className="flex-1 h-1.5 bg-red-100 rounded-full">
                                                                                <div 
                                                                                    className="h-full bg-red-500 rounded-full"
                                                                                    style={{ width: `${drData.struct.mutation_analysis.impact_score * 100}%` }}
                                                                                />
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                ) : (
                                                                    <p className="text-xs text-slate-500">
                                                                        {drData.struct.mutation_analysis.message || "Mutation position not found in structure"}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        )}
                                                        
                                                        {/* Structure Stats */}
                                                        {drData.struct.analysis && (
                                                            <div className="grid grid-cols-2 gap-2 text-xs">
                                                                <div className="bg-slate-50 p-2 rounded">
                                                                    <span className="text-slate-500">Residues</span>
                                                                    <p className="font-semibold text-slate-700">{drData.struct.analysis.residue_count}</p>
                                                                </div>
                                                                <div className="bg-slate-50 p-2 rounded">
                                                                    <span className="text-slate-500">Avg pLDDT</span>
                                                                    <p className="font-semibold text-slate-700">{drData.struct.analysis.avg_plddt?.toFixed(1)}</p>
                                                                </div>
                                                                <div className="bg-slate-50 p-2 rounded col-span-2">
                                                                    <span className="text-slate-500">High Confidence Regions</span>
                                                                    <p className="font-semibold text-slate-700">{drData.struct.analysis.high_confidence_pct?.toFixed(0)}% of structure</p>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Module B: Patents */}
                                            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm col-span-2">
                                                <div className="flex items-center justify-between mb-4">
                                                    <div className="flex items-center gap-2">
                                                        <Scale className="text-amber-500" />
                                                        <h3 className="font-bold text-slate-700">Patent Hawk - Freedom to Operate</h3>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <a href={drData.patent.google_patents_link} target="_blank" className="text-xs text-blue-600 hover:underline">Google Patents</a>
                                                        <span className="text-slate-300">|</span>
                                                        <a href={drData.patent.lens_link} target="_blank" className="text-xs text-blue-600 hover:underline">Lens.org</a>
                                                    </div>
                                                </div>
                                                
                                                <div className="grid grid-cols-2 gap-4">
                                                    {/* Risk Assessment */}
                                                    <div className="space-y-4">
                                                        {/* Scooped Score */}
                                                        <div className={`p-4 rounded-lg border-2 ${
                                                            drData.patent.risk_color === 'red' ? 'bg-red-50 border-red-200' :
                                                            drData.patent.risk_color === 'amber' ? 'bg-amber-50 border-amber-200' :
                                                            drData.patent.risk_color === 'yellow' ? 'bg-yellow-50 border-yellow-200' :
                                                            'bg-green-50 border-green-200'
                                                        }`}>
                                                            <div className="flex justify-between items-center mb-2">
                                                                <span className="text-sm font-medium text-slate-600">Scooped Score</span>
                                                                <span className={`text-2xl font-bold ${
                                                                    drData.patent.risk_color === 'red' ? 'text-red-600' :
                                                                    drData.patent.risk_color === 'amber' ? 'text-amber-600' :
                                                                    drData.patent.risk_color === 'yellow' ? 'text-yellow-600' :
                                                                    'text-green-600'
                                                                }`}>
                                                                    {drData.patent.scooped_score}
                                                                    <span className="text-sm">/100</span>
                                                                </span>
                                                            </div>
                                                            <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                                                                <div 
                                                                    className={`h-full rounded-full ${
                                                                        drData.patent.risk_color === 'red' ? 'bg-red-500' :
                                                                        drData.patent.risk_color === 'amber' ? 'bg-amber-500' :
                                                                        drData.patent.risk_color === 'yellow' ? 'bg-yellow-500' :
                                                                        'bg-green-500'
                                                                    }`}
                                                                    style={{ width: `${drData.patent.scooped_score}%` }}
                                                                />
                                                            </div>
                                                            <p className="text-xs text-slate-500 mt-2">
                                                                {drData.patent.risk_label}
                                                            </p>
                                                        </div>
                                                        
                                                        {/* Key Metrics */}
                                                        <div className="grid grid-cols-2 gap-2">
                                                            <div className="bg-slate-50 p-3 rounded-lg">
                                                                <span className="text-xs text-slate-500">Total Patents</span>
                                                                <p className="text-xl font-bold text-slate-800">{drData.patent.total_hits || 0}</p>
                                                            </div>
                                                            <div className="bg-slate-50 p-3 rounded-lg">
                                                                <span className="text-xs text-slate-500">Recent (5yr)</span>
                                                                <p className="text-xl font-bold text-slate-800">{drData.patent.recent_filings_5y || 0}</p>
                                                            </div>
                                                        </div>
                                                        
                                                        {/* Assessment */}
                                                        <div className="bg-slate-50 p-3 rounded-lg">
                                                            <span className="text-xs text-slate-500 block mb-1">Assessment</span>
                                                            <p className="text-xs text-slate-700 leading-relaxed">
                                                                {drData.patent.risk_assessment || drData.patent.message}
                                                            </p>
                                                        </div>
                                                        
                                                        {/* Top Competitors */}
                                                        {drData.patent.top_competitors && drData.patent.top_competitors.length > 0 && (
                                                            <div>
                                                                <span className="text-xs text-slate-500 block mb-2">Top Competitors</span>
                                                                <div className="space-y-1">
                                                                    {drData.patent.top_competitors.slice(0, 4).map((comp: any, i: number) => (
                                                                        <div key={i} className="flex items-center justify-between text-xs">
                                                                            <span className="text-slate-600 truncate max-w-[120px]">{comp.name}</span>
                                                                            <span className="font-medium text-slate-800">{comp.count} patents</span>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                    
                                                    {/* Heatmap Visualization */}
                                                    <div>
                                                        <span className="text-xs text-slate-500 block mb-2">Filing Activity Heatmap (Last 6 Years)</span>
                                                        {drData.patent.heatmap && drData.patent.heatmap.length > 0 ? (
                                                            <div className="overflow-x-auto">
                                                                <table className="w-full text-xs">
                                                                    <thead>
                                                                        <tr>
                                                                            <th className="text-left p-1 text-slate-500 font-medium">Assignee</th>
                                                                            {drData.patent.heatmap[0]?.data?.map((d: any) => (
                                                                                <th key={d.year} className="text-center p-1 text-slate-500 font-medium w-10">{d.year.slice(2)}</th>
                                                                            ))}
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody>
                                                                        {drData.patent.heatmap.map((row: any, i: number) => (
                                                                            <tr key={i}>
                                                                                <td className="p-1 text-slate-600 truncate max-w-[80px]" title={row.name}>{row.name}</td>
                                                                                {row.data.map((cell: any, j: number) => {
                                                                                    const intensity = Math.min(1, cell.count / 5);
                                                                                    return (
                                                                                        <td key={j} className="p-1">
                                                                                            <div 
                                                                                                className="w-full h-6 rounded flex items-center justify-center text-[10px] font-medium"
                                                                                                style={{
                                                                                                    backgroundColor: intensity > 0 
                                                                                                        ? `rgba(245, 158, 11, ${0.2 + intensity * 0.8})` 
                                                                                                        : '#f1f5f9',
                                                                                                    color: intensity > 0.5 ? 'white' : '#64748b'
                                                                                                }}
                                                                                                title={`${row.name}: ${cell.count} patents in ${cell.year}`}
                                                                                            >
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
                                                        ) : (
                                                            <div className="h-48 flex items-center justify-center bg-slate-50 rounded-lg">
                                                                <div className="text-center">
                                                                    <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-2" />
                                                                    <p className="text-sm text-slate-500">No significant patent activity</p>
                                                                    <p className="text-xs text-green-600 font-medium">White Space Opportunity</p>
                                                                </div>
                                                            </div>
                                                        )}
                                                        
                                                        {/* Sample Patents */}
                                                        {drData.patent.sample_patents && drData.patent.sample_patents.length > 0 && (
                                                            <div className="mt-4">
                                                                <span className="text-xs text-slate-500 block mb-2">Recent Filings</span>
                                                                <div className="space-y-1 max-h-24 overflow-y-auto">
                                                                    {drData.patent.sample_patents.slice(0, 3).map((p: any, i: number) => (
                                                                        <div key={i} className="text-xs p-2 bg-slate-50 rounded">
                                                                            <p className="text-slate-700 truncate" title={p.title}>{p.title}</p>
                                                                            <p className="text-slate-400">{p.assignee} | {p.date}</p>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Module C: Models */}
                                            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                                                <div className="flex items-center gap-2 mb-4">
                                                    <Microscope className="text-emerald-500" />
                                                    <h3 className="font-bold text-slate-700">Recommended Models</h3>
                                                </div>
                                                <div className="overflow-x-auto">
                                                    <table className="w-full text-sm text-left">
                                                        <thead className="text-xs text-slate-500 bg-slate-50 uppercase">
                                                            <tr>
                                                                <th className="px-3 py-2">Cell Line</th>
                                                                <th className="px-3 py-2">Tissue</th>
                                                                <th className="px-3 py-2">Match</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {drData.models.slice(0, 3).map((m: any) => (
                                                                <tr key={m.id} className="border-b border-slate-100">
                                                                    <td className="px-3 py-2 font-medium">{m.name}</td>
                                                                    <td className="px-3 py-2 text-slate-500">{m.tissue}</td>
                                                                    <td className="px-3 py-2 text-green-600 font-bold">{(m.match_score * 100).toFixed(0)}%</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>

                                            {/* Module D: Protocol */}
                                            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                                                <div className="flex items-center gap-2 mb-4">
                                                    <FileEdit className="text-indigo-500" />
                                                    <h3 className="font-bold text-slate-700">Validation Protocol</h3>
                                                </div>
                                                <div className="bg-slate-900 text-slate-300 p-4 rounded-lg font-mono text-xs h-48 overflow-y-auto whitespace-pre-wrap">
                                                    {drData.proto.content}
                                                </div>
                                                <button className="mt-4 w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 text-sm font-medium rounded-lg transition-colors">
                                                    Copy to Lab Notebook
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
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
