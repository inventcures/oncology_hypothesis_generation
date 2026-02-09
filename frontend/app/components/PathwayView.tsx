"use client";

import { useState, useMemo, useCallback } from "react";
import { ArrowRight, Info } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GraphNode {
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
  signal_role?: "upstream" | "downstream" | "target";
}

interface GraphLink {
  source: string;
  target: string;
  relation: string;
  label: string;
  weight: number;
  color: string;
  thickness: number;
  source_data: string;
  animated: boolean;
  signal_direction?: "upstream" | "downstream";
}

interface Props {
  nodes: GraphNode[];
  links: GraphLink[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const VIEW_W = 800;
const VIEW_H = 500;

const ACTIVATING_COLOR = "#22c55e";
const INHIBITING_COLOR = "#ef4444";

const COL_X = {
  upstream: 150,
  target: VIEW_W / 2,
  downstream: VIEW_W - 150,
} as const;

const PATHWAY_ROW_Y = VIEW_H - 55;

const NODE_W = 130;
const NODE_H = 40;
const TARGET_W = 160;
const TARGET_H = 52;

const NODE_RX = 8;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isInhibiting(link: GraphLink): boolean {
  if (link.color === INHIBITING_COLOR) return true;
  const rel = (link.relation || link.label || "").toLowerCase();
  return rel.includes("inhibit") || rel.includes("repress") || rel.includes("suppress") || rel.includes("block");
}

function relationLabel(link: GraphLink): string {
  return link.label || link.relation?.replace(/_/g, " ") || "related";
}

/** Distribute items vertically within a column, centered around VIEW_H/2. */
function distributeY(count: number, centerY: number, spacing: number): number[] {
  if (count === 0) return [];
  const totalHeight = (count - 1) * spacing;
  const startY = centerY - totalHeight / 2;
  return Array.from({ length: count }, (_, i) => startY + i * spacing);
}

/** Compute a cubic bezier path for a curved arrow between two rectangles. */
function curvedPath(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  curvature: number = 0.4,
): string {
  const dx = x2 - x1;
  const cp1x = x1 + dx * curvature;
  const cp2x = x2 - dx * curvature;
  return `M ${x1} ${y1} C ${cp1x} ${y1}, ${cp2x} ${y2}, ${x2} ${y2}`;
}

/** Get the edge connection points for source/target rectangles. */
function getEdgeEndpoints(
  srcX: number,
  srcY: number,
  srcW: number,
  tgtX: number,
  tgtY: number,
  tgtW: number,
): { x1: number; y1: number; x2: number; y2: number } {
  const goesRight = tgtX > srcX;
  const goesLeft = tgtX < srcX;
  // Horizontal flow: exit right side of source, enter left side of target
  if (goesRight) {
    return { x1: srcX + srcW / 2, y1: srcY, x2: tgtX - tgtW / 2, y2: tgtY };
  }
  if (goesLeft) {
    return { x1: srcX - srcW / 2, y1: srcY, x2: tgtX + tgtW / 2, y2: tgtY };
  }
  // Same column — connect bottom-to-top or top-to-bottom
  if (tgtY > srcY) {
    return { x1: srcX, y1: srcY + NODE_H / 2, x2: tgtX, y2: tgtY - NODE_H / 2 };
  }
  return { x1: srcX, y1: srcY - NODE_H / 2, x2: tgtX, y2: tgtY + NODE_H / 2 };
}

/** Resolve node color with fallback. */
function nodeColor(node: GraphNode): string {
  if (node.color) return node.color;
  const map: Record<string, string> = {
    gene: "#3b82f6",
    disease: "#ef4444",
    drug: "#10b981",
    pathway: "#8b5cf6",
    mutation: "#f59e0b",
    cell_type: "#06b6d4",
    biomarker: "#ec4899",
    mechanism: "#6366f1",
  };
  return map[node.type.toLowerCase()] || "#9ca3af";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full py-20 px-8 text-center">
      <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-5">
        <Info className="text-slate-400" size={28} />
      </div>
      <p className="text-base font-semibold text-slate-600 mb-2">
        No signaling pathway data available for this query.
      </p>
      <p className="text-sm text-slate-400 max-w-md">
        Try querying a specific gene like KRAS, EGFR, or TP53.
      </p>
    </div>
  );
}

interface TooltipData {
  x: number;
  y: number;
  name: string;
  type: string;
  confidence: number;
  role?: string;
}

function NodeTooltip({ data }: { data: TooltipData }) {
  // Position tooltip above the node, clamped to viewport
  const tx = Math.max(80, Math.min(data.x, VIEW_W - 80));
  const ty = data.y - 50;
  return (
    <g className="pointer-events-none">
      <foreignObject x={tx - 75} y={ty - 36} width={150} height={72}>
        <div className="bg-slate-800 text-white text-xs rounded-lg px-3 py-2 shadow-xl border border-slate-600/30 backdrop-blur">
          <p className="font-bold text-[11px] truncate">{data.name}</p>
          <div className="flex items-center justify-between mt-1 gap-2">
            <span className="text-slate-300 capitalize">{data.type.replace(/_/g, " ")}</span>
            <span className="font-mono text-[10px] text-slate-400">
              {(data.confidence * 100).toFixed(0)}%
            </span>
          </div>
          {data.role && (
            <span className="text-[9px] text-blue-300 capitalize">{data.role}</span>
          )}
        </div>
      </foreignObject>
    </g>
  );
}

interface EdgeTooltipData {
  x: number;
  y: number;
  label: string;
  weight: number;
}

function EdgeTooltip({ data }: { data: EdgeTooltipData }) {
  const tx = Math.max(60, Math.min(data.x, VIEW_W - 60));
  return (
    <g className="pointer-events-none">
      <foreignObject x={tx - 55} y={data.y - 28} width={110} height={32}>
        <div className="bg-slate-800 text-white text-[10px] rounded-md px-2 py-1 shadow-lg border border-slate-600/30 text-center truncate">
          {data.label}
        </div>
      </foreignObject>
    </g>
  );
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

function Legend({ nodeTypes }: { nodeTypes: { type: string; color: string }[] }) {
  return (
    <g transform={`translate(${VIEW_W - 165}, 12)`}>
      <rect x={0} y={0} width={155} height={nodeTypes.length * 20 + 65} rx={8} fill="white" fillOpacity={0.95} stroke="#e2e8f0" strokeWidth={1} />

      {/* Title */}
      <text x={10} y={18} className="text-[9px] font-bold fill-slate-400 uppercase" style={{ letterSpacing: "0.05em" }}>
        Legend
      </text>

      {/* Activating arrow */}
      <line x1={10} y1={34} x2={36} y2={34} stroke={ACTIVATING_COLOR} strokeWidth={2} />
      <polygon points="36,30 44,34 36,38" fill={ACTIVATING_COLOR} />
      <text x={50} y={37} className="text-[10px] fill-slate-600">Activating</text>

      {/* Inhibiting arrow */}
      <line x1={10} y1={50} x2={36} y2={50} stroke={INHIBITING_COLOR} strokeWidth={2} strokeDasharray="4 3" />
      <polygon points="36,46 44,50 36,54" fill={INHIBITING_COLOR} />
      <text x={50} y={53} className="text-[10px] fill-slate-600">Inhibiting</text>

      {/* Node types */}
      {nodeTypes.map((nt, i) => (
        <g key={nt.type} transform={`translate(10, ${65 + i * 20})`}>
          <rect x={0} y={-5} width={12} height={12} rx={3} fill={nt.color} />
          <text x={18} y={5} className="text-[10px] fill-slate-600 capitalize">
            {nt.type.replace(/_/g, " ")}
          </text>
        </g>
      ))}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function PathwayView({ nodes, links }: Props) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<number | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // -----------------------------------------------------------------------
  // Determine if signal_role data exists
  // -----------------------------------------------------------------------
  const hasSignalData = useMemo(
    () => nodes.some((n) => n.signal_role),
    [nodes],
  );

  if (!hasSignalData) {
    return <EmptyState />;
  }

  // -----------------------------------------------------------------------
  // Partition nodes by role
  // -----------------------------------------------------------------------
  const { upstreamNodes, targetNodes, downstreamNodes, pathwayNodes } = useMemo(() => {
    const up: GraphNode[] = [];
    const tgt: GraphNode[] = [];
    const down: GraphNode[] = [];
    const pw: GraphNode[] = [];

    for (const n of nodes) {
      if (n.type.toLowerCase() === "pathway") {
        pw.push(n);
      } else if (n.signal_role === "upstream") {
        up.push(n);
      } else if (n.signal_role === "target") {
        tgt.push(n);
      } else if (n.signal_role === "downstream") {
        down.push(n);
      }
    }
    return { upstreamNodes: up, targetNodes: tgt, downstreamNodes: down, pathwayNodes: pw };
  }, [nodes]);

  // -----------------------------------------------------------------------
  // Layout: assign positions to each node
  // -----------------------------------------------------------------------
  const positionMap = useMemo(() => {
    const map: Record<string, { x: number; y: number; w: number; h: number }> = {};

    const centerY = (VIEW_H - 60) / 2; // leave room for pathway row
    const colSpacing = 56;

    // Upstream column
    const upYs = distributeY(upstreamNodes.length, centerY, colSpacing);
    upstreamNodes.forEach((n, i) => {
      map[n.id] = { x: COL_X.upstream, y: upYs[i], w: NODE_W, h: NODE_H };
    });

    // Target column
    const tgtYs = distributeY(targetNodes.length, centerY, colSpacing + 10);
    targetNodes.forEach((n, i) => {
      map[n.id] = { x: COL_X.target, y: tgtYs[i], w: TARGET_W, h: TARGET_H };
    });

    // Downstream column
    const downYs = distributeY(downstreamNodes.length, centerY, colSpacing);
    downstreamNodes.forEach((n, i) => {
      map[n.id] = { x: COL_X.downstream, y: downYs[i], w: NODE_W, h: NODE_H };
    });

    // Pathway row (bottom, spread evenly)
    const pwCount = pathwayNodes.length;
    if (pwCount > 0) {
      const pwSpacing = Math.min(160, (VIEW_W - 100) / pwCount);
      const totalPwWidth = (pwCount - 1) * pwSpacing;
      const startPwX = VIEW_W / 2 - totalPwWidth / 2;
      pathwayNodes.forEach((n, i) => {
        map[n.id] = { x: startPwX + i * pwSpacing, y: PATHWAY_ROW_Y, w: NODE_W, h: NODE_H };
      });
    }

    return map;
  }, [upstreamNodes, targetNodes, downstreamNodes, pathwayNodes]);

  // -----------------------------------------------------------------------
  // Connected edges for a hovered node
  // -----------------------------------------------------------------------
  const connectedEdgeIndices = useMemo(() => {
    if (!hoveredNode) return new Set<number>();
    const s = new Set<number>();
    links.forEach((l, i) => {
      if (l.source === hoveredNode || l.target === hoveredNode) s.add(i);
    });
    return s;
  }, [hoveredNode, links]);

  const connectedNodeIds = useMemo(() => {
    if (!hoveredNode) return new Set<string>();
    const s = new Set<string>([hoveredNode]);
    links.forEach((l) => {
      if (l.source === hoveredNode) s.add(l.target);
      if (l.target === hoveredNode) s.add(l.source);
    });
    return s;
  }, [hoveredNode, links]);

  // -----------------------------------------------------------------------
  // Unique node types for legend
  // -----------------------------------------------------------------------
  const legendNodeTypes = useMemo(() => {
    const seen = new Map<string, string>();
    for (const n of nodes) {
      const t = n.type.toLowerCase();
      if (!seen.has(t)) {
        seen.set(t, nodeColor(n));
      }
    }
    return Array.from(seen.entries()).map(([type, color]) => ({ type, color }));
  }, [nodes]);

  // -----------------------------------------------------------------------
  // Toggle expanded node
  // -----------------------------------------------------------------------
  const toggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  // -----------------------------------------------------------------------
  // Tooltip state
  // -----------------------------------------------------------------------
  const tooltipData: TooltipData | null = useMemo(() => {
    if (!hoveredNode) return null;
    const n = nodes.find((nd) => nd.id === hoveredNode);
    if (!n) return null;
    const pos = positionMap[n.id];
    if (!pos) return null;
    return {
      x: pos.x,
      y: pos.y - pos.h / 2,
      name: n.label || n.id,
      type: n.type,
      confidence: n.confidence ?? 0.5,
      role: n.signal_role,
    };
  }, [hoveredNode, nodes, positionMap]);

  const edgeTooltipData: EdgeTooltipData | null = useMemo(() => {
    if (hoveredEdge === null) return null;
    const link = links[hoveredEdge];
    if (!link) return null;
    const srcPos = positionMap[link.source];
    const tgtPos = positionMap[link.target];
    if (!srcPos || !tgtPos) return null;
    return {
      x: (srcPos.x + tgtPos.x) / 2,
      y: (srcPos.y + tgtPos.y) / 2 - 16,
      label: relationLabel(link),
      weight: link.weight,
    };
  }, [hoveredEdge, links, positionMap]);

  // -----------------------------------------------------------------------
  // Render a single node rectangle
  // -----------------------------------------------------------------------
  const renderNode = useCallback(
    (node: GraphNode) => {
      const pos = positionMap[node.id];
      if (!pos) return null;

      const isTarget = node.signal_role === "target";
      const w = pos.w;
      const h = pos.h;
      const color = nodeColor(node);
      const isHovered = hoveredNode === node.id;
      const isDimmed = hoveredNode !== null && !connectedNodeIds.has(node.id);
      const isExpanded = expandedNodes.has(node.id);

      // Expanded: show connected edges from this node
      const expandedLinks = isExpanded
        ? links.filter(
            (l) =>
              (l.source === node.id || l.target === node.id) &&
              positionMap[l.source] &&
              positionMap[l.target],
          )
        : [];

      return (
        <g
          key={node.id}
          transform={`translate(${pos.x}, ${pos.y})`}
          className="cursor-pointer"
          onMouseEnter={() => setHoveredNode(node.id)}
          onMouseLeave={() => setHoveredNode(null)}
          onClick={() => toggleExpand(node.id)}
          opacity={isDimmed ? 0.2 : 1}
          style={{ transition: "opacity 200ms" }}
        >
          {/* Target glow */}
          {isTarget && (
            <rect
              x={-w / 2 - 4}
              y={-h / 2 - 4}
              width={w + 8}
              height={h + 8}
              rx={NODE_RX + 2}
              fill="none"
              stroke={color}
              strokeWidth={2}
              opacity={0.4}
              className="animate-pulse"
            />
          )}

          {/* Expanded highlight ring */}
          {isExpanded && (
            <rect
              x={-w / 2 - 6}
              y={-h / 2 - 6}
              width={w + 12}
              height={h + 12}
              rx={NODE_RX + 3}
              fill="none"
              stroke={color}
              strokeWidth={1.5}
              strokeDasharray="5 3"
              opacity={0.5}
            />
          )}

          {/* Main rectangle */}
          <rect
            x={-w / 2}
            y={-h / 2}
            width={w}
            height={h}
            rx={NODE_RX}
            fill="white"
            stroke={isHovered ? color : "#e2e8f0"}
            strokeWidth={isHovered ? 2 : 1}
            className="drop-shadow-sm"
          />

          {/* Color accent bar (left border) */}
          <rect
            x={-w / 2}
            y={-h / 2}
            width={5}
            height={h}
            rx={2}
            fill={color}
          />
          {/* Round the top-left and bottom-left with a clip */}
          <clipPath id={`clip-accent-${node.id}`}>
            <rect x={-w / 2} y={-h / 2} width={5} height={h} rx={NODE_RX} />
          </clipPath>
          <rect
            x={-w / 2}
            y={-h / 2}
            width={5}
            height={h}
            fill={color}
            clipPath={`url(#clip-accent-${node.id})`}
          />

          {/* Label */}
          <text
            x={0}
            y={isTarget ? -4 : 0}
            textAnchor="middle"
            dominantBaseline="middle"
            className={`font-semibold fill-slate-700 pointer-events-none select-none ${isTarget ? "text-[12px]" : "text-[10px]"}`}
          >
            {(node.label || node.id).length > 18
              ? (node.label || node.id).slice(0, 16) + "..."
              : node.label || node.id}
          </text>

          {/* Type subtitle for target */}
          {isTarget && (
            <text
              x={0}
              y={12}
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-[9px] fill-slate-400 pointer-events-none select-none uppercase"
              style={{ letterSpacing: "0.05em" }}
            >
              Target
            </text>
          )}

          {/* Confidence bar */}
          <rect
            x={-w / 2 + 8}
            y={h / 2 - 5}
            width={w - 16}
            height={2}
            rx={1}
            fill="#e2e8f0"
          />
          <rect
            x={-w / 2 + 8}
            y={h / 2 - 5}
            width={Math.max(0, (w - 16) * (node.confidence ?? 0.5))}
            height={2}
            rx={1}
            fill={color}
            opacity={0.6}
          />

          {/* Expand indicator */}
          {expandedLinks.length > 0 && (
            <circle cx={w / 2 - 8} cy={-h / 2 + 8} r={4} fill={color} opacity={0.6} />
          )}
        </g>
      );
    },
    [positionMap, hoveredNode, connectedNodeIds, expandedNodes, links, toggleExpand],
  );

  // -----------------------------------------------------------------------
  // Render edges
  // -----------------------------------------------------------------------
  const renderEdge = useCallback(
    (link: GraphLink, index: number) => {
      const srcPos = positionMap[link.source];
      const tgtPos = positionMap[link.target];
      if (!srcPos || !tgtPos) return null;

      const inhibiting = isInhibiting(link);
      const edgeColor = inhibiting ? INHIBITING_COLOR : (link.color === INHIBITING_COLOR ? INHIBITING_COLOR : (link.color === ACTIVATING_COLOR ? ACTIVATING_COLOR : ACTIVATING_COLOR));
      const arrowId = `pathway-arrow-${index}`;
      const isEdgeHovered = hoveredEdge === index;
      const isConnected = connectedEdgeIndices.has(index);
      const isDimmed = hoveredNode !== null && !isConnected;
      const thickness = isEdgeHovered ? 2.5 : (link.thickness ? Math.min(link.thickness, 3) : 1.5);

      const ep = getEdgeEndpoints(srcPos.x, srcPos.y, srcPos.w, tgtPos.x, tgtPos.y, tgtPos.w);
      const pathD = curvedPath(ep.x1, ep.y1, ep.x2, ep.y2);

      return (
        <g key={`edge-${index}`}>
          <defs>
            <marker
              id={arrowId}
              markerWidth="8"
              markerHeight="6"
              refX="7"
              refY="3"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <polygon points="0 0, 8 3, 0 6" fill={edgeColor} opacity={isDimmed ? 0.15 : 0.85} />
            </marker>
          </defs>

          {/* Invisible hit area */}
          <path
            d={pathD}
            stroke="transparent"
            strokeWidth={14}
            fill="none"
            className="cursor-pointer"
            onMouseEnter={() => setHoveredEdge(index)}
            onMouseLeave={() => setHoveredEdge(null)}
          />

          {/* Visible path */}
          <path
            d={pathD}
            stroke={edgeColor}
            strokeWidth={thickness}
            strokeOpacity={isDimmed ? 0.1 : isEdgeHovered || isConnected ? 0.9 : 0.5}
            strokeDasharray={inhibiting ? "6 4" : "none"}
            fill="none"
            markerEnd={`url(#${arrowId})`}
            style={{ transition: "stroke-opacity 200ms, stroke-width 200ms" }}
          />
        </g>
      );
    },
    [positionMap, hoveredNode, hoveredEdge, connectedEdgeIndices],
  );

  // -----------------------------------------------------------------------
  // Column headers
  // -----------------------------------------------------------------------
  const columnHeaders = useMemo(() => {
    const headers: { x: number; label: string }[] = [];
    if (upstreamNodes.length > 0) {
      headers.push({ x: COL_X.upstream, label: "Upstream" });
    }
    if (targetNodes.length > 0) {
      headers.push({ x: COL_X.target, label: "Target" });
    }
    if (downstreamNodes.length > 0) {
      headers.push({ x: COL_X.downstream, label: "Downstream" });
    }
    return headers;
  }, [upstreamNodes.length, targetNodes.length, downstreamNodes.length]);

  // -----------------------------------------------------------------------
  // Pathway label row header
  // -----------------------------------------------------------------------
  const hasPathways = pathwayNodes.length > 0;

  // -----------------------------------------------------------------------
  // All laid-out nodes (in render order)
  // -----------------------------------------------------------------------
  const allNodes = useMemo(
    () => [...upstreamNodes, ...targetNodes, ...downstreamNodes, ...pathwayNodes],
    [upstreamNodes, targetNodes, downstreamNodes, pathwayNodes],
  );

  // -----------------------------------------------------------------------
  // Flow arrows between columns (decorative)
  // -----------------------------------------------------------------------
  const flowArrows = useMemo(() => {
    const arrows: { x: number; y: number }[] = [];
    const midY = (VIEW_H - 60) / 2;

    if (upstreamNodes.length > 0 && targetNodes.length > 0) {
      arrows.push({ x: (COL_X.upstream + COL_X.target) / 2, y: midY });
    }
    if (targetNodes.length > 0 && downstreamNodes.length > 0) {
      arrows.push({ x: (COL_X.target + COL_X.downstream) / 2, y: midY });
    }
    return arrows;
  }, [upstreamNodes.length, targetNodes.length, downstreamNodes.length]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="w-full h-full flex flex-col bg-slate-50 rounded-lg overflow-hidden">
      <svg
        className="w-full h-full"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Glow filter for target node */}
          <filter id="pathway-target-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background */}
        <rect x={0} y={0} width={VIEW_W} height={VIEW_H} fill="#f8fafc" rx={8} />

        {/* Subtle grid */}
        <g opacity={0.04}>
          {Array.from({ length: 21 }, (_, i) => (
            <line
              key={`gv-${i}`}
              x1={i * 40}
              y1={0}
              x2={i * 40}
              y2={VIEW_H}
              stroke="#0f172a"
              strokeWidth={0.5}
            />
          ))}
          {Array.from({ length: 14 }, (_, i) => (
            <line
              key={`gh-${i}`}
              x1={0}
              y1={i * 40}
              x2={VIEW_W}
              y2={i * 40}
              stroke="#0f172a"
              strokeWidth={0.5}
            />
          ))}
        </g>

        {/* Column headers */}
        {columnHeaders.map((ch) => (
          <text
            key={ch.label}
            x={ch.x}
            y={22}
            textAnchor="middle"
            className="text-[10px] font-bold fill-slate-400 uppercase pointer-events-none select-none"
            style={{ letterSpacing: "0.08em" }}
          >
            {ch.label}
          </text>
        ))}

        {/* Pathway row header */}
        {hasPathways && (
          <text
            x={35}
            y={PATHWAY_ROW_Y}
            textAnchor="start"
            dominantBaseline="middle"
            className="text-[9px] font-bold fill-slate-400 uppercase pointer-events-none select-none"
            style={{ letterSpacing: "0.06em" }}
          >
            Pathways
          </text>
        )}

        {/* Decorative flow direction arrows */}
        {flowArrows.map((fa, i) => (
          <g key={`flow-${i}`} transform={`translate(${fa.x}, ${fa.y})`} opacity={0.15}>
            <polygon points="-8,-6 4,0 -8,6" fill="#64748b" />
          </g>
        ))}

        {/* === EDGES === */}
        <g>
          {links.map((link, i) => renderEdge(link, i))}
        </g>

        {/* === NODES === */}
        <g>
          {allNodes.map((node) => renderNode(node))}
        </g>

        {/* Edge tooltip */}
        {edgeTooltipData && <EdgeTooltip data={edgeTooltipData} />}

        {/* Node tooltip */}
        {tooltipData && <NodeTooltip data={tooltipData} />}

        {/* Legend */}
        <Legend nodeTypes={legendNodeTypes} />
      </svg>
    </div>
  );
}
