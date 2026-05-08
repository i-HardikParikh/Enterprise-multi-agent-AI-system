// src/components/MetricCard.tsx
"use client";

import clsx from "clsx";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "violet" | "emerald" | "amber" | "rose" | "default";
}

export function MetricCard({ label, value, sub, accent = "default" }: Props) {
  const accentColor = {
    violet: "text-violet-400",
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    rose: "text-rose-400",
    default: "text-ink-100",
  }[accent];

  return (
    <div className="bg-ink-900/60 border border-ink-800 rounded-xl p-4">
      <p className="text-ink-500 text-[10px] font-mono uppercase tracking-widest mb-1.5">
        {label}
      </p>
      <p className={clsx("text-xl font-display font-semibold tabular-nums", accentColor)}>
        {value}
      </p>
      {sub && (
        <p className="text-ink-600 text-[11px] font-mono mt-0.5">{sub}</p>
      )}
    </div>
  );
}
