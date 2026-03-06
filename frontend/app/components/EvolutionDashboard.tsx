"use client";

import { useState, useCallback, useRef } from "react";
import {
  GitBranch,
  Loader2,
  TrendingUp,
  Zap,
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Play,
  RefreshCw,
} from "lucide-react";
import type {
  EvolutionSSEEvent,
  EvolutionStepEvent,
  EvolutionFinalEvent,
  MetaGuidanceEvent,
  HypothesisObject,
} from "../types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const ISLAND_COLORS: Record<string, string> = {
  "gene-centric": "emerald",
  "disease-centric": "blue",
  "mechanism-centric": "violet",
};

function statusIcon(status: string) {
  if (status === "pass") return <CheckCircle size={14} className="text-emerald-500" />;
  if (status === "fail") return <XCircle size={14} className="text-red-500" />;
  return <AlertTriangle size={14} className="text-amber-500" />;
}

function BeliefBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 60 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-600 w-10 text-right">{pct}%</span>
    </div>
  );
}

function BeliefSparkline({ trajectory }: { trajectory: number[] }) {
  if (!trajectory.length) return null;
  const h = 24;
  const w = 80;
  const max = Math.max(...trajectory, 0.01);
  const points = trajectory
    .map((v, i) => {
      const x = (i / Math.max(trajectory.length - 1, 1)) * w;
      const y = h - (v / max) * h;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} className="inline-block">
      <polyline points={points} fill="none" stroke="#6366f1" strokeWidth={1.5} />
    </svg>
  );
}

type BanditStats = EvolutionFinalEvent["bandit_stats"];

function BanditArmsChart({ stats }: { stats: BanditStats }) {
  const maxPulls = Math.max(...Object.values(stats.arms).map((a) => a.pull_count), 1);
  return (
    <div className="space-y-1.5">
      {Object.entries(stats.arms).map(([op, arm]) => (
        <div key={op} className="flex items-center gap-2 text-xs">
          <span className="w-28 truncate font-mono text-slate-600">{op}</span>
          <div className="flex-1 h-3 bg-slate-100 rounded overflow-hidden">
            <div
              className="h-full bg-indigo-400 rounded transition-all"
              style={{ width: `${(arm.pull_count / maxPulls) * 100}%` }}
            />
          </div>
          <span className="w-6 text-right text-slate-500">{arm.pull_count}</span>
          <span
            className={`w-14 text-right font-mono ${arm.avg_reward >= 0 ? "text-emerald-600" : "text-red-500"}`}
          >
            {arm.avg_reward >= 0 ? "+" : ""}
            {arm.avg_reward.toFixed(3)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function EvolutionDashboard({ query }: { query: string }) {
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<EvolutionSSEEvent[]>([]);
  const [finalResult, setFinalResult] = useState<EvolutionFinalEvent | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stepEvents = events.filter((e): e is EvolutionStepEvent => e.type === "evolution_step");
  const metaEvents = events.filter((e): e is MetaGuidanceEvent => e.type === "meta_guidance");

  const runEvolution = useCallback(async () => {
    if (!query.trim()) return;
    setRunning(true);
    setEvents([]);
    setFinalResult(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY || "";
      const resp = await fetch(`${API_BASE}/generate-evolved`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { "X-API-Key": apiKey } : {}),
        },
        body: JSON.stringify({ text: query }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        setRunning(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6)) as EvolutionSSEEvent;
            if (event.type === "final_results") {
              setFinalResult(event as EvolutionFinalEvent);
            }
            setEvents((prev) => [...prev, event]);
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error("Evolution stream error:", err);
      }
    } finally {
      setRunning(false);
    }
  }, [query]);

  const stopEvolution = useCallback(() => {
    abortRef.current?.abort();
    setRunning(false);
  }, []);

  // Group step events by island
  const islandSteps: Record<string, EvolutionStepEvent[]> = {};
  for (const ev of stepEvents) {
    (islandSteps[ev.island] ??= []).push(ev);
  }

  const rankedHypotheses: HypothesisObject[] = finalResult?.hypotheses ?? [];

  return (
    <div className="w-full h-full overflow-auto pt-6 px-8 pb-8 space-y-6">
      {/* Header & Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <GitBranch size={20} className="text-indigo-600" />
            Adaptive Hypothesis Evolution
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Multi-island population evolution with Bayesian belief tracking
          </p>
        </div>
        <div className="flex items-center gap-2">
          {running ? (
            <button
              onClick={stopEvolution}
              className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-600 rounded-lg text-sm font-medium hover:bg-red-100 transition-colors"
            >
              <XCircle size={16} />
              Stop
            </button>
          ) : (
            <button
              onClick={runEvolution}
              disabled={!query.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {events.length > 0 ? <RefreshCw size={16} /> : <Play size={16} />}
              {events.length > 0 ? "Re-run" : "Evolve"}
            </button>
          )}
        </div>
      </div>

      {running && (
        <div className="flex items-center gap-3 text-sm text-indigo-600 bg-indigo-50 px-4 py-3 rounded-lg">
          <Loader2 size={16} className="animate-spin" />
          <span>
            Generation {stepEvents.length > 0 ? stepEvents[stepEvents.length - 1].generation + 1 : 1}
            {" "}&middot; {stepEvents.length} hypotheses evaluated
          </span>
        </div>
      )}

      {/* Island Columns */}
      {Object.keys(islandSteps).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(islandSteps).map(([islandName, steps]) => {
            const color = ISLAND_COLORS[islandName] || "slate";
            return (
              <div key={islandName} className="border border-slate-200 rounded-lg overflow-hidden">
                <div className={`px-4 py-2 bg-${color}-50 border-b border-${color}-100`}>
                  <h3 className={`text-sm font-semibold text-${color}-700 capitalize`}>
                    {islandName.replace("-", " ")}
                  </h3>
                  <p className="text-xs text-slate-500">{steps.length} candidates</p>
                </div>
                <div className="divide-y divide-slate-100 max-h-80 overflow-auto">
                  {steps.map((step, i) => (
                    <div key={i} className="px-4 py-3 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-800 truncate">
                          {step.hypothesis.target_gene} &middot; {step.hypothesis.disease}
                        </span>
                        {statusIcon(step.scorecard_summary.overall_status)}
                      </div>
                      <p className="text-xs text-slate-500 truncate">{step.hypothesis.mechanism}</p>
                      <BeliefBar value={step.belief_posterior} />
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span className="font-mono">{step.operator_used}</span>
                        <span className={step.delta >= 0 ? "text-emerald-500" : "text-red-400"}>
                          {step.delta >= 0 ? "+" : ""}{step.delta.toFixed(3)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Final Results */}
      {finalResult && (
        <>
          {/* Ranked hypotheses */}
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center gap-2">
              <Target size={16} className="text-indigo-600" />
              <h3 className="text-sm font-semibold text-slate-800">Ranked Hypotheses</h3>
            </div>
            <div className="divide-y divide-slate-100">
              {rankedHypotheses.map((h, idx) => (
                <div key={h.id} className="px-4 py-3 flex items-start gap-3">
                  <span className="text-lg font-bold text-indigo-600 mt-0.5">#{idx + 1}</span>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">{h.target_gene}</span>
                      <span className="text-slate-400">&middot;</span>
                      <span className="text-slate-700">{h.disease}</span>
                      {h.mutation && (
                        <>
                          <span className="text-slate-400">&middot;</span>
                          <span className="text-xs font-mono text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">
                            {h.mutation}
                          </span>
                        </>
                      )}
                    </div>
                    <p className="text-sm text-slate-600">{h.mechanism}</p>
                    <p className="text-xs text-slate-400">{h.rationale}</p>
                    <div className="flex items-center gap-4 mt-1">
                      <BeliefBar value={h.belief_posterior} />
                      <BeliefSparkline trajectory={h.belief_trajectory} />
                      {h.island && (
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">
                          {h.island}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Bandit Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-slate-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-2">
                <Zap size={14} className="text-amber-500" />
                Mutation Operator Performance
              </h3>
              <BanditArmsChart stats={finalResult.bandit_stats} />
              <p className="text-[10px] text-slate-400 mt-2">
                {finalResult.bandit_stats.total_pulls} total pulls
              </p>
            </div>

            <div className="border border-slate-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-2">
                <TrendingUp size={14} className="text-emerald-500" />
                Island Summary
              </h3>
              <div className="space-y-2">
                {finalResult.island_summary.map((isl) => (
                  <div key={isl.name} className="flex items-center justify-between text-sm">
                    <span className="text-slate-600 capitalize">{isl.name.replace("-", " ")}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-400">{isl.population_size} hyp.</span>
                      <span className="font-mono text-slate-700">{(isl.best_score * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Meta-Guidance Log */}
          {metaEvents.length > 0 && (
            <div className="border border-amber-200 rounded-lg p-4 bg-amber-50/50">
              <h3 className="text-sm font-semibold text-amber-800 mb-2 flex items-center gap-2">
                <AlertTriangle size={14} />
                Meta-Guidance Events
              </h3>
              <div className="space-y-2">
                {metaEvents.map((ev, i) => (
                  <div key={i} className="text-sm">
                    <span className="font-medium text-amber-700">{ev.island}:</span>{" "}
                    <span className="text-slate-700">{ev.tactic.tactic}</span>
                    <p className="text-xs text-slate-500 mt-0.5">{ev.tactic.reasoning}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-slate-400 text-right">
            Completed in {(finalResult.elapsed_ms / 1000).toFixed(1)}s
          </p>
        </>
      )}

      {!running && events.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <GitBranch size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-sm">Click &ldquo;Evolve&rdquo; to start multi-island hypothesis evolution</p>
        </div>
      )}
    </div>
  );
}
