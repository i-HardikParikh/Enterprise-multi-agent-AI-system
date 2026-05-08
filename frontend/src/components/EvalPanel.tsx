// src/components/EvalPanel.tsx
"use client";

import { useState } from "react";
import clsx from "clsx";
import { evaluateJob } from "@/lib/api";
import type { EvalResult } from "@/lib/types";
import { ScoreBadge } from "./ScoreBadge";

interface Props {
  jobId: string;
}

type LoadState = "idle" | "loading" | "done" | "error";

const DIM_LABELS: Record<string, string> = {
  faithfulness: "Faithfulness",
  answer_relevance: "Answer Relevance",
  completeness: "Completeness",
  clarity: "Clarity",
};

const DIM_WEIGHTS: Record<string, number> = {
  faithfulness: 35,
  answer_relevance: 35,
  completeness: 20,
  clarity: 10,
};

export function EvalPanel({ jobId }: Props) {
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [result, setResult] = useState<EvalResult | null>(null);
  const [error, setError] = useState("");

  const runEval = async () => {
    setLoadState("loading");
    try {
      const res = await evaluateJob(jobId);
      setResult(res);
      setLoadState("done");
    } catch (e) {
      setError((e as Error).message);
      setLoadState("error");
    }
  };

  if (loadState === "idle") {
    return (
      <button
        onClick={runEval}
        className="w-full py-2.5 rounded-xl border border-ink-700 text-ink-400 text-xs font-mono hover:border-violet-500/50 hover:text-violet-300 transition-all"
      >
        ◈ Run Detailed Evaluation
      </button>
    );
  }

  if (loadState === "loading") {
    return (
      <div className="w-full py-2.5 rounded-xl border border-ink-700 text-ink-500 text-xs font-mono text-center">
        <span className="animate-pulse">Evaluating output…</span>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <p className="text-rose-400 text-xs font-mono text-center py-2">
        Evaluation failed: {error}
      </p>
    );
  }

  if (!result) return null;

  const dims = ["faithfulness", "answer_relevance", "completeness", "clarity"];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono text-ink-400 uppercase tracking-widest">
          LLM-as-Judge Evaluation
        </h3>
        <ScoreBadge score={result.overall_score} label="Overall" size="sm" />
      </div>

      {/* Dimension bars */}
      <div className="space-y-3">
        {dims.map((dim) => {
          const d = result[dim as keyof EvalResult] as {
            score: number;
            reasoning: string;
          };
          if (!d || typeof d.score !== "number") return null;
          const pct = Math.round(d.score * 100);
          const color =
            pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-violet-500" : "bg-amber-500";

          return (
            <div key={dim}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-ink-300 text-xs font-mono">
                  {DIM_LABELS[dim]}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-ink-500 text-[10px] font-mono">
                    weight {DIM_WEIGHTS[dim]}%
                  </span>
                  <span
                    className={clsx(
                      "text-xs font-mono font-medium tabular-nums",
                      pct >= 80 ? "text-emerald-400" : pct >= 60 ? "text-violet-300" : "text-amber-400"
                    )}
                  >
                    {pct}%
                  </span>
                </div>
              </div>
              {/* Bar */}
              <div className="h-1.5 bg-ink-800 rounded-full overflow-hidden">
                <div
                  className={clsx("h-full rounded-full transition-all duration-700", color)}
                  style={{ width: `${pct}%` }}
                />
              </div>
              {/* Reasoning */}
              <p className="text-ink-600 text-[11px] font-mono mt-1 line-clamp-2">
                {d.reasoning}
              </p>
            </div>
          );
        })}
      </div>

      {/* Summary */}
      {result.summary && (
        <div className="bg-ink-950/60 border border-ink-800 rounded-lg px-3 py-2.5">
          <p className="text-ink-400 text-xs leading-relaxed">{result.summary}</p>
        </div>
      )}

      <p className="text-ink-700 text-[10px] font-mono text-right">
        eval latency: {result.latency_ms}ms
      </p>
    </div>
  );
}
