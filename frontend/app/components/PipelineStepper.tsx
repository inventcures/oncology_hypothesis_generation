"use client";

import React, { useEffect, useState } from "react";
import { Dna, Network, FileText, Sparkles, Lightbulb, CheckCircle, XCircle, Loader2 } from "lucide-react";

export type StepStatus = "pending" | "active" | "done" | "error";

export interface PipelineStep {
  id: string;
  label: string;
  icon: string;
  status: StepStatus;
  startedAt?: number;
  completedAt?: number;
  detail?: string;
  errorMsg?: string;
}

interface PipelineStepperProps {
  steps: PipelineStep[];
  progress: number;
  startTime: number | null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ICON_MAP: Record<string, React.ElementType> = {
  Dna,
  Network,
  FileText,
  Sparkles,
  Lightbulb,
};

function StepIcon({ iconName, status }: { iconName: string; status: StepStatus }) {
  const Icon = ICON_MAP[iconName] || Sparkles;

  if (status === "done") {
    return <CheckCircle size={18} className="text-emerald-500" />;
  }
  if (status === "error") {
    return <XCircle size={18} className="text-red-500" />;
  }
  if (status === "active") {
    return <Loader2 size={18} className="text-indigo-500 animate-spin" />;
  }
  return <Icon size={18} className="text-slate-300" />;
}

function ElapsedTimer({ startTime }: { startTime: number | null }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) return;
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  if (!startTime) return null;
  return <span className="text-xs text-slate-400 font-mono">{elapsed}s</span>;
}

function formatStepTime(step: PipelineStep): string | null {
  if (step.status !== "done" || !step.startedAt || !step.completedAt) return null;
  const ms = step.completedAt - step.startedAt;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function PipelineStepper({ steps, progress, startTime }: PipelineStepperProps) {
  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl p-8">
        {/* Title */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center">
            <Sparkles size={20} className="text-indigo-500" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-800">Analyzing Your Query</h3>
            <p className="text-xs text-slate-400">Processing through the Onco-TTT pipeline</p>
          </div>
        </div>

        {/* Steps */}
        <div className="space-y-1 mb-6">
          {steps.map((step, i) => {
            const isLast = i === steps.length - 1;
            const time = formatStepTime(step);

            return (
              <div key={step.id} className="relative">
                {/* Connecting line */}
                {!isLast && (
                  <div
                    className={`absolute left-[17px] top-[32px] w-px h-[20px] ${
                      step.status === "done" ? "bg-emerald-200" : "bg-slate-100"
                    }`}
                  />
                )}

                <div
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                    step.status === "active"
                      ? "bg-indigo-50 border border-indigo-100"
                      : step.status === "error"
                      ? "bg-red-50 border border-red-100"
                      : "border border-transparent"
                  }`}
                >
                  {/* Icon */}
                  <div className="shrink-0 w-[36px] flex justify-center">
                    <StepIcon iconName={step.icon} status={step.status} />
                  </div>

                  {/* Label */}
                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm font-medium ${
                        step.status === "active"
                          ? "text-indigo-700"
                          : step.status === "done"
                          ? "text-slate-500"
                          : step.status === "error"
                          ? "text-red-600"
                          : "text-slate-400"
                      }`}
                    >
                      {step.label}
                    </p>
                    {step.detail && step.status === "done" && (
                      <p className="text-xs text-slate-400 truncate">{step.detail}</p>
                    )}
                    {step.errorMsg && step.status === "error" && (
                      <p className="text-xs text-red-400 truncate">{step.errorMsg}</p>
                    )}
                  </div>

                  {/* Timing */}
                  <div className="shrink-0 text-right">
                    {time && <span className="text-xs text-slate-400 font-mono">{time}</span>}
                    {step.status === "active" && (
                      <span className="text-xs text-indigo-400 font-mono animate-pulse">...</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-500 transition-all duration-300 ease-out"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 font-mono">{Math.round(progress)}%</span>
            <ElapsedTimer startTime={startTime} />
          </div>
        </div>
      </div>
    </div>
  );
}

export const INITIAL_PIPELINE_STEPS: PipelineStep[] = [
  { id: "ner", label: "Entity Extraction", icon: "Dna", status: "pending" },
  { id: "kg", label: "Knowledge Graph", icon: "Network", status: "pending" },
  { id: "lit", label: "Literature & Atlas", icon: "FileText", status: "pending" },
  { id: "rank", label: "Node Ranking", icon: "Sparkles", status: "pending" },
  { id: "hypothesis", label: "Hypothesis Generation", icon: "Lightbulb", status: "pending" },
];
