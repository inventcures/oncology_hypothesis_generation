import { useState } from "react";
import { Send, Activity, Brain, ShieldCheck, Microscope, BarChart3, Network, Table as TableIcon, FileText } from "lucide-react";

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
  const [status, setStatus] = useState("Idle");
  const [viewMode, setViewMode] = useState<"graph" | "table" | "metrics" | "papers">("graph");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
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
        body: JSON.stringify({ text: query }),
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
      <header className="flex items-center justify-between px-8 py-4 bg-white border-b border-slate-200 shadow-sm z-20">
        <div className="flex items-center gap-2">
          <div className="bg-blue-600 p-1.5 rounded-lg">
             <Activity className="text-white w-5 h-5" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-800">Onco-TTT</h1>
        </div>
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
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar / Feed */}
        <aside className="w-[400px] bg-white border-r border-slate-200 flex flex-col z-10 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
          <div className="p-6 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Research Query</h2>
            <form onSubmit={handleSubmit}>
              <div className="relative group">
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask a complex question (e.g., 'Targetable mechanisms in KRAS G12C resistance')..."
                  className="w-full h-32 p-4 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:outline-none resize-none transition-all"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="absolute bottom-3 right-3 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-600/20"
                >
                  <Send size={16} />
                </button>
              </div>
            </form>
          </div>

          <div className="flex-1 overflow-y-auto p-6 bg-slate-50/50">
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
            <div className="absolute top-6 left-6 z-10 flex gap-2 bg-white/90 backdrop-blur border border-slate-200 p-1.5 rounded-lg shadow-sm">
                <button 
                    onClick={() => setViewMode("graph")}
                    className={`p-2 rounded-md transition-colors ${viewMode === "graph" ? "bg-blue-50 text-blue-600" : "text-slate-500 hover:bg-slate-50"}`}
                    title="Graph View"
                >
                    <Network size={20} />
                </button>
                <button 
                    onClick={() => setViewMode("table")}
                    className={`p-2 rounded-md transition-colors ${viewMode === "table" ? "bg-blue-50 text-blue-600" : "text-slate-500 hover:bg-slate-50"}`}
                    title="Evidence Table"
                >
                    <TableIcon size={20} />
                </button>
                <button 
                    onClick={() => setViewMode("metrics")}
                    className={`p-2 rounded-md transition-colors ${viewMode === "metrics" ? "bg-blue-50 text-blue-600" : "text-slate-500 hover:bg-slate-50"}`}
                    title="Metrics"
                >
                    <BarChart3 size={20} />
                </button>
                <button 
                    onClick={() => setViewMode("papers")}
                    className={`p-2 rounded-md transition-colors ${viewMode === "papers" ? "bg-blue-50 text-blue-600" : "text-slate-500 hover:bg-slate-50"}`}
                    title="Literature"
                >
                    <FileText size={20} />
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
                                {/* Links */}
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
                                    </g>
                                );
                                })}
                                {/* Nodes */}
                                {graphData.nodes.map((node) => (
                                <g key={node.id} transform={`translate(${node.x},${node.y})`} className="group">
                                    <circle
                                    r={24}
                                    fill={getNodeColor(node.type)}
                                    className="cursor-pointer transition-all duration-300 drop-shadow-md group-hover:drop-shadow-xl"
                                    stroke="white"
                                    strokeWidth={3}
                                    />
                                    <text
                                    dy={45}
                                    textAnchor="middle"
                                    className="text-[10px] font-bold fill-slate-500 uppercase tracking-wider pointer-events-none select-none"
                                    >
                                    {node.id}
                                    </text>
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
                                </g>
                                ))}
                            </svg>
                        )}

                        {viewMode === "table" && (
                            <div className="w-full h-full p-24 overflow-auto">
                                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                                    <table className="w-full text-sm text-left">
                                        <thead className="bg-slate-50 border-b border-slate-200">
                                            <tr>
                                                <th className="px-6 py-4 font-semibold text-slate-700">Entity Name</th>
                                                <th className="px-6 py-4 font-semibold text-slate-700">Type</th>
                                                <th className="px-6 py-4 font-semibold text-slate-700">Coordinates</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {graphData.nodes.map((n) => (
                                                <tr key={n.id} className="hover:bg-slate-50/50">
                                                    <td className="px-6 py-4 font-medium text-slate-900">{n.id}</td>
                                                    <td className="px-6 py-4">
                                                        <span 
                                                            className="px-2 py-1 rounded-full text-xs font-semibold text-white"
                                                            style={{backgroundColor: getNodeColor(n.type)}}
                                                        >
                                                            {n.type}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 text-slate-500 font-mono text-xs">
                                                        {n.x.toFixed(0)}, {n.y.toFixed(0)}
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
    </main>
  );
}
