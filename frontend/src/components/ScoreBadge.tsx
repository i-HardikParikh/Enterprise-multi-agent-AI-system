// src/components/ScoreBadge.tsx
"use client";

import clsx from "clsx";

interface Props {
  score: number | null;
  label?: string;
  size?: "sm" | "md" | "lg";
}

export function ScoreBadge({ score, label = "Quality", size = "md" }: Props) {
  if (score === null) return null;

  const pct = Math.round(score * 100);
  const tier =
    pct >= 85 ? "excellent" : pct >= 70 ? "good" : pct >= 50 ? "ok" : "poor";

  const tierStyles = {
    excellent: "bg-emerald-500/15 border-emerald-500/40 text-emerald-400",
    good: "bg-violet-500/15 border-violet-500/40 text-violet-300",
    ok: "bg-amber-500/15 border-amber-500/40 text-amber-400",
    poor: "bg-rose-500/15 border-rose-500/40 text-rose-400",
  };

  const sizeStyles = {
    sm: "text-xs px-2.5 py-1",
    md: "text-sm px-3 py-1.5",
    lg: "text-base px-4 py-2",
  };

  return (
    <div
      className={clsx(
        "inline-flex items-center gap-2 rounded-lg border font-mono font-medium",
        tierStyles[tier],
        sizeStyles[size]
      )}
    >
      {/* Circular progress indicator */}
      <svg width="16" height="16" viewBox="0 0 16 16" className="flex-shrink-0">
        <circle
          cx="8" cy="8" r="6"
          fill="none"
          stroke="currentColor"
          strokeOpacity="0.2"
          strokeWidth="2"
        />
        <circle
          cx="8" cy="8" r="6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeDasharray={`${(pct / 100) * 37.7} 37.7`}
          strokeLinecap="round"
          transform="rotate(-90 8 8)"
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
      </svg>
      <span>
        {label}: {pct}%
      </span>
    </div>
  );
}
