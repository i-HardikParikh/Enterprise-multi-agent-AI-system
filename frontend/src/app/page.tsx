// src/app/page.tsx
"use client";

import { useState } from "react";
import { Upload, Square, RotateCcw, Zap, History, Settings } from "lucide-react";
import Link from "next/link";
import clsx from "clsx";
import { useAgentStream } from "@/hooks/useAgentStream";
import { PipelineNode } from "@/components/PipelineNode";
import { LogPanel } from "@/components/LogPanel";
import { OutputPanel } from "@/components/OutputPanel";
import { UploadModal } from "@/components/UploadModal";
import { ProviderBar } from "@/components/ProviderBar";
import type { OutputFormat, PipelineNodeId } from "@/lib/types";

const PIPELINE_NODES: PipelineNodeId[] = [
  "memory_retrieval",
  "planner",
  "executor",
  "validator",
];

const EXAMPLE_PROMPTS = [
  "Analyse Q1 2024 sales data and create an executive summary with trends and recommendations",
  "Research the latest trends in AI/ML and generate a structured industry briefing",
  "Query the employee database and create a department headcount and salary analysis",
  "Summarise all uploaded documents and produce a consolidated knowledge report",
];

export default function HomePage() {
  const [input, setInput] = useState("");
  const [format, setFormat] = useState<OutputFormat>("markdown");
  const [showUpload, setShowUpload] = useState(false);
  const { state, run, stop, reset } = useAgentStream();

  const handleRun = () => {
    if (!input.trim() || state.running) return;
    run({ user_input: input.trim(), output_format: format, session_id: crypto.randomUUID() });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleRun();
  };

  const hasOutput = !!state.finalOutput;
  const showRight = state.running || hasOutput;

  return (
    <div className="min-h-screen bg-grid flex flex-col">
      {/* Header */}
      <header className="border-b border-ink-800/60 bg-ink-950/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-screen-xl mx-auto px-5 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="w-7 h-7 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
              <Zap size={13} className="text-violet-400" />
            </div>
            <div className="hidden sm:block">
              <h1 className="font-display font-semibold text-sm text-ink-100 leading-none">Enterprise Agent</h1>
              <p className="text-ink-600 text-[10px] font-mono leading-none mt-0.5">Multi-Agent AI System</p>
            </div>
          </div>

          <div className="hidden md:block flex-1 text-center">
            <ProviderBar />
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <Link href="/history" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-ink-800 text-ink-500 text-xs font-mono hover:border-ink-600 hover:text-ink-300 transition-all">
              <History size={12} /><span className="hidden sm:inline">History</span>
            </Link>
            <Link href="/settings" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-ink-800 text-ink-500 text-xs font-mono hover:border-ink-600 hover:text-ink-300 transition-all">
              <Settings size={12} /><span className="hidden sm:inline">Config</span>
            </Link>
            <button onClick={() => setShowUpload(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-ink-700 text-ink-400 text-xs font-mono hover:border-violet-500/50 hover:text-violet-300 transition-all">
              <Upload size={12} /><span className="hidden sm:inline">Upload Docs</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-screen-xl mx-auto w-full px-5 py-6">
        <div className={clsx("grid gap-5 transition-all duration-500", showRight ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1 max-w-2xl mx-auto")}>

          {/* LEFT */}
          <div className="flex flex-col gap-4">
            {/* Input */}
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <label className="text-ink-500 text-[10px] font-mono uppercase tracking-widest">Task Input</label>
                <span className="text-ink-700 text-[10px] font-mono">⌘↵ to run</span>
              </div>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={state.running}
                placeholder={"Describe your task in natural language…\ne.g. Analyse Q1 sales data and generate a report with insights"}
                rows={4}
                className="w-full bg-ink-950/60 border border-ink-800 rounded-xl text-ink-200 text-sm font-sans placeholder:text-ink-700 px-4 py-3 resize-none focus:outline-none focus:border-violet-500/50 focus:bg-ink-950 transition-all disabled:opacity-50 leading-relaxed"
              />
              {!input && !state.running && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {EXAMPLE_PROMPTS.slice(0, 2).map((p) => (
                    <button key={p} onClick={() => setInput(p)} className="text-[11px] text-ink-500 hover:text-ink-300 bg-ink-800/40 hover:bg-ink-800 border border-ink-700/60 rounded-lg px-2.5 py-1 font-mono transition-all text-left">
                      ↗ {p.slice(0, 52)}…
                    </button>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-3 mt-4">
                <select value={format} onChange={(e) => setFormat(e.target.value as OutputFormat)} disabled={state.running}
                  className="bg-ink-800/60 border border-ink-700 text-ink-300 text-xs font-mono rounded-lg px-3 py-2 focus:outline-none disabled:opacity-50">
                  <option value="markdown">Markdown</option>
                  <option value="json">JSON</option>
                </select>
                <div className="flex items-center gap-2 ml-auto">
                  {(state.running || hasOutput) && (
                    <button onClick={reset} className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-ink-700 text-ink-500 text-xs font-mono hover:border-ink-500 hover:text-ink-300 transition-all">
                      <RotateCcw size={12} />Reset
                    </button>
                  )}
                  {state.running ? (
                    <button onClick={stop} className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600/15 border border-rose-500/40 text-rose-400 text-xs font-mono hover:bg-rose-600/25 transition-all">
                      <Square size={11} fill="currentColor" />Stop
                    </button>
                  ) : (
                    <button onClick={handleRun} disabled={!input.trim()} className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-mono font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-all">
                      <Zap size={12} />Run Agent
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Pipeline */}
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl p-4">
              <p className="text-ink-600 text-[10px] font-mono uppercase tracking-widest mb-3">Pipeline</p>
              <div className="flex flex-wrap items-center gap-1">
                {PIPELINE_NODES.map((id, i) => (
                  <PipelineNode key={id} id={id} state={state.pipeline[id]} isLast={i === PIPELINE_NODES.length - 1} />
                ))}
              </div>
              {state.elapsedSeconds !== null && (
                <div className="mt-3 pt-3 border-t border-ink-800/60 flex items-center justify-between">
                  <span className="text-ink-700 text-[11px] font-mono">elapsed</span>
                  <span className={clsx("text-xs font-mono tabular-nums font-medium", state.running ? "text-amber-400 animate-pulse" : "text-emerald-400")}>
                    {state.elapsedSeconds}s
                  </span>
                </div>
              )}
            </div>

            {/* Log */}
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl overflow-hidden flex flex-col" style={{ minHeight: "220px", maxHeight: "320px" }}>
              <div className="flex items-center justify-between px-4 py-3 border-b border-ink-800 flex-shrink-0">
                <p className="text-ink-600 text-[10px] font-mono uppercase tracking-widest">Execution Log</p>
                <span className="text-ink-700 text-[10px] font-mono">{state.logs.length} entries</span>
              </div>
              <div className="flex-1 min-h-0">
                <LogPanel logs={state.logs} />
              </div>
            </div>
          </div>

          {/* RIGHT */}
          {showRight && (
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl overflow-hidden flex flex-col animate-fade-in" style={{ minHeight: "560px" }}>
              {state.finalOutput ? (
                <OutputPanel
                  output={state.finalOutput}
                  validationScore={state.validationScore}
                  stepCount={state.stepHistory.length}
                  elapsedSeconds={state.elapsedSeconds}
                  outputFormat={format}
                  jobId={state.jobId}
                />
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center gap-5 px-8 text-center">
                  <div className="relative w-16 h-16">
                    <div className="absolute inset-0 border border-violet-500/15 rounded-2xl" />
                    <div className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-violet-500/50 to-transparent animate-scan" />
                    <Zap size={18} className="absolute inset-0 m-auto text-violet-400/30" />
                  </div>
                  <div>
                    <p className="text-ink-400 text-sm font-mono">{state.running ? "Agents working…" : "Output will appear here"}</p>
                    <p className="text-ink-700 text-xs font-mono mt-1.5 leading-relaxed max-w-xs">
                      {state.running ? "Processing your request through the agent pipeline" : "Run the agent to see the generated output"}
                    </p>
                  </div>
                  {state.running && (
                    <div className="flex gap-1.5">
                      {[0, 1, 2].map((i) => (
                        <span key={i} className="w-1.5 h-1.5 rounded-full bg-violet-500/60 animate-pulse" style={{ animationDelay: `${i * 0.2}s` }} />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </div>
  );
}
