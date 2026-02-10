"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import { Send, Activity, Brain, ShieldCheck, Microscope, BarChart3, Network, Table as TableIcon, FileText, Sparkles, Search, ArrowRight, FlaskConical, Scale, Dna, FileEdit, AlertTriangle, CheckCircle, XCircle, Target, Download, Copy, X as XIcon, Info, HelpCircle, GitBranch, History, RefreshCw, Zap, TrendingUp, FileDown } from "lucide-react";

// Dynamically import components to avoid SSR issues
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

const ValidationDashboard = dynamic(() => import("./components/ValidationDashboard"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

const ClinicalTrialsDashboard = dynamic(() => import("./components/ClinicalTrialsDashboard"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

const PathwayView = dynamic(() => import("./components/PathwayView"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

const TargetDossier = dynamic(() => import("./components/TargetDossier"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

const IndicationHeatmap = dynamic(() => import("./components/IndicationHeatmap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

const WhatIfSimulator = dynamic(() => import("./components/WhatIfSimulator"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

const ExportReport = dynamic(() => import("./components/ExportReport"), { ssr: false });

const InteractiveGraph = dynamic(() => import("./components/InteractiveGraph"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

const CompetitiveDashboard = dynamic(() => import("./components/CompetitiveDashboard"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  ),
});

type EvidenceItem = {
  type: string;
  source?: string;
  target?: string;
  relation?: string;
  weight?: number;
  title?: string;
};

type Hypothesis = {
  id: string;
  title: string;
  description: string;
  confidence: number;
  verified: boolean;
  novelty_score: number;
  evidence?: EvidenceItem[];
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
  label: string;
  color: string;
  border_color: string;
  confidence: number;
  radius: number;
  x: number;
  y: number;
  degree: number;
  source: string;
  glow: boolean;
};

type GraphLink = {
  source: string;
  target: string;
  relation: string;
  label: string;
  weight: number;
  color: string;
  thickness: number;
  source_data: string;
  animated: boolean;
};

type GraphLegendItem = {
  type: string;
  color: string;
  count: number;
  label: string;
};

type GraphStats = {
  total_nodes: number;
  total_edges: number;
  entity_types: Record<string, number>;
  relation_types: Record<string, number>;
  sources: Record<string, number>;
};

type PocketData = {
  id: string;
  name: string;
  color: string;
  center: number[];
  residue_ids: number[];
  druggability_score: number;
  druggability_label: string;
};

type StructureResult = {
  uniprot_id?: string;
  pdb_url?: string;
  pdb_content?: string;
  pockets?: PocketData[];
  druggability_score: number;
  binding_site_residues?: number[];
  mutation_analysis?: {
    found: boolean;
    position?: number;
    wt_aa?: string;
    mut_aa?: string;
    coordinate?: number[];
    in_binding_pocket?: boolean;
    impact_assessment?: string;
    impact_score?: number;
    message?: string;
  };
  analysis?: {
    residue_count: number;
    avg_plddt?: number;
    high_confidence_pct?: number;
  };
  error?: string;
};

type PatentResult = {
  scooped_score: number;
  risk_color: string;
  risk_label: string;
  risk_assessment?: string;
  message?: string;
  total_hits?: number;
  recent_filings_5y?: number;
  google_patents_link: string;
  lens_link: string;
  top_competitors?: { name: string; count: number }[];
  heatmap?: { name: string; data: { year: string; count: number }[] }[];
  sample_patents?: { title: string; assignee: string; date: string }[];
};

type ModelResult = {
  total_found?: number;
  top_pick?: {
    name: string;
    disease: string;
    match_score: number;
    mutation_match?: string;
    mutations?: string[];
  };
  recommendations?: any[];
  avoid_list?: { name: string; problem_info?: { issue: string } }[];
  notes?: string[];
};

type ProtocolResult = {
  content: string;
  generated_by?: string;
  grnas?: {
    sequence: string;
    gc_content: number;
    score: number;
    off_target_risk: string;
  }[];
  timeline?: { day: number; task: string }[];
  reagents?: (string | { name: string })[];
};

type DeepResearchData = {
  struct: StructureResult;
  patent: PatentResult;
  models: ModelResult;
  proto: ProtocolResult;
  target: string;
  mutation: string | null;
  tissue: string;
  query: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://backend-production-baa6.up.railway.app";

export default function Home() {
  const [query, setQuery] = useState("");
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[]; stats?: GraphStats; legend?: GraphLegendItem[] } | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<number | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [status, setStatus] = useState("Idle");
  const [viewMode, setViewMode] = useState<"graph" | "table" | "metrics" | "papers" | "validate" | "deep_research" | "trials" | "pathway" | "dossier" | "indications" | "whatif" | "competitive">("graph");
  const [drData, setDrData] = useState<DeepResearchData | null>(null);
  const [drLoading, setDrLoading] = useState(false);
  const [validationData, setValidationData] = useState<any>(null);
  const [validationLoading, setValidationLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [drError, setDrError] = useState<string | null>(null);
  const [validationQuery, setValidationQuery] = useState<string>("");
  const [trialsData, setTrialsData] = useState<any>(null);
  const [trialsLoading, setTrialsLoading] = useState(false);
  const [trialsQuery, setTrialsQuery] = useState("");
  // Error states for user-facing error messages
  const [validationError, setValidationError] = useState<string | null>(null);
  const [trialsError, setTrialsError] = useState<string | null>(null);
  // Query history (localStorage-backed)
  const [queryHistory, setQueryHistory] = useState<{text: string; time: number}[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  // Interactive graph toggle
  const [useInteractiveGraph, setUseInteractiveGraph] = useState(true);
  // Dossier state
  const [dossierData, setDossierData] = useState<any>(null);
  const [dossierLoading, setDossierLoading] = useState(false);
  // Indication expansion state
  const [indicationData, setIndicationData] = useState<any>(null);
  const [indicationLoading, setIndicationLoading] = useState(false);
  // What-If simulator state
  const [whatIfResult, setWhatIfResult] = useState<any>(null);
  const [whatIfLoading, setWhatIfLoading] = useState(false);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  // --- URL State: read query from URL on mount ---
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const urlQuery = params.get("q");
    const urlView = params.get("view");
    if (urlQuery) {
      setQuery(urlQuery);
    }
    if (urlView && ["graph","table","metrics","papers","validate","deep_research","trials","pathway","dossier","indications","whatif","competitive"].includes(urlView)) {
      setViewMode(urlView as typeof viewMode);
    }
    // Load history from localStorage
    try {
      const saved = localStorage.getItem("onco_query_history");
      if (saved) setQueryHistory(JSON.parse(saved));
    } catch { /* ignore */ }
  }, []);

  // --- URL State: update URL when query or viewMode changes ---
  useEffect(() => {
    if (typeof window === "undefined" || !hasSearched) return;
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (viewMode !== "graph") params.set("view", viewMode);
    const newUrl = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.replaceState({}, "", newUrl);
  }, [query, viewMode, hasSearched]);

  // --- Export helpers ---
  const exportCSV = useCallback(() => {
    if (!graphData) return;
    const header = "Entity,Type,Confidence,Source";
    const rows = graphData.nodes.map(n =>
      `"${(n.label || n.id).replace(/"/g, '""')}","${n.type}","${((n.confidence || 0.5) * 100).toFixed(0)}%","${n.source || 'unknown'}"`
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `onco-ttt-entities-${Date.now()}.csv`;
    a.click(); URL.revokeObjectURL(url);
    showToast("CSV exported successfully");
  }, [graphData, showToast]);

  const exportBibTeX = useCallback(() => {
    if (!papers.length) return;
    const entries = papers.map((p, i) => {
      const key = `paper${i + 1}_${p.year || 'nd'}`;
      return `@article{${key},
  title={${p.title}},
  author={${p.authors}},
  journal={${p.journal}},
  year={${p.year || 'n.d.'}},
  url={${p.url || ''}}
}`;
    });
    const bib = entries.join("\n\n");
    const blob = new Blob([bib], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `onco-ttt-papers-${Date.now()}.bib`;
    a.click(); URL.revokeObjectURL(url);
    showToast("BibTeX exported successfully");
  }, [papers, showToast]);

  // --- Tissue inference helper ---
  const inferTissue = useCallback((): string => {
    const q = query.toLowerCase();
    if (q.includes("melanoma") || q.includes("skin")) return "skin";
    if (q.includes("breast")) return "breast";
    if (q.includes("pancrea")) return "pancreas";
    if (q.includes("colorectal") || q.includes("colon")) return "colon";
    if (q.includes("brain") || q.includes("glioma") || q.includes("glioblastoma")) return "brain";
    if (q.includes("liver") || q.includes("hepato")) return "liver";
    if (q.includes("prostate")) return "prostate";
    if (q.includes("ovarian") || q.includes("ovary")) return "ovary";
    if (q.includes("renal") || q.includes("kidney")) return "kidney";
    return "lung"; // default
  }, [query]);

  const handleDeepResearch = useCallback(async () => {
    if (!graphData || graphData.nodes.length === 0) return;
    
    // Naive heuristic: Pick the first Gene node as the target
    const targetNode = graphData.nodes.find(n => n.type.toLowerCase() === 'gene') || graphData.nodes[0];
    const diseaseNode = graphData.nodes.find(n => n.type.toLowerCase() === 'disease') || { id: "Cancer" };
    
    // Extract mutation from query if present (e.g., "G12C", "V600E")
    const mutationMatch = query.match(/([A-Z]\d+[A-Z])/i);
    const mutation = mutationMatch ? mutationMatch[1].toUpperCase() : null;
    
    setDrLoading(true);
    setDrError(null);
    try {
        const apiUrl = API_URL;
        const tissue = inferTissue();
        
        // Build structure URL with mutation if present
        const structureUrl = mutation 
            ? `${apiUrl}/structure/${targetNode.id}?mutation=${mutation}`
            : `${apiUrl}/structure/${targetNode.id}`;
        
        // Parallel Fetching - tissue and cell_line are now dynamically inferred
        const [structRes, patentRes, modelRes, protoRes] = await Promise.all([
            fetch(structureUrl),
            fetch(`${apiUrl}/patents/check?gene=${targetNode.id}&disease=${diseaseNode.id}`),
            fetch(`${apiUrl}/models/recommend?tissue=${encodeURIComponent(tissue)}&mutation=${mutation || targetNode.id}`),
            fetch(`${apiUrl}/protocols/generate?method=crispr&gene=${targetNode.id}&cell_line=auto`)
        ]);

        const struct = await structRes.json();
        const patent = await patentRes.json();
        const models = await modelRes.json();
        const proto = await protoRes.json();

        setDrData({ struct, patent, models, proto, target: targetNode.id, mutation, tissue, query });
    } catch (e) {
        console.error("Deep Research Failed", e);
        setDrError(String(e));
    } finally {
        setDrLoading(false);
    }
  }, [graphData, query, inferTissue]);

  const handleValidation = useCallback(async () => {
    if (!graphData || graphData.nodes.length === 0) return;
    
    const targetNode = graphData.nodes.find(n => n.type.toLowerCase() === 'gene') || graphData.nodes[0];
    const diseaseNode = graphData.nodes.find(n => n.type.toLowerCase() === 'disease') || { id: "Cancer" };
    
    // Infer cancer type from query
    let cancerType = diseaseNode.id;
    if (query.toLowerCase().includes("lung")) cancerType = "Lung Cancer";
    if (query.toLowerCase().includes("breast")) cancerType = "Breast Cancer";
    if (query.toLowerCase().includes("melanoma")) cancerType = "Melanoma";
    if (query.toLowerCase().includes("pancrea")) cancerType = "Pancreatic Cancer";
    if (query.toLowerCase().includes("colorectal")) cancerType = "Colorectal Cancer";
    
    setValidationLoading(true);
    setValidationError(null);
    setViewMode("validate");
    
    try {
      const apiUrl = API_URL;
      const resp = await fetch(
        `${apiUrl}/validate?gene=${targetNode.id}&disease=${cancerType}&cancer_type=${cancerType}`
      );
      
      if (resp.ok) {
        const data = await resp.json();
        setValidationData(data);
        setValidationQuery(query);
      } else {
        setValidationError(`Validation failed: ${resp.status} ${resp.statusText}`);
      }
    } catch (e) {
      setValidationError(`Validation error: ${e instanceof Error ? e.message : "Network error"}`);
    } finally {
      setValidationLoading(false);
    }
  }, [graphData, query]);

  const handleTrialsSearch = useCallback(async () => {
    if (!graphData?.nodes) return;
    const geneNode = graphData.nodes.find((n) => n.type.toLowerCase() === "gene");
    const diseaseNode = graphData.nodes.find((n) => n.type.toLowerCase() === "disease");
    const gene = geneNode?.id || "";
    const disease = diseaseNode?.id || "cancer";
    if (!gene) return;
    setTrialsLoading(true);
    setTrialsError(null);
    try {
      const res = await fetch(`${API_URL}/clinical_trials?gene=${encodeURIComponent(gene)}&disease=${encodeURIComponent(disease)}`);
      if (res.ok) {
        const data = await res.json();
        setTrialsData(data);
        setTrialsQuery(query);
      } else {
        setTrialsError(`Clinical trials search failed: ${res.status} ${res.statusText}`);
      }
    } catch (err) {
      setTrialsError(`Clinical trials error: ${err instanceof Error ? err.message : "Network error"}`);
    } finally {
      setTrialsLoading(false);
    }
  }, [graphData, query]);

  const handleDossier = useCallback(async () => {
    if (!graphData?.nodes) return;
    const geneNode = graphData.nodes.find(n => n.type.toLowerCase() === "gene") || graphData.nodes[0];
    const diseaseNode = graphData.nodes.find(n => n.type.toLowerCase() === "disease") || { id: "Cancer" };
    const mutationMatch = query.match(/([A-Z]\d+[A-Z])/i);
    const mutation = mutationMatch ? mutationMatch[1].toUpperCase() : null;
    const tissue = inferTissue();
    
    setDossierLoading(true);
    setViewMode("dossier");
    try {
      const res = await fetch(`${API_URL}/dossier`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gene: geneNode.id, disease: (diseaseNode as any).id || "Cancer", mutation, tissue }),
      });
      if (res.ok) {
        setDossierData(await res.json());
      }
    } catch (e) {
      console.error("Dossier failed:", e);
    } finally {
      setDossierLoading(false);
    }
  }, [graphData, query, inferTissue]);

  const handleIndications = useCallback(async () => {
    if (!graphData?.nodes) return;
    const geneNode = graphData.nodes.find(n => n.type.toLowerCase() === "gene");
    if (!geneNode) return;
    
    setIndicationLoading(true);
    setViewMode("indications");
    try {
      const res = await fetch(`${API_URL}/indications?gene=${encodeURIComponent(geneNode.id)}&limit=25`);
      if (res.ok) {
        setIndicationData(await res.json());
      }
    } catch (e) {
      console.error("Indications failed:", e);
    } finally {
      setIndicationLoading(false);
    }
  }, [graphData]);

  const handleWhatIf = useCallback(async (targetNode: string, perturbationType: string) => {
    setWhatIfLoading(true);
    try {
      const res = await fetch(`${API_URL}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_node: targetNode, perturbation_type: perturbationType, query }),
      });
      if (res.ok) {
        setWhatIfResult(await res.json());
      }
    } catch (e) {
      console.error("Simulation failed:", e);
    } finally {
      setWhatIfLoading(false);
    }
  }, [query]);

  const handleSubmit = useCallback(async (e?: React.FormEvent, overrideQuery?: string) => {
    if (e) e.preventDefault();
    const textToSearch = overrideQuery || query;
    if (!textToSearch) return;

    if (overrideQuery) setQuery(overrideQuery);
    
    setLoading(true);
    setHasSearched(true);
    setHypotheses([]);
    setGraphData(null);
    setPapers([]);
    // Reset all secondary view state from previous search
    setDrData(null);
    setDrError(null);
    setValidationData(null);
    setValidationQuery("");
    setTrialsData(null);
    setTrialsQuery("");
    setValidationError(null);
    setTrialsError(null);
    setDossierData(null);
    setIndicationData(null);
    setWhatIfResult(null);
    setHoveredEdge(null);
    setHoveredNode(null);
    setSelectedNode(null);
    setViewMode("graph");
    setStatus("Analyzing your question...");

    // Save to query history
    const newHistory = [{text: textToSearch, time: Date.now()}, ...queryHistory.filter(h => h.text !== textToSearch)].slice(0, 20);
    setQueryHistory(newHistory);
    try { localStorage.setItem("onco_query_history", JSON.stringify(newHistory)); } catch { /* ignore */ }

    try {
      const apiUrl = API_URL;
      
      // Try SSE streaming first — falls back to regular POST if it fails
      try {
        const res = await fetch(`${apiUrl}/generate_stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textToSearch }),
        });
        
        if (res.ok && res.headers.get("content-type")?.includes("text/event-stream")) {
          const reader = res.body?.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          
          while (reader) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";
            
            for (const line of lines) {
              if (!line.startsWith("data: ")) continue;
              try {
                const event = JSON.parse(line.slice(6));
                if (event.message) setStatus(event.message);
                
                if (event.type === "complete" && event.data) {
                  setHypotheses(event.data.hypotheses || []);
                  setGraphData(event.data.graph_context);
                  setPapers(event.data.papers || []);
                  setStatus("Complete");
                }
              } catch { /* skip malformed events */ }
            }
          }
          setLoading(false);
          return;
        }
      } catch {
        // SSE failed — fall back to regular POST below
      }
      
      // Fallback: regular POST with synthetic status updates
      setTimeout(() => setStatus("Identifying genes, drugs & pathways..."), 800);
      setTimeout(() => setStatus("Connecting biological relationships..."), 1800);
      setTimeout(() => setStatus("Finding relevant research papers..."), 2800);

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
  }, [query]);

  const handleExampleClick = useCallback((text: string) => {
    handleSubmit(undefined, text);
  }, [handleSubmit]);

  const getNodeColor = useMemo(() => (node: GraphNode | { type: string; color?: string }) => {
    // Use backend-provided color if available, else fallback
    if ('color' in node && node.color) return node.color;
    const fallbacks: Record<string, string> = {
      gene: "#3b82f6", Gene: "#3b82f6",
      disease: "#ef4444", Disease: "#ef4444",
      drug: "#10b981", Drug: "#10b981",
      pathway: "#8b5cf6", Pathway: "#8b5cf6",
      mutation: "#f59e0b", Mutation: "#f59e0b",
      cell_type: "#06b6d4", CellType: "#06b6d4",
      biomarker: "#ec4899", Biomarker: "#ec4899",
      mechanism: "#6366f1", Mechanism: "#6366f1",
    };
    return fallbacks[node.type] || "#9ca3af";
  }, []);

  return (
    <main className="flex min-h-screen flex-col bg-slate-50 text-slate-900 font-sans">
      <style jsx global>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translate(-50%, 10px); }
          to { opacity: 1; transform: translate(-50%, 0); }
        }
      `}</style>
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
                <div className={`w-2 h-2 rounded-full ${status.includes("genes") || status.includes("Identifying") ? "bg-indigo-500 animate-pulse" : "bg-green-500"}`}></div>
                <span className="text-slate-600">Entity Extraction</span>
            </div>
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${status.includes("Connecting") || status.includes("relationships") ? "bg-blue-500 animate-pulse" : "bg-green-500"}`}></div>
                <span className="text-slate-600">Knowledge Graph</span>
            </div>
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${status.includes("papers") || status.includes("Finding") ? "bg-amber-500 animate-pulse" : "bg-green-500"}`}></div>
                <span className="text-slate-600">Literature</span>
            </div>
            {graphData && (
              <ExportReport
                query={query}
                hypotheses={hypotheses}
                graphData={graphData}
                papers={papers}
                validationData={validationData}
                drData={drData}
                trialsData={trialsData}
              />
            )}
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
                        <span>AI-Powered Cancer Research Assistant</span>
                    </div>
                    <h2 className="text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
                        Ask About <br/> 
                        <span className="text-blue-600">Cancer Biology</span>
                    </h2>
                    <p className="text-lg text-slate-500 max-w-2xl mx-auto">
                        Get hypotheses backed by evidence. We extract genes, drugs, and pathways from your question, 
                        connect them using validated databases, and surface relevant research papers.
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
                            placeholder="e.g. Why does KRAS-mutant lung cancer resist immunotherapy?"
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

                {/* Suggested Queries - Tiered */}
                <div className="pt-8 space-y-6">
                    <div>
                        <p className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Start Simple</p>
                        <div className="flex flex-wrap justify-center gap-3">
                            {[
                                "What genes drive lung cancer?",
                                "How does melanoma resist treatment?",
                                "What drugs target EGFR?",
                                "What is the role of TP53 in cancer?"
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
                    <div>
                        <p className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">Go Deeper</p>
                        <div className="flex flex-wrap justify-center gap-2">
                            {[
                                "KRAS G12C resistance mechanisms in NSCLC",
                                "STK11 loss and immune exclusion in Lung Adenocarcinoma",
                                "YAP1-mediated immunotherapy failure",
                                "EGFR T790M bypass signaling tracks"
                            ].map((q) => (
                                <button
                                    key={q}
                                    onClick={() => handleExampleClick(q)}
                                    className="px-3 py-1.5 bg-slate-50 border border-slate-100 hover:border-blue-300 hover:text-blue-600 rounded-full text-xs font-medium text-slate-400 transition-all"
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
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
            {queryHistory.length > 0 && (
              <div className="mt-2">
                <button onClick={() => setShowHistory(!showHistory)} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors">
                  <History size={12} />
                  <span>Recent ({queryHistory.length})</span>
                </button>
                {showHistory && (
                  <div className="mt-1.5 space-y-1 max-h-32 overflow-y-auto">
                    {queryHistory.slice(0, 8).map((h, i) => (
                      <button key={i} onClick={() => handleSubmit(undefined, h.text)} className="w-full text-left text-xs text-slate-500 hover:text-blue-600 hover:bg-blue-50 px-2 py-1 rounded truncate transition-colors">
                        {h.text}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
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
                 <div className="p-4 rounded-lg bg-red-50 border border-red-100 text-sm mb-4">
                    <p className="text-red-700 font-medium mb-2">Analysis could not be completed</p>
                    <p className="text-red-600 text-xs mb-3">This usually means one of our data sources is temporarily unavailable.</p>
                    <button
                      onClick={() => handleSubmit()}
                      className="px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-medium rounded-md transition-colors"
                    >
                      Try Again
                    </button>
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
                    <span className="text-xs font-medium text-slate-500">{(h.confidence * 100).toFixed(0)}% Evidence</span>
                  </div>

                  {h.evidence && h.evidence.length > 0 && (
                    <details className="mt-3">
                      <summary className="text-xs text-slate-400 cursor-pointer hover:text-blue-500 select-none transition-colors">
                        Evidence trail ({h.evidence.length} {h.evidence.length === 1 ? "link" : "links"})
                      </summary>
                      <div className="mt-2 space-y-1.5 pl-3 border-l-2 border-blue-100">
                        {h.evidence.map((e: EvidenceItem, i: number) => (
                          <div key={i} className="text-xs text-slate-500 flex items-center gap-1.5">
                            {e.type === "graph_edge" ? (
                              <>
                                <span className="font-medium text-slate-700">{e.source}</span>
                                <span className="text-blue-400">&rarr;</span>
                                <span className="font-medium text-slate-700">{e.target}</span>
                                <span className="text-slate-300 ml-1">({e.relation})</span>
                              </>
                            ) : (
                              <span className="italic">{e.title || "Supporting reference"}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
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
            <div className="shrink-0 mx-6 mt-4 mb-2 z-10 flex gap-1 bg-white/80 backdrop-blur-md border border-slate-200 p-1 rounded-lg shadow-sm w-fit">
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
                <button
                    onClick={() => setViewMode("pathway")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "pathway" ? "bg-violet-50 text-violet-600 shadow-sm border border-violet-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <GitBranch size={16} />
                    <span>Pathways</span>
                </button>
                <div className="w-px bg-slate-200 my-1 mx-1"></div>
                <button 
                    onClick={() => setViewMode("validate")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "validate" ? "bg-emerald-50 text-emerald-600 shadow-sm border border-emerald-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <Target size={16} />
                    <span>Validate</span>
                </button>
                <button 
                    onClick={() => setViewMode("deep_research")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "deep_research" ? "bg-purple-50 text-purple-600 shadow-sm border border-purple-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <FlaskConical size={16} />
                    <span>Feasibility</span>
                </button>
                <div className="w-px bg-slate-200 my-1 mx-1"></div>
                <button
                    onClick={() => setViewMode("trials")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "trials" ? "bg-cyan-50 text-cyan-600 shadow-sm border border-cyan-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <Activity size={16} />
                    <span>Trials</span>
                </button>
                <div className="w-px bg-slate-200 my-1 mx-1"></div>
                <button
                    onClick={handleDossier}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "dossier" ? "bg-blue-50 text-blue-600 shadow-sm border border-blue-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <Target size={16} />
                    <span>Dossier</span>
                </button>
                <button
                    onClick={handleIndications}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "indications" ? "bg-violet-50 text-violet-600 shadow-sm border border-violet-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <TrendingUp size={16} />
                    <span>Indications</span>
                </button>
                <button
                    onClick={() => setViewMode("whatif")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "whatif" ? "bg-amber-50 text-amber-600 shadow-sm border border-amber-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <Zap size={16} />
                    <span>What-If</span>
                </button>
                <button
                    onClick={() => setViewMode("competitive")}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === "competitive" ? "bg-blue-50 text-blue-600 shadow-sm border border-blue-100" : "text-slate-500 hover:bg-slate-50"}`}
                >
                    <BarChart3 size={16} />
                    <span>Intel</span>
                </button>
            </div>

            <div className="flex-1 relative overflow-auto bg-slate-50/30">
                {/* Background Grid */}
                <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'repeating-linear-gradient(90deg, transparent, transparent calc(100% / 40 - 1px), #0f172a calc(100% / 40 - 1px), #0f172a calc(100% / 40)), repeating-linear-gradient(0deg, transparent, transparent calc(100% / 40 - 1px), #0f172a calc(100% / 40 - 1px), #0f172a calc(100% / 40))' }} />
            
                {graphData ? (
                    <>
                        {viewMode === "graph" && useInteractiveGraph && (
                            <InteractiveGraph
                                nodes={graphData.nodes}
                                links={graphData.links}
                                stats={graphData.stats}
                                legend={graphData.legend}
                            />
                        )}

                        {viewMode === "graph" && !useInteractiveGraph && (
                            <>
                                {/* Rich Graph Legend (from backend) */}
                                <div className="absolute top-4 right-6 bg-white/95 backdrop-blur-sm p-4 rounded-xl border border-slate-200 shadow-lg text-xs space-y-2 z-10 min-w-[180px]">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Entity Types</span>
                                        {graphData.stats && (
                                            <span className="text-[10px] text-slate-400">
                                                {graphData.stats.total_nodes}N / {graphData.stats.total_edges}E
                                            </span>
                                        )}
                                    </div>
                                    {(graphData.legend || []).map((item) => (
                                        <div key={item.type} className="flex items-center justify-between gap-2">
                                            <div className="flex items-center gap-2">
                                                <span className="w-3 h-3 rounded-full shrink-0 shadow-sm" style={{ backgroundColor: item.color }}></span>
                                                <span className="text-slate-600 font-medium">{item.label}</span>
                                            </div>
                                            <span className="text-slate-400 font-mono">{item.count}</span>
                                        </div>
                                    ))}
                                    {(!graphData.legend || graphData.legend.length === 0) && (
                                        <>
                                            <div className="flex items-center gap-2">
                                                <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                                                <span className="text-slate-600 font-medium">Gene / Target</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="w-3 h-3 rounded-full bg-red-500"></span>
                                                <span className="text-slate-600 font-medium">Disease</span>
                                            </div>
                                        </>
                                    )}
                                    <div className="border-t border-slate-100 pt-2 mt-2 space-y-1.5">
                                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Edges</span>
                                        <div className="flex items-center gap-2">
                                            <span className="w-6 h-[3px] bg-slate-500 rounded"></span>
                                            <span className="text-slate-500">Weak</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="w-6 h-[5px] bg-slate-700 rounded"></span>
                                            <span className="text-slate-500">Strong</span>
                                        </div>
                                    </div>
                                    {graphData.stats?.sources && Object.keys(graphData.stats.sources).length > 1 && (
                                        <div className="border-t border-slate-100 pt-2 mt-2 space-y-1">
                                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Sources</span>
                                            {Object.entries(graphData.stats.sources).map(([src, count]) => (
                                                <div key={src} className="flex items-center justify-between text-[10px]">
                                                    <span className="text-slate-500 capitalize">{src}</span>
                                                    <span className="text-slate-400 font-mono">{count as number}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                <svg className="w-full h-full" viewBox="0 0 800 600">
                                <defs>
                                    {/* Color-deduplicated arrowheads */}
                                    {Array.from(new Set(graphData.links.map(l => l.color || '#94a3b8'))).map((color) => (
                                        <marker key={`arrow-${color}`} id={`arrow-${color.replace('#', '')}`} markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse">
                                            <polygon points="0 0, 10 4, 0 8" fill={`${color}cc`} />
                                        </marker>
                                    ))}
                                    {/* Default arrowhead fallback */}
                                    <marker id="arrowhead" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse">
                                        <polygon points="0 0, 10 4, 0 8" fill="#64748b" />
                                    </marker>
                                    {/* Glow filter for high-confidence nodes */}
                                    <filter id="node-glow" x="-50%" y="-50%" width="200%" height="200%">
                                        <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                                        <feMerge>
                                            <feMergeNode in="coloredBlur"/>
                                            <feMergeNode in="SourceGraphic"/>
                                        </feMerge>
                                    </filter>
                                    {/* Pulse animation for high-confidence edges */}
                                    <style>{`
                                        @keyframes edge-pulse {
                                            0%, 100% { opacity: 0.7; }
                                            50% { opacity: 1; }
                                        }
                                        .edge-animated { animation: edge-pulse 2s ease-in-out infinite; }
                                        @keyframes glow-pulse {
                                            0%, 100% { filter: drop-shadow(0 0 4px rgba(59,130,246,0.3)); }
                                            50% { filter: drop-shadow(0 0 8px rgba(59,130,246,0.6)); }
                                        }
                                        .node-glow { animation: glow-pulse 3s ease-in-out infinite; }
                                    `}</style>
                                </defs>

                                {/* === EDGES === */}
                                {graphData.links.map((link, i) => {
                                    const sourceNode = graphData.nodes.find(n => n.id === link.source);
                                    const targetNode = graphData.nodes.find(n => n.id === link.target);
                                    if (!sourceNode || !targetNode) return null;
                                    
                                    const isHovered = hoveredEdge === i;
                                    const isConnectedToHoveredNode = hoveredNode === link.source || hoveredNode === link.target;
                                    const isDimmed = hoveredNode !== null && !isConnectedToHoveredNode;
                                    const edgeColor = link.color || "#94a3b8";
                                    const thickness = link.thickness || (1 + link.weight * 4);
                                    const midX = (sourceNode.x + targetNode.x) / 2;
                                    const midY = (sourceNode.y + targetNode.y) / 2;

                                    // Shorten line to stop at node radius
                                    const sRadius = sourceNode.radius || 22;
                                    const tRadius = targetNode.radius || 22;
                                    const dx = targetNode.x - sourceNode.x;
                                    const dy = targetNode.y - sourceNode.y;
                                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                                    const sx = sourceNode.x + (dx / dist) * sRadius;
                                    const sy = sourceNode.y + (dy / dist) * sRadius;
                                    const tx = targetNode.x - (dx / dist) * (tRadius + 10);
                                    const ty = targetNode.y - (dy / dist) * (tRadius + 10);

                                    return (
                                        <g key={`edge-${i}`} className={link.animated && !isDimmed ? 'edge-animated' : ''}>
                                            {/* Invisible wider hit area for hover */}
                                            <line
                                                x1={sx} y1={sy} x2={tx} y2={ty}
                                                stroke="transparent"
                                                strokeWidth={Math.max(thickness + 10, 14)}
                                                className="cursor-pointer"
                                                onMouseEnter={() => setHoveredEdge(i)}
                                                onMouseLeave={() => setHoveredEdge(null)}
                                            />
                                            {/* Visible edge */}
                                            <line
                                                x1={sx} y1={sy} x2={tx} y2={ty}
                                                stroke={edgeColor}
                                                strokeWidth={isHovered ? thickness + 1.5 : thickness}
                                                strokeOpacity={isDimmed ? 0.15 : isHovered ? 1 : 0.7}
                                                markerEnd={`url(#arrow-${(link.color || '#94a3b8').replace('#', '')})`}
                                                strokeLinecap="round"
                                                className="transition-all duration-200"
                                            />
                                            {/* Edge label (shown on edge hover or node hover) */}
                                            {(isHovered || isConnectedToHoveredNode) && !isDimmed && (
                                                <>
                                                    <rect
                                                        x={midX - 32} y={midY - 12}
                                                        width="64" height="24"
                                                        rx="6" fill={edgeColor}
                                                        fillOpacity={0.95}
                                                        className="drop-shadow-md"
                                                    />
                                                    <text
                                                        x={midX} y={midY + 1}
                                                        textAnchor="middle" dominantBaseline="middle"
                                                        className="text-[9px] fill-white font-bold select-none pointer-events-none"
                                                    >
                                                        {link.label || link.relation.replace(/_/g, ' ')}
                                                    </text>
                                                    {/* Confidence badge */}
                                                    <rect
                                                        x={midX + 28} y={midY - 8}
                                                        width="28" height="16" rx="4"
                                                        fill="white" fillOpacity={0.9}
                                                    />
                                                    <text
                                                        x={midX + 42} y={midY + 1}
                                                        textAnchor="middle" dominantBaseline="middle"
                                                        className="text-[8px] font-bold select-none pointer-events-none"
                                                        fill={edgeColor}
                                                    >
                                                        {(link.weight * 100).toFixed(0)}%
                                                    </text>
                                                </>
                                            )}
                                        </g>
                                    );
                                })}

                                {/* === NODES === */}
                                {graphData.nodes.map((node) => {
                                    const nodeColor = getNodeColor(node);
                                    const borderColor = node.border_color || nodeColor;
                                    const radius = node.radius || 22;
                                    const isHovered = hoveredNode === node.id;
                                    const isSelected = selectedNode === node.id;
                                    const isDimmed = hoveredNode !== null && !isHovered && !graphData.links.some(
                                        l => (l.source === hoveredNode && l.target === node.id) || (l.target === hoveredNode && l.source === node.id)
                                    );
                                    const displayRadius = isHovered ? radius + 4 : isSelected ? radius + 2 : radius;

                                    return (
                                        <g
                                            key={node.id}
                                            transform={`translate(${node.x},${node.y})`}
                                            className={`cursor-pointer ${node.glow && !isDimmed ? 'node-glow' : ''}`}
                                            onMouseEnter={() => setHoveredNode(node.id)}
                                            onMouseLeave={() => setHoveredNode(null)}
                                            onClick={() => setSelectedNode(selectedNode === node.id ? null : node.id)}
                                            opacity={isDimmed ? 0.25 : 1}
                                        >
                                            {/* Outer ring for selected state */}
                                            {isSelected && (
                                                <circle
                                                    r={displayRadius + 6}
                                                    fill="none"
                                                    stroke={nodeColor}
                                                    strokeWidth={2}
                                                    strokeDasharray="4 3"
                                                    opacity={0.6}
                                                />
                                            )}

                                            {/* Confidence ring (background arc) */}
                                            <circle
                                                r={displayRadius + 2}
                                                fill="none"
                                                stroke={nodeColor}
                                                strokeWidth={2.5}
                                                strokeDasharray={`${node.confidence * 2 * Math.PI * (displayRadius + 2)} ${2 * Math.PI * (displayRadius + 2)}`}
                                                strokeDashoffset={0}
                                                opacity={0.35}
                                                transform="rotate(-90)"
                                            />

                                            {/* Main node circle */}
                                            <circle
                                                r={displayRadius}
                                                fill={nodeColor}
                                                stroke="white"
                                                strokeWidth={isHovered ? 4 : 3}
                                                className="transition-all duration-200 drop-shadow-md"
                                            />

                                            {/* Node label (entity name) */}
                                            <text
                                                dy={displayRadius + 16}
                                                textAnchor="middle"
                                                className="text-[10px] font-bold fill-slate-600 pointer-events-none select-none"
                                                style={{ textShadow: '0 1px 2px rgba(255,255,255,0.8)' }}
                                            >
                                                {(node.label || node.id).length > 16 ? (node.label || node.id).slice(0, 14) + '...' : (node.label || node.id)}
                                            </text>

                                            {/* Type abbreviation inside node */}
                                            <text
                                                dy={1}
                                                textAnchor="middle"
                                                dominantBaseline="middle"
                                                fill="white"
                                                fontSize={displayRadius > 28 ? "12" : "10"}
                                                fontWeight="bold"
                                                className="pointer-events-none select-none"
                                            >
                                                {(node.type || '').replace(/_/g, '').slice(0, 2).toUpperCase()}
                                            </text>

                                            {/* Rich tooltip on hover */}
                                            {isHovered && (
                                                <foreignObject x="-100" y={-(displayRadius + 80)} width="200" height="75" className="pointer-events-none">
                                                    <div className="bg-slate-800/95 backdrop-blur text-white text-xs rounded-xl py-2.5 px-3.5 shadow-2xl border border-slate-600/30">
                                                        <div className="flex items-center justify-between mb-1">
                                                            <p className="font-bold text-[11px] truncate max-w-[140px]">{node.label || node.id}</p>
                                                            <span className="text-[9px] px-1.5 py-0.5 rounded-md font-semibold" style={{ backgroundColor: `${nodeColor}40`, color: nodeColor }}>
                                                                {node.type.replace(/_/g, ' ')}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-3 text-[10px] text-slate-300">
                                                            <span>Conf: <strong className="text-white">{(node.confidence * 100).toFixed(0)}%</strong></span>
                                                            <span>Deg: <strong className="text-white">{node.degree}</strong></span>
                                                            <span className="capitalize text-slate-400">{node.source}</span>
                                                        </div>
                                                    </div>
                                                </foreignObject>
                                            )}
                                        </g>
                                    );
                                })}
                            </svg>
                            </>
                        )}

                        {viewMode === "table" && (
                            <div className="w-full h-full p-12 overflow-auto">
                                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden max-w-5xl mx-auto">
                                     <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-start justify-between">
                                       <div>
                                         <h3 className="text-lg font-bold text-slate-800">Biological Entities Found</h3>
                                         <p className="text-sm text-slate-500 mt-1">
                                              Genes, drugs, pathways, and other biological entities identified in your query, cross-referenced with validated databases.
                                              {graphData.stats && ` ${graphData.stats.total_nodes} entities across ${Object.keys(graphData.stats.entity_types).length} types.`}
                                          </p>
                                       </div>
                                       <button
                                         onClick={exportCSV}
                                         className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:border-blue-400 hover:text-blue-600 rounded-lg text-xs font-medium text-slate-600 transition-all shadow-sm shrink-0"
                                       >
                                         <Download size={14} />
                                         Export CSV
                                       </button>
                                     </div>
                                    <table className="w-full text-sm text-left">
                                        <thead className="bg-slate-50 border-b border-slate-200">
                                             <tr>
                                                 <th className="px-6 py-4 font-semibold text-slate-700 w-1/4">Entity Name</th>
                                                 <th className="px-6 py-4 font-semibold text-slate-700 w-1/6">Type</th>
                                                 <th className="px-6 py-4 font-semibold text-slate-700 w-[80px]">Confidence</th>
                                                 <th className="px-6 py-4 font-semibold text-slate-700 w-[80px]">Source</th>
                                                 <th className="px-6 py-4 font-semibold text-slate-700">Context</th>
                                             </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {graphData.nodes.map((n) => (
                                                 <tr key={n.id} className="hover:bg-slate-50/50 transition-colors">
                                                     <td className="px-6 py-4 font-medium text-slate-900">{n.label || n.id}</td>
                                                     <td className="px-6 py-4">
                                                         <span 
                                                             className="px-2.5 py-1 rounded-full text-xs font-semibold text-white shadow-sm"
                                                             style={{backgroundColor: getNodeColor(n)}}
                                                         >
                                                             {n.type.replace(/_/g, ' ')}
                                                         </span>
                                                     </td>
                                                     <td className="px-6 py-4">
                                                         <div className="flex items-center gap-2">
                                                             <div className="w-12 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                                                 <div className="h-full rounded-full" style={{ width: `${(n.confidence || 0.5) * 100}%`, backgroundColor: getNodeColor(n) }} />
                                                             </div>
                                                             <span className="text-xs text-slate-500 font-mono">{((n.confidence || 0.5) * 100).toFixed(0)}%</span>
                                                         </div>
                                                     </td>
                                                     <td className="px-6 py-4">
                                                         <span className={`text-xs px-2 py-0.5 rounded-md font-medium ${
                                                             n.source === 'gliner2' ? 'bg-indigo-50 text-indigo-600' :
                                                             n.source === 'opentargets' ? 'bg-emerald-50 text-emerald-600' :
                                                             n.source === 'curated' ? 'bg-amber-50 text-amber-600' :
                                                             'bg-slate-50 text-slate-500'
                                                         }`}>
                                                             {n.source || 'unknown'}
                                                         </span>
                                                     </td>
                                                     <td className="px-6 py-4 text-slate-500 text-xs">
                                                         {(n.type === 'gene' || n.type === 'Gene') && `Potential driver or target in ${query.split(' ')[0]} context.`}
                                                         {(n.type === 'disease' || n.type === 'Disease') && `Clinical condition associated with retrieved targets.`}
                                                         {(n.type === 'drug' || n.type === 'Drug') && `Therapeutic agent interacting with this pathway.`}
                                                         {(n.type === 'mechanism' || n.type === 'Mechanism') && `Biological process implicated in resistance.`}
                                                         {n.type === 'pathway' && `Signaling pathway connected to query targets.`}
                                                         {n.type === 'mutation' && `Genetic alteration identified in query context.`}
                                                         {n.type === 'cell_type' && `Cell population relevant to the tumor microenvironment.`}
                                                         {n.type === 'biomarker' && `Predictive or prognostic biomarker.`}
                                                         {n.type === 'anatomical_site' && `Anatomical location of disease presentation.`}
                                                         {n.type === 'clinical_outcome' && `Treatment endpoint or clinical outcome measure.`}
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
                                             Discovery Potential
                                         </h3>
                                         <p className="text-xs text-slate-400 mb-6">
                                             How likely is this to lead to a new finding? High scores mean less explored territory.
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
                                 {papers.length > 0 && (
                                   <div className="max-w-7xl mx-auto mb-4 flex justify-end">
                                     <button
                                       onClick={exportBibTeX}
                                       className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:border-blue-400 hover:text-blue-600 rounded-lg text-xs font-medium text-slate-600 transition-all shadow-sm"
                                     >
                                       <Download size={14} />
                                       Export BibTeX
                                     </button>
                                   </div>
                                 )}
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

                        {viewMode === "validate" && (
                            <div className="w-full h-full bg-slate-50/30">
                                {validationError ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="bg-white p-8 rounded-2xl shadow-lg border border-red-200 max-w-md text-center">
                                            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                                                <XCircle className="text-red-500" size={32} />
                                            </div>
                                            <h3 className="text-lg font-bold text-slate-900 mb-2">Validation Failed</h3>
                                            <p className="text-slate-500 text-sm mb-4">{validationError}</p>
                                            <button onClick={() => { setValidationError(null); handleValidation(); }} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 flex items-center gap-2 mx-auto">
                                                <RefreshCw size={14} /> Retry
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <ValidationDashboard
                                        data={validationData}
                                        loading={validationLoading}
                                        onRun={handleValidation}
                                        gene={graphData?.nodes.find(n => n.type.toLowerCase() === 'gene')?.id}
                                        disease={graphData?.nodes.find(n => n.type.toLowerCase() === 'disease')?.id || "Cancer"}
                                    />
                                )}
                            </div>
                        )}

                        {viewMode === "pathway" && (
                            <div className="w-full h-full overflow-auto bg-slate-50/30 p-4">
                                <PathwayView
                                    nodes={graphData?.nodes || []}
                                    links={graphData?.links || []}
                                />
                            </div>
                        )}

                         {viewMode === "deep_research" && (
                             <div className="w-full h-full p-12 overflow-auto bg-slate-50/50">
                                 {!drData ? (
                                     <div className="flex flex-col items-center justify-center h-full">
                                         <div className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 max-w-md text-center">
                                             {drError ? (
                                               <>
                                                 <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                                                     <XCircle className="text-red-500" size={32} />
                                                 </div>
                                                 <h3 className="text-xl font-bold text-slate-900 mb-2">Analysis Failed</h3>
                                                 <p className="text-slate-500 mb-4">
                                                     The deep research analysis could not be completed. This usually means one of the upstream services is temporarily unavailable.
                                                 </p>
                                                 <p className="text-xs text-red-400 bg-red-50 p-2 rounded-lg mb-6 font-mono break-all">{drError}</p>
                                                 <button 
                                                     onClick={() => { setDrError(null); handleDeepResearch(); }}
                                                     className="w-full py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium transition-all shadow-md flex items-center justify-center gap-2"
                                                 >
                                                     <Sparkles size={18} />
                                                     Try Again
                                                 </button>
                                               </>
                                             ) : (
                                               <>
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
                                               </>
                                             )}
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
                                                        <h3 className="font-bold text-slate-700">Protein Structure Analysis</h3>
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
                                                                mutationAnalysis={drData.struct.mutation_analysis as any}
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
                                                                                    style={{ width: `${(drData.struct.mutation_analysis.impact_score ?? 0) * 100}%` }}
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
                                                        <h3 className="font-bold text-slate-700">Patent Landscape</h3>
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
                                                                <span className="text-sm font-medium text-slate-600">IP Competition Score</span>
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
                                                <div className="flex items-center justify-between mb-4">
                                                    <div className="flex items-center gap-2">
                                                        <Microscope className="text-emerald-500" />
                                                         <h3 className="font-bold text-slate-700">Cell Line Recommendations</h3>
                                                    </div>
                                                    {drData.models?.total_found && (
                                                        <span className="text-xs text-slate-400">{drData.models.total_found} models found</span>
                                                    )}
                                                </div>
                                                
                                                {/* Top Pick */}
                                                {drData.models?.top_pick && (
                                                    <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                                                        <div className="flex items-center justify-between mb-2">
                                                            <span className="text-xs font-semibold text-emerald-700 uppercase">Top Pick</span>
                                                            <span className="text-lg font-bold text-emerald-600">{drData.models.top_pick.match_score}%</span>
                                                        </div>
                                                        <div className="flex items-center justify-between">
                                                            <div>
                                                                <p className="font-bold text-slate-800">{drData.models.top_pick.name}</p>
                                                                <p className="text-xs text-slate-500">{drData.models.top_pick.disease}</p>
                                                            </div>
                                                            {drData.models.top_pick.mutation_match === "Exact" && (
                                                                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-medium rounded">
                                                                    Exact Mutation Match
                                                                </span>
                                                            )}
                                                        </div>
                                                        {drData.models.top_pick.mutations && drData.models.top_pick.mutations.length > 0 && (
                                                            <div className="mt-2 flex flex-wrap gap-1">
                                                                {drData.models.top_pick.mutations.slice(0, 3).map((mut: string, i: number) => (
                                                                    <span key={i} className="px-1.5 py-0.5 bg-slate-100 text-slate-600 text-[10px] rounded">
                                                                        {mut}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                                
                                                {/* Recommendations Table */}
                                                <div className="overflow-x-auto max-h-48">
                                                    <table className="w-full text-xs text-left">
                                                        <thead className="text-[10px] text-slate-500 bg-slate-50 uppercase sticky top-0">
                                                            <tr>
                                                                <th className="px-2 py-2">Cell Line</th>
                                                                <th className="px-2 py-2">Disease</th>
                                                                <th className="px-2 py-2">Data</th>
                                                                <th className="px-2 py-2">Score</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-slate-100">
                                                            {(drData.models?.recommendations || []).slice(0, 6).map((m: any, i: number) => (
                                                                <tr key={m.name || i} className={`${m.is_problematic ? 'bg-red-50/50' : 'hover:bg-slate-50'}`}>
                                                                    <td className="px-2 py-2">
                                                                        <div className="flex items-center gap-1">
                                                                            <span className="font-medium text-slate-700">{m.name}</span>
                                                                            {m.is_problematic && (
                                                                                <AlertTriangle className="w-3 h-3 text-amber-500" />
                                                                            )}
                                                                        </div>
                                                                    </td>
                                                                    <td className="px-2 py-2 text-slate-500 truncate max-w-[100px]" title={m.disease}>
                                                                        {m.disease}
                                                                    </td>
                                                                    <td className="px-2 py-2">
                                                                        <div className="flex gap-0.5">
                                                                            {(m.available_data || []).slice(0, 4).map((d: string, j: number) => (
                                                                                <span key={j} className="w-4 h-4 bg-blue-100 text-blue-600 rounded text-[8px] flex items-center justify-center" title={d}>
                                                                                    {d[0]}
                                                                                </span>
                                                                            ))}
                                                                        </div>
                                                                    </td>
                                                                    <td className="px-2 py-2">
                                                                        <span className={`font-bold ${
                                                                            m.match_score >= 80 ? 'text-emerald-600' :
                                                                            m.match_score >= 60 ? 'text-blue-600' :
                                                                            'text-slate-500'
                                                                        }`}>
                                                                            {m.match_score || Math.round((m.match_score || 0.8) * 100)}%
                                                                        </span>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                                
                                                {/* Avoid List */}
                                                {drData.models?.avoid_list && drData.models.avoid_list.length > 0 && (
                                                    <div className="mt-4 p-2 bg-amber-50 border border-amber-100 rounded-lg">
                                                        <span className="text-xs font-semibold text-amber-700 flex items-center gap-1 mb-1">
                                                            <AlertTriangle className="w-3 h-3" />
                                                            Lines to Avoid
                                                        </span>
                                                        <div className="flex flex-wrap gap-1">
                                                            {drData.models.avoid_list.slice(0, 3).map((line: any, i: number) => (
                                                                <span key={i} className="text-[10px] text-amber-700" title={line.problem_info?.issue}>
                                                                    {line.name}
                                                                    {i < 2 && ", "}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                
                                                {/* Notes */}
                                                {drData.models?.notes && drData.models.notes.length > 0 && (
                                                    <div className="mt-3 space-y-1">
                                                        {drData.models.notes.slice(0, 2).map((note: string, i: number) => (
                                                            <p key={i} className="text-[10px] text-slate-500">{note}</p>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>

                                            {/* Module D: Protocol */}
                                            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                                                <div className="flex items-center justify-between mb-4">
                                                    <div className="flex items-center gap-2">
                                                        <FileEdit className="text-indigo-500" />
                                                         <h3 className="font-bold text-slate-700">Experiment Protocol Generator</h3>
                                                    </div>
                                                    <span className={`text-xs px-2 py-1 rounded ${
                                                        drData.proto.generated_by === 'LLM' 
                                                            ? 'bg-purple-100 text-purple-700' 
                                                            : 'bg-slate-100 text-slate-600'
                                                    }`}>
                                                        {drData.proto.generated_by || 'Template'}
                                                    </span>
                                                </div>
                                                
                                                {/* gRNA Table (for CRISPR protocols) */}
                                                {drData.proto.grnas && drData.proto.grnas.length > 0 && (
                                                    <div className="mb-4">
                                                        <span className="text-xs font-semibold text-slate-600 block mb-2">
                                                            Designed gRNA Sequences
                                                        </span>
                                                        <div className="overflow-x-auto">
                                                            <table className="w-full text-[10px]">
                                                                <thead className="bg-indigo-50 text-indigo-700">
                                                                    <tr>
                                                                        <th className="px-2 py-1 text-left">#</th>
                                                                        <th className="px-2 py-1 text-left">Sequence</th>
                                                                        <th className="px-2 py-1">GC%</th>
                                                                        <th className="px-2 py-1">Score</th>
                                                                        <th className="px-2 py-1">Risk</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody className="divide-y divide-slate-100">
                                                                    {drData.proto.grnas.slice(0, 3).map((grna: any, i: number) => (
                                                                        <tr key={i} className={i === 0 ? 'bg-green-50' : ''}>
                                                                            <td className="px-2 py-1 font-medium">{i + 1}</td>
                                                                            <td className="px-2 py-1 font-mono">
                                                                                <code className="bg-slate-100 px-1 rounded text-[9px]">
                                                                                    {grna.sequence}
                                                                                </code>
                                                                            </td>
                                                                            <td className="px-2 py-1 text-center">{grna.gc_content}%</td>
                                                                            <td className="px-2 py-1 text-center">
                                                                                <span className={`font-bold ${
                                                                                    grna.score >= 0.7 ? 'text-green-600' :
                                                                                    grna.score >= 0.5 ? 'text-blue-600' : 'text-amber-600'
                                                                                }`}>
                                                                                    {grna.score}
                                                                                </span>
                                                                            </td>
                                                                            <td className="px-2 py-1 text-center">
                                                                                <span className={`px-1.5 py-0.5 rounded text-[8px] font-medium ${
                                                                                    grna.off_target_risk === 'Low' ? 'bg-green-100 text-green-700' :
                                                                                    grna.off_target_risk === 'Medium' ? 'bg-yellow-100 text-yellow-700' :
                                                                                    'bg-red-100 text-red-700'
                                                                                }`}>
                                                                                    {grna.off_target_risk}
                                                                                </span>
                                                                            </td>
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                        {drData.proto.grnas.length > 0 && (
                                                            <p className="text-[10px] text-slate-400 mt-1">
                                                                Top gRNA: <code className="bg-slate-100 px-1 rounded">{drData.proto.grnas[0].sequence}</code>
                                                            </p>
                                                        )}
                                                    </div>
                                                )}
                                                
                                                {/* Timeline (for CRISPR) */}
                                                {drData.proto.timeline && Array.isArray(drData.proto.timeline) && (
                                                    <div className="mb-4">
                                                        <span className="text-xs font-semibold text-slate-600 block mb-2">Timeline</span>
                                                        <div className="flex gap-1 overflow-x-auto pb-2">
                                                            {drData.proto.timeline.slice(0, 6).map((step: any, i: number) => (
                                                                <div key={i} className="flex-shrink-0 w-20 text-center">
                                                                    <div className="w-6 h-6 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center mx-auto text-[10px] font-bold">
                                                                        D{step.day}
                                                                    </div>
                                                                    <p className="text-[9px] text-slate-500 mt-1 leading-tight">{step.task}</p>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                
                                                {/* Protocol Content */}
                                                <div className="bg-slate-900 text-slate-300 p-4 rounded-lg font-mono text-xs max-h-64 overflow-y-auto whitespace-pre-wrap">
                                                    {drData.proto.content}
                                                </div>
                                                
                                                {/* Reagents */}
                                                {drData.proto.reagents && drData.proto.reagents.length > 0 && (
                                                    <div className="mt-3">
                                                        <span className="text-xs text-slate-500">Key Reagents: </span>
                                                        <span className="text-xs text-slate-600">
                                                            {drData.proto.reagents.slice(0, 4).map((r: any) => 
                                                                typeof r === 'string' ? r : r.name
                                                            ).join(', ')}
                                                        </span>
                                                    </div>
                                                )}
                                                
                                                <button 
                                                    onClick={() => {
                                                        navigator.clipboard.writeText(drData.proto.content);
                                                        showToast('Protocol copied to clipboard!');
                                                    }}
                                                    className="mt-4 w-full py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                                                >
                                                    <FileEdit className="w-4 h-4" />
                                                    Copy to Lab Notebook
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {viewMode === "trials" && (
                            <div className="w-full h-full overflow-auto bg-slate-50/30 p-6">
                                {trialsError ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="bg-white p-8 rounded-2xl shadow-lg border border-red-200 max-w-md text-center">
                                            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                                                <XCircle className="text-red-500" size={32} />
                                            </div>
                                            <h3 className="text-lg font-bold text-slate-900 mb-2">Trials Search Failed</h3>
                                            <p className="text-slate-500 text-sm mb-4">{trialsError}</p>
                                            <button onClick={() => { setTrialsError(null); handleTrialsSearch(); }} className="px-4 py-2 bg-cyan-600 text-white rounded-lg text-sm hover:bg-cyan-700 flex items-center gap-2 mx-auto">
                                                <RefreshCw size={14} /> Retry
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <ClinicalTrialsDashboard
                                        data={trialsData}
                                        loading={trialsLoading}
                                        onSearch={handleTrialsSearch}
                                        gene={graphData?.nodes.find(n => n.type.toLowerCase() === 'gene')?.id}
                                        disease={graphData?.nodes.find(n => n.type.toLowerCase() === 'disease')?.id || "Cancer"}
                                    />
                                )}
                            </div>
                        )}

                        {viewMode === "dossier" && (
                            <div className="w-full h-full overflow-auto bg-slate-50/30">
                                <TargetDossier
                                    data={dossierData}
                                    loading={dossierLoading}
                                    onGenerate={handleDossier}
                                    gene={graphData?.nodes.find(n => n.type.toLowerCase() === 'gene')?.id}
                                    disease={graphData?.nodes.find(n => n.type.toLowerCase() === 'disease')?.id || "Cancer"}
                                />
                            </div>
                        )}

                        {viewMode === "indications" && (
                            <div className="w-full h-full overflow-auto bg-slate-50/30">
                                <IndicationHeatmap
                                    data={indicationData}
                                    loading={indicationLoading}
                                    onFetch={handleIndications}
                                    gene={graphData?.nodes.find(n => n.type.toLowerCase() === 'gene')?.id}
                                />
                            </div>
                        )}

                        {viewMode === "whatif" && (
                            <div className="w-full h-full overflow-auto bg-slate-50/30">
                                <WhatIfSimulator
                                    result={whatIfResult}
                                    loading={whatIfLoading}
                                    availableNodes={(graphData?.nodes || []).map(n => ({ id: n.id, label: n.label || n.id, type: n.type }))}
                                    onSimulate={handleWhatIf}
                                    onReset={() => setWhatIfResult(null)}
                                />
                            </div>
                        )}

                        {viewMode === "competitive" && (
                            <div className="w-full h-full overflow-auto bg-slate-50/30">
                                <CompetitiveDashboard
                                    trialsData={trialsData}
                                    patentData={drData?.patent}
                                    gene={graphData?.nodes.find(n => n.type.toLowerCase() === 'gene')?.id}
                                    disease={graphData?.nodes.find(n => n.type.toLowerCase() === 'disease')?.id || "Cancer"}
                                />
                            </div>
                        )}
                    </>
                ) : (
                    <div className="flex items-center justify-center w-full h-full">
                      <div className="text-center">
                          <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
                              <Microscope size={40} className="text-slate-300" />
                          </div>
                           <h3 className="text-xl font-semibold text-slate-900 mb-2">Ready to Explore</h3>
                           <p className="text-slate-500 max-w-sm mx-auto">
                               Enter a question on the left to start your analysis and see the results here.
                           </p>
                      </div>
                    </div>
                )}
            </div>
        </section>
      </div>
      )}
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-[slideUp_0.3s_ease-out]">
          <div className="bg-slate-800 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 text-sm font-medium">
            <CheckCircle size={16} className="text-emerald-400 shrink-0" />
            {toast}
            <button onClick={() => setToast(null)} className="ml-2 text-slate-400 hover:text-white">
              <XIcon size={14} />
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
