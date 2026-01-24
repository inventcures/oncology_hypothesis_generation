"use client";

import { useState } from "react";
import { Send, Activity, Brain, ShieldCheck, Microscope } from "lucide-react";

type Hypothesis = {
  id: string;
  title: string;
  description: string;
  confidence: number;
  verified: boolean;
  novelty_score: number;
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
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
    setHypotheses([]);
    setGraphData(null);
    setStatus("Initializing TTT Adaptation...");

    try {
      // Simulate TTT phases
      setTimeout(() => setStatus("ARK Exploring Knowledge Graph..."), 1000);
      setTimeout(() => setStatus("MEDEA Verifying Context..."), 2000);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiUrl}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: query }),
      });
      
      const data = await res.json();
      setHypotheses(data.hypotheses);
      setGraphData(data.graph_context);
      setStatus("Complete");
    } catch (error) {
      console.error(error);
      setStatus("Error connecting to backend");
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
    <main className="flex min-h-screen flex-col bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Activity className="text-blue-600" />
          <h1 className="text-xl font-bold tracking-tight">Onco-TTT</h1>
        </div>
        <div className="flex gap-4 text-sm text-gray-500">
          <span className={status.includes("ARK") ? "text-blue-600 font-bold" : ""}>ARK: {status.includes("ARK") ? "Working..." : "Ready"}</span>
          <span className={status.includes("MEDEA") ? "text-green-600 font-bold" : ""}>MEDEA: {status.includes("MEDEA") ? "Verifying..." : "Ready"}</span>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar / Feed */}
        <aside className="w-1/3 bg-white border-r border-gray-200 p-6 flex flex-col z-10 shadow-lg">
          <h2 className="text-lg font-semibold mb-4">Research Query</h2>
          <form onSubmit={handleSubmit} className="mb-8">
            <div className="relative">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., Mechanisms of resistance to KRAS G12C inhibitors..."
                className="w-full h-32 p-4 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
              />
              <button
                type="submit"
                disabled={loading}
                className="absolute bottom-3 right-3 p-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-all"
              >
                <Send size={16} />
              </button>
            </div>
          </form>

          {status !== "Idle" && status !== "Complete" && (
            <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-100 flex items-center gap-3">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-ping" />
              <p className="text-sm font-medium text-blue-700">
                {status}
              </p>
            </div>
          )}

          <div className="flex-1 overflow-y-auto pr-2">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">
              Generated Hypotheses
            </h3>
            <div className="space-y-4">
              {hypotheses.map((h) => (
                <div
                  key={h.id}
                  className="p-4 rounded-lg border border-gray-200 hover:border-blue-400 hover:shadow-md cursor-pointer transition-all bg-white"
                >
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-semibold text-blue-900 leading-tight">{h.title}</h4>
                    {h.verified ? (
                      <ShieldCheck className="text-green-500 shrink-0" size={18} />
                    ) : (
                      <Brain className="text-amber-500 shrink-0" size={18} />
                    )}
                  </div>
                  <p className="text-sm text-gray-600 line-clamp-3 mb-3">
                    {h.description}
                  </p>
                  <div className="flex items-center gap-4 text-xs font-medium text-gray-400">
                    <span className="bg-gray-100 px-2 py-1 rounded">Conf: {(h.confidence * 100).toFixed(0)}%</span>
                    <span className="bg-gray-100 px-2 py-1 rounded">Novelty: {(h.novelty_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
              {hypotheses.length === 0 && !loading && (
                <div className="text-center text-gray-400 py-10 text-sm">
                  No hypotheses generated yet. Enter a query to begin discovery.
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Main Canvas Area */}
        <section className="flex-1 bg-slate-50 relative overflow-hidden flex items-center justify-center">
          {/* Background Grid */}
          <div className="absolute inset-0 grid grid-cols-[repeat(40,minmax(0,1fr))] opacity-5 pointer-events-none">
            {Array.from({ length: 1600 }).map((_, i) => (
              <div key={i} className="border-r border-b border-gray-400" />
            ))}
          </div>
          
          {graphData ? (
             <svg className="w-full h-full" viewBox="0 0 800 600">
                <defs>
                  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="28" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
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
                        strokeWidth={2}
                        markerEnd="url(#arrowhead)"
                      />
                      <text x={(source.x + target.x)/2} y={(source.y + target.y)/2} fill="#64748b" fontSize="10" textAnchor="middle" dy="-5">
                         {link.relation}
                      </text>
                    </g>
                  );
                })}
                {/* Nodes */}
                {graphData.nodes.map((node) => (
                  <g key={node.id} transform={`translate(${node.x},${node.y})`}>
                    <circle
                      r={20}
                      fill={getNodeColor(node.type)}
                      stroke="white"
                      strokeWidth={2}
                      className="cursor-pointer hover:stroke-gray-800 transition-colors"
                    />
                    <text
                      dy={35}
                      textAnchor="middle"
                      className="text-xs font-medium fill-slate-700 pointer-events-none select-none"
                    >
                      {node.id}
                    </text>
                    <text
                       dy={4}
                       textAnchor="middle"
                       fill="white"
                       fontSize="10"
                       fontWeight="bold"
                       pointer-events="none"
                    >
                      {node.type[0]}
                    </text>
                  </g>
                ))}
             </svg>
          ) : (
            <div className="text-center text-gray-400 z-10">
              <Microscope size={64} className="mx-auto mb-4 opacity-20" />
              <p className="text-lg font-light">
                Select a hypothesis to visualize the mechanism <br />
                or explore the Knowledge Graph.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
