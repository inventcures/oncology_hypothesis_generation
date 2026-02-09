"use client";

import { useEffect, useRef, useState } from "react";

// Types for the structure data
interface Pocket {
  id: string;
  name: string;
  center: number[];
  residue_ids: number[];
  druggability_score: number;
  druggability_label: string;
  color: string;
}

interface MutationAnalysis {
  position: number;
  wt_aa: string;
  mut_aa: string;
  found: boolean;
  coordinate?: number[];
  in_binding_pocket: boolean;
  impact_assessment: string;
  impact_score: number;
}

interface MolstarViewerProps {
  pdbContent: string;
  pockets?: Pocket[];
  mutationAnalysis?: MutationAnalysis | null;
  bindingResidues?: number[];
}

/**
 * Mol* (Molstar) 3D Protein Viewer Component
 * 
 * Uses the Mol* library to render protein structures with:
 * - Cartoon representation
 * - Highlighted binding pockets
 * - Mutation position markers
 */
export default function MolstarViewer({
  pdbContent,
  pockets = [],
  mutationAnalysis,
  bindingResidues = [],
}: MolstarViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    
    const initViewer = async () => {
      if (!containerRef.current || !pdbContent) return;
      
      try {
        setIsLoading(true);
        setError(null);
        
        // Dynamically import Mol* to avoid SSR issues
        const { createPluginUI } = await import("molstar/lib/mol-plugin-ui");
        const { renderReact18 } = await import("molstar/lib/mol-plugin-ui/react18");
        const { DefaultPluginUISpec } = await import("molstar/lib/mol-plugin-ui/spec");
        const { PluginCommands } = await import("molstar/lib/mol-plugin/commands");
        const { ColorNames } = await import("molstar/lib/mol-util/color/names");
        const { StructureSelection } = await import("molstar/lib/mol-model/structure");
        const { Script } = await import("molstar/lib/mol-script/script");
        const { MolScriptBuilder: MS } = await import("molstar/lib/mol-script/language/builder");
        
        if (!mounted) return;
        
        // Clear previous viewer
        if (viewerRef.current) {
          viewerRef.current.dispose();
        }
        containerRef.current.innerHTML = '';
        
        // Create the Mol* plugin
        const plugin = await createPluginUI({
          target: containerRef.current,
          render: renderReact18,
          spec: {
            ...DefaultPluginUISpec(),
            layout: {
              initial: {
                isExpanded: false,
                showControls: false,
                regionState: {
                  bottom: "hidden",
                  left: "hidden",
                  right: "hidden",
                  top: "hidden",
                },
              },
            },
          },
        });
        
        viewerRef.current = plugin;
        
        // Load PDB data
        const data = await plugin.builders.data.rawData({
          data: pdbContent,
          label: "Structure",
        });
        
        const trajectory = await plugin.builders.structure.parseTrajectory(data, "pdb");
        const model = await plugin.builders.structure.createModel(trajectory);
        const structure = await plugin.builders.structure.createStructure(model);
        
        // Apply cartoon representation with color by pLDDT (B-factor)
        const components = await plugin.builders.structure.tryCreateComponentStatic(
          structure,
          "polymer"
        );
        
        if (components) {
          await plugin.builders.structure.representation.addRepresentation(
            components,
            {
              type: "cartoon",
              color: "uncertainty", // Colors by pLDDT stored in B-factor
              colorParams: { 
                domain: [50, 90],
                list: { 
                  colors: [
                    ColorNames.orange, // Low confidence
                    ColorNames.yellow,
                    ColorNames.lightgreen,
                    ColorNames.blue    // High confidence
                  ] 
                }
              },
            }
          );
        }
        
        // Highlight binding pockets
        if (pockets.length > 0 && bindingResidues.length > 0) {
          try {
            // Create selection for binding site residues
            const sel = Script.getStructureSelection(Q => 
              Q.struct.generator.atomGroups({
                'residue-test': Q.core.set.has([
                  Q.set(...bindingResidues),
                  Q.ammp('auth_seq_id')
                ])
              }), 
              structure.data!
            );
            
            const loci = StructureSelection.toLociWithSourceUnits(sel);
            
            // Add surface representation for binding sites
            plugin.managers.interactivity.lociHighlights.highlight({ loci });
          } catch (e) {
            console.log("Could not highlight pockets:", e);
          }
        }
        
        // Highlight mutation position
        if (mutationAnalysis?.found && mutationAnalysis.position) {
          try {
            const sel = Script.getStructureSelection(Q => 
              Q.struct.generator.atomGroups({
                'residue-test': Q.core.rel.eq([
                  Q.ammp('auth_seq_id'),
                  mutationAnalysis.position
                ])
              }), 
              structure.data!
            );
            
            const loci = StructureSelection.toLociWithSourceUnits(sel);
            plugin.managers.interactivity.lociHighlights.highlight({ 
              loci
            });
          } catch (e) {
            console.log("Could not highlight mutation:", e);
          }
        }
        
        // Reset camera to show full structure
        await PluginCommands.Camera.Reset(plugin);
        
        setIsLoading(false);
        
      } catch (err) {
        console.error("Mol* initialization error:", err);
        if (mounted) {
          setError("Failed to initialize 3D viewer");
          setIsLoading(false);
        }
      }
    };
    
    initViewer();
    
    return () => {
      mounted = false;
      if (viewerRef.current) {
        try {
          viewerRef.current.dispose();
        } catch (e) {
          // Ignore disposal errors
        }
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdbContent]);

  return (
    <div className="relative w-full h-full min-h-[300px] bg-slate-900 rounded-lg overflow-hidden">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 z-10">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-slate-400 text-sm">Loading 3D Structure...</p>
          </div>
        </div>
      )}
      
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-900 z-10">
          <div className="text-center">
            <p className="text-red-400 text-sm">{error}</p>
            <p className="text-slate-500 text-xs mt-2">PDB data available for download</p>
          </div>
        </div>
      )}
      
      <div 
        ref={containerRef} 
        className="w-full h-full"
        style={{ minHeight: "300px" }}
      />
      
      {/* Legend overlay */}
      {!isLoading && !error && (
        <div className="absolute bottom-4 left-4 bg-slate-800/90 backdrop-blur-sm p-3 rounded-lg text-xs space-y-1">
          <div className="text-slate-300 font-semibold mb-2">pLDDT Confidence</div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-blue-500"></span>
            <span className="text-slate-400">Very High (&gt;90)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-green-400"></span>
            <span className="text-slate-400">Confident (70-90)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-yellow-400"></span>
            <span className="text-slate-400">Low (50-70)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-orange-400"></span>
            <span className="text-slate-400">Disordered (&lt;50)</span>
          </div>
          {mutationAnalysis?.found && (
            <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-600">
              <span className="w-3 h-3 rounded-full bg-red-500"></span>
              <span className="text-slate-400">Mutation Site</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
