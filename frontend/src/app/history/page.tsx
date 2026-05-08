// src/app/history/page.tsx
"use client";

import { useState } from "react";
import { ArrowLeft, Search, RefreshCw, CheckCircle, XCircle, Clock, AlertTriangle } from "lucide-react";
import Link from "next/link";
import clsx from "clsx";
import { fetchJobStatus } from "@/lib/api";
import type { RunResponse, TaskStatus } from "@/lib/types";
import { ScoreBadge } from "@/components/ScoreBadge";

const STATUS_ICON: Record<TaskStatus, React.ReactNode> = {
  completed:      <CheckCircle size={14} className="text-emerald-400" />,
  failed:         <XCircle size={14} className="text-rose-400" />,
  in_progress:    <Clock size={14} className="text-amber-400" />,
  pending:        <Clock size={14} className="text-ink-500" />,
  needs_retry:    <RefreshCw size={14} className="text-amber-400" />,
  awaiting_human: <AlertTriangle size={14} className="text-amber-400" />,
};

const STATUS_LABEL: Record<TaskStatus, string> = {
  completed:      "Completed",
  failed:         "Failed",
  in_progress:    "In Progress",
  pending:        "Pending",
  needs_retry:    "Retrying",
  awaiting_human: "Awaiting Review",
};

export default function HistoryPage() {
  const [jobId, setJobId] = useState("");
  const [result, setResult] = useState<RunResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const lookup = async () => {
    if (!jobId.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetchJobStatus(jobId.trim());
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-grid">
      {/* Header */}
      <header className="border-b border-ink-800/60 bg-ink-950/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-screen-xl mx-auto px-5 py-3 flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-ink-500 hover:text-ink-200 text-xs font-mono transition-colors"
          >
            <ArrowLeft size={13} />
            Back
          </Link>
          <span className="text-ink-700">|</span>
          <h1 className="font-display font-semibold text-sm text-ink-200">
            Job History
          </h1>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-5 py-8">
        <div className="max-w-2xl mx-auto space-y-6">

          {/* Search bar */}
          <div className="bg-ink-900/60 border border-ink-800 rounded-2xl p-5">
            <p className="text-ink-500 text-[10px] font-mono uppercase tracking-widest mb-3">
              Lookup Job by ID
            </p>
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-600" />
                <input
                  value={jobId}
                  onChange={(e) => setJobId(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && lookup()}
                  placeholder="Enter job ID…"
                  className="w-full bg-ink-950/60 border border-ink-800 rounded-xl text-ink-200 text-sm font-mono placeholder:text-ink-700 pl-9 pr-4 py-2.5 focus:outline-none focus:border-violet-500/50 transition-all"
                />
              </div>
              <button
                onClick={lookup}
                disabled={!jobId.trim() || loading}
                className="px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-mono font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                {loading ? "Looking up…" : "Lookup"}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl px-4 py-3 flex items-center gap-2">
              <XCircle size={14} className="text-rose-400 flex-shrink-0" />
              <p className="text-rose-400 text-sm font-mono">{error}</p>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl overflow-hidden animate-fade-in">
              {/* Job header */}
              <div className="px-5 py-4 border-b border-ink-800">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {STATUS_ICON[result.status as TaskStatus]}
                    <span className="text-ink-200 text-sm font-medium">
                      {STATUS_LABEL[result.status as TaskStatus] ?? result.status}
                    </span>
                  </div>
                  <ScoreBadge score={result.validation_score ?? null} size="sm" />
                </div>
                <p className="text-ink-600 text-[11px] font-mono mt-2">
                  Job ID: {result.job_id}
                </p>
              </div>

              {/* Step history */}
              {result.step_history.length > 0 && (
                <div className="px-5 py-4 border-b border-ink-800">
                  <p className="text-ink-500 text-[10px] font-mono uppercase tracking-widest mb-3">
                    Steps ({result.step_history.length})
                  </p>
                  <div className="space-y-1.5">
                    {result.step_history.map((step, i) => (
                      <div
                        key={i}
                        className={clsx("text-xs font-mono flex items-start gap-2", {
                          "text-emerald-400": step.startsWith("✅"),
                          "text-amber-400": step.startsWith("⚠️"),
                          "text-rose-400": step.startsWith("❌"),
                          "text-ink-400": !step.startsWith("✅") && !step.startsWith("⚠️") && !step.startsWith("❌"),
                        })}
                      >
                        <span className="text-ink-700 flex-shrink-0 tabular-nums w-5 text-right">
                          {i + 1}.
                        </span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error log */}
              {result.error_log.length > 0 && (
                <div className="px-5 py-4 border-b border-ink-800">
                  <p className="text-rose-500 text-[10px] font-mono uppercase tracking-widest mb-3">
                    Errors ({result.error_log.length})
                  </p>
                  <div className="space-y-1">
                    {result.error_log.map((err, i) => (
                      <p key={i} className="text-rose-400 text-xs font-mono">
                        {err}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {/* Output preview */}
              {result.final_output && (
                <div className="px-5 py-4">
                  <p className="text-ink-500 text-[10px] font-mono uppercase tracking-widest mb-3">
                    Output Preview
                  </p>
                  <pre className="text-xs font-mono text-ink-400 whitespace-pre-wrap line-clamp-6 bg-ink-950/60 rounded-xl p-3 border border-ink-800">
                    {result.final_output.slice(0, 800)}
                    {result.final_output.length > 800 ? "\n…" : ""}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!result && !error && !loading && (
            <div className="text-center py-16">
              <p className="text-ink-700 text-sm font-mono">
                Enter a job ID to look up its status and output
              </p>
              <p className="text-ink-800 text-xs font-mono mt-2">
                Job IDs are shown in the execution log after running an agent
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
