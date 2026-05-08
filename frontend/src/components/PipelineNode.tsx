// src/components/PipelineNode.tsx
"use client";

import clsx from "clsx";
import type { NodeState, PipelineNodeId } from "@/lib/types";

const NODE_LABELS: Record<PipelineNodeId, string> = {
  memory_retrieval: "Memory & RAG",
  planner: "Planner",
  executor: "Executor",
  validator: "Validator",
};

const NODE_ICONS: Record<PipelineNodeId, string> = {
  memory_retrieval: "◈",
  planner: "◎",
  executor: "◆",
  validator: "◉",
};

interface Props {
  id: PipelineNodeId;
  state: NodeState;
  isLast?: boolean;
}

export function PipelineNode({ id, state, isLast }: Props) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={clsx(
          "relative flex items-center gap-2.5 px-4 py-2.5 rounded-xl border text-xs font-mono font-medium transition-all duration-300",
          {
            "border-ink-700 text-ink-500 bg-ink-900/40": state === "idle",
            "border-violet-500/70 text-violet-300 bg-violet-600/10 glow-violet":
              state === "active",
            "border-emerald-500/60 text-emerald-400 bg-emerald-500/8":
              state === "done",
            "border-rose-500/60 text-rose-400 bg-rose-500/8": state === "error",
          }
        )}
      >
        {/* Animated pulse for active */}
        {state === "active" && (
          <span className="absolute inset-0 rounded-xl border border-violet-500/40 animate-ping opacity-30" />
        )}

        {/* Dot */}
        <span
          className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0", {
            "bg-ink-600": state === "idle",
            "bg-violet-400 animate-pulse-dot": state === "active",
            "bg-emerald-400": state === "done",
            "bg-rose-400": state === "error",
          })}
        />

        {/* Icon */}
        <span className="text-[10px] opacity-70">{NODE_ICONS[id]}</span>

        {/* Label */}
        <span>{NODE_LABELS[id]}</span>

        {/* Status indicator */}
        {state === "done" && (
          <span className="text-emerald-400 text-[10px]">✓</span>
        )}
        {state === "error" && (
          <span className="text-rose-400 text-[10px]">✗</span>
        )}
      </div>

      {/* Arrow */}
      {!isLast && (
        <span
          className={clsx("text-xs transition-colors duration-300 px-0.5", {
            "text-ink-700": state === "idle",
            "text-violet-500/60": state === "active",
            "text-emerald-500/50": state === "done",
          })}
        >
          →
        </span>
      )}
    </div>
  );
}
