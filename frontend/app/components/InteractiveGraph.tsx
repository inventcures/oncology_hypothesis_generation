"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, SimulationNodeDatum, SimulationLinkDatum } from "d3-force";

interface GraphNode {
  id: string; type: string; label: string; color: string; border_color: string;
  confidence: number; radius: number; degree: number; source: string; glow: boolean;
  relevance?: number; signal_role?: string;
  // d3 simulation adds these
  x?: number; y?: number; vx?: number; vy?: number; fx?: number | null; fy?: number | null;
  index?: number;
}

interface GraphLink {
  source: string | GraphNode; target: string | GraphNode;
  relation: string; label: string; weight: number; color: string;
  thickness: number; source_data: string; animated: boolean; signal_direction?: string;
}

interface InteractiveGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
  stats?: { total_nodes: number; total_edges: number; entity_types: Record<string, number>; relation_types: Record<string, number>; sources: Record<string, number>; };
  legend?: { type: string; color: string; count: number; label: string; }[];
}

export default function InteractiveGraph({ nodes: inputNodes, links: inputLinks, stats, legend }: InteractiveGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [simNodes, setSimNodes] = useState<GraphNode[]>([]);
  const [simLinks, setSimLinks] = useState<GraphLink[]>([]);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<number | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const simulationRef = useRef<any>(null);
  
  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  
  // Setup simulation
  useEffect(() => {
    if (inputNodes.length === 0) return;
    
    // Deep clone to avoid mutating props
    const nodesCopy: GraphNode[] = inputNodes.map(n => ({ ...n }));
    const linksCopy: GraphLink[] = inputLinks.map(l => ({ ...l, source: typeof l.source === 'object' ? l.source.id : l.source, target: typeof l.target === 'object' ? l.target.id : l.target }));
    
    const sim = forceSimulation<GraphNode>(nodesCopy)
      .force("link", forceLink<GraphNode, any>(linksCopy).id((d: any) => d.id).distance(100).strength(0.5))
      .force("charge", forceManyBody().strength(-300))
      .force("center", forceCenter(dimensions.width / 2, dimensions.height / 2))
      .force("collide", forceCollide<GraphNode>().radius((d: any) => (d.radius || 22) + 10))
      .alphaDecay(0.02)
      .on("tick", () => {
        setSimNodes([...nodesCopy]);
        setSimLinks([...linksCopy]);
      });
    
    simulationRef.current = sim;
    
    return () => { sim.stop(); };
  }, [inputNodes, inputLinks, dimensions.width, dimensions.height]);
  
  // Zoom handler
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform(prev => ({
      ...prev,
      scale: Math.max(0.2, Math.min(5, prev.scale * scaleFactor)),
    }));
  }, []);
  
  // Pan handlers
  const handleBgMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as SVGElement).tagName === 'rect') {
      setIsPanning(true);
      setPanStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
    }
  }, [transform]);
  
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isPanning) {
      setTransform(prev => ({ ...prev, x: e.clientX - panStart.x, y: e.clientY - panStart.y }));
    }
    if (dragging && simulationRef.current) {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const x = (e.clientX - rect.left - transform.x) / transform.scale;
      const y = (e.clientY - rect.top - transform.y) / transform.scale;
      
      const node = simNodes.find(n => n.id === dragging);
      if (node) {
        node.fx = x;
        node.fy = y;
        simulationRef.current.alpha(0.3).restart();
      }
    }
  }, [isPanning, panStart, dragging, simNodes, transform]);
  
  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    if (dragging) {
      const node = simNodes.find(n => n.id === dragging);
      if (node) {
        node.fx = null;
        node.fy = null;
      }
      setDragging(null);
    }
  }, [dragging, simNodes]);
  
  const handleNodeMouseDown = useCallback((e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation();
    setDragging(nodeId);
    const node = simNodes.find(n => n.id === nodeId);
    if (node) {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      node.fx = (e.clientX - rect.left - transform.x) / transform.scale;
      node.fy = (e.clientY - rect.top - transform.y) / transform.scale;
    }
  }, [simNodes, transform]);
  
  const getSourceTarget = (link: GraphLink): { source: GraphNode | null; target: GraphNode | null } => {
    const srcId = typeof link.source === 'object' ? link.source.id : link.source;
    const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
    return {
      source: simNodes.find(n => n.id === srcId) || null,
      target: simNodes.find(n => n.id === tgtId) || null,
    };
  };
  
  // Reset view
  const resetView = useCallback(() => {
    setTransform({ x: 0, y: 0, scale: 1 });
    setSelectedNode(null);
    setHoveredNode(null);
  }, []);
  
  return (
    <div ref={containerRef} className="w-full h-full relative">
      {/* Controls */}
      <div className="absolute top-4 left-4 z-20 flex gap-1 bg-white/90 backdrop-blur-sm rounded-lg border border-slate-200 shadow-sm p-1">
        <button onClick={() => setTransform(p => ({ ...p, scale: Math.min(5, p.scale * 1.3) }))} className="px-2 py-1 text-xs hover:bg-slate-100 rounded" title="Zoom in">+</button>
        <button onClick={() => setTransform(p => ({ ...p, scale: Math.max(0.2, p.scale * 0.7) }))} className="px-2 py-1 text-xs hover:bg-slate-100 rounded" title="Zoom out">-</button>
        <button onClick={resetView} className="px-2 py-1 text-xs hover:bg-slate-100 rounded text-slate-500" title="Reset">Reset</button>
      </div>
      
      {/* Legend */}
      <div className="absolute top-4 right-4 z-20 bg-white/95 backdrop-blur-sm p-3 rounded-xl border border-slate-200 shadow-lg text-xs space-y-1.5 min-w-[160px]">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Entities</span>
          {stats && <span className="text-[10px] text-slate-400">{stats.total_nodes}N / {stats.total_edges}E</span>}
        </div>
        {(legend || []).map(item => (
          <div key={item.type} className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
              <span className="text-slate-600">{item.label}</span>
            </div>
            <span className="text-slate-400 font-mono">{item.count}</span>
          </div>
        ))}
        <div className="border-t border-slate-100 pt-1.5 mt-1.5 text-[10px] text-slate-400">
          Scroll to zoom | Drag to pan | Drag nodes
        </div>
      </div>
      
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="cursor-grab active:cursor-grabbing"
        onWheel={handleWheel}
        onMouseDown={handleBgMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          {Array.from(new Set(simLinks.map(l => l.color || '#94a3b8'))).map(color => (
            <marker key={`arrow-${color}`} id={`ig-arrow-${color.replace('#','')}`} markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto" markerUnits="userSpaceOnUse">
              <polygon points="0 0, 8 3, 0 6" fill={`${color}cc`} />
            </marker>
          ))}
          <filter id="ig-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        
        {/* Pan/zoom background */}
        <rect width={dimensions.width} height={dimensions.height} fill="transparent" />
        
        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.scale})`}>
          {/* Edges */}
          {simLinks.map((link, i) => {
            const { source: sn, target: tn } = getSourceTarget(link);
            if (!sn || !tn || sn.x == null || tn.x == null) return null;
            
            const srcId = typeof link.source === 'object' ? link.source.id : link.source;
            const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
            const isConnectedToHover = hoveredNode === srcId || hoveredNode === tgtId;
            const isDimmed = hoveredNode !== null && !isConnectedToHover;
            const isHovered = hoveredEdge === i;
            const edgeColor = link.color || "#94a3b8";
            const thickness = link.thickness || (1 + link.weight * 3);
            
            const dx = tn.x! - sn.x!;
            const dy = tn.y! - sn.y!;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const sR = sn.radius || 22;
            const tR = tn.radius || 22;
            const sx = sn.x! + (dx / dist) * sR;
            const sy = sn.y! + (dy / dist) * sR;
            const tx = tn.x! - (dx / dist) * (tR + 8);
            const ty = tn.y! - (dy / dist) * (tR + 8);
            const mx = (sx + tx) / 2;
            const my = (sy + ty) / 2;
            
            return (
              <g key={`e-${i}`}>
                <line x1={sx} y1={sy} x2={tx} y2={ty} stroke="transparent" strokeWidth={14} className="cursor-pointer" onMouseEnter={() => setHoveredEdge(i)} onMouseLeave={() => setHoveredEdge(null)} />
                <line x1={sx} y1={sy} x2={tx} y2={ty} stroke={edgeColor} strokeWidth={isHovered ? thickness + 1 : thickness} strokeOpacity={isDimmed ? 0.1 : isHovered ? 1 : 0.6} markerEnd={`url(#ig-arrow-${edgeColor.replace('#','')})`} strokeLinecap="round" className="transition-opacity duration-150" />
                {(isHovered || isConnectedToHover) && !isDimmed && (
                  <>
                    <rect x={mx - 30} y={my - 10} width="60" height="20" rx="5" fill={edgeColor} fillOpacity={0.95} />
                    <text x={mx} y={my + 2} textAnchor="middle" dominantBaseline="middle" className="text-[8px] fill-white font-bold select-none pointer-events-none">{link.label || link.relation.replace(/_/g, ' ')}</text>
                  </>
                )}
              </g>
            );
          })}
          
          {/* Nodes */}
          {simNodes.map(node => {
            if (node.x == null || node.y == null) return null;
            const isHovered = hoveredNode === node.id;
            const isSelected = selectedNode === node.id;
            const isDimmed = hoveredNode !== null && !isHovered && !simLinks.some(l => {
              const sid = typeof l.source === 'object' ? l.source.id : l.source;
              const tid = typeof l.target === 'object' ? l.target.id : l.target;
              return (sid === hoveredNode && tid === node.id) || (tid === hoveredNode && sid === node.id);
            });
            const r = isHovered ? (node.radius || 22) + 3 : (node.radius || 22);
            
            return (
              <g key={node.id} transform={`translate(${node.x},${node.y})`} className={`cursor-pointer ${node.glow && !isDimmed ? '' : ''}`} opacity={isDimmed ? 0.2 : 1}
                onMouseEnter={() => !dragging && setHoveredNode(node.id)}
                onMouseLeave={() => !dragging && setHoveredNode(null)}
                onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                onClick={() => setSelectedNode(selectedNode === node.id ? null : node.id)}
              >
                {isSelected && <circle r={r + 5} fill="none" stroke={node.color} strokeWidth={2} strokeDasharray="4 3" opacity={0.6} />}
                <circle r={r + 2} fill="none" stroke={node.color} strokeWidth={2} strokeDasharray={`${node.confidence * 2 * Math.PI * (r + 2)} ${2 * Math.PI * (r + 2)}`} opacity={0.3} transform="rotate(-90)" />
                <circle r={r} fill={node.color} stroke="white" strokeWidth={isHovered ? 3.5 : 2.5} className="drop-shadow-md" filter={node.glow ? "url(#ig-glow)" : undefined} />
                <text dy={r + 14} textAnchor="middle" className="text-[9px] font-bold fill-slate-600 pointer-events-none select-none" style={{ textShadow: '0 1px 2px rgba(255,255,255,0.8)' }}>
                  {(node.label || node.id).length > 14 ? (node.label || node.id).slice(0, 12) + '...' : (node.label || node.id)}
                </text>
                <text dy={1} textAnchor="middle" dominantBaseline="middle" fill="white" fontSize={r > 28 ? "11" : "9"} fontWeight="bold" className="pointer-events-none select-none">
                  {(node.type || '').replace(/_/g, '').slice(0, 2).toUpperCase()}
                </text>
                
                {isHovered && (
                  <foreignObject x="-90" y={-(r + 70)} width="180" height="65" className="pointer-events-none">
                    <div className="bg-slate-800/95 backdrop-blur text-white text-xs rounded-lg py-2 px-3 shadow-2xl">
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-bold text-[10px] truncate max-w-[120px]">{node.label || node.id}</p>
                        <span className="text-[8px] px-1 py-0.5 rounded" style={{ backgroundColor: `${node.color}40`, color: node.color }}>{node.type.replace(/_/g, ' ')}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[9px] text-slate-300">
                        <span>Conf: <strong className="text-white">{(node.confidence * 100).toFixed(0)}%</strong></span>
                        <span>Deg: <strong className="text-white">{node.degree}</strong></span>
                        {node.relevance ? <span>Rel: <strong className="text-white">{(node.relevance * 100).toFixed(0)}%</strong></span> : null}
                      </div>
                    </div>
                  </foreignObject>
                )}
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
