// src/components/LogPanel.tsx
"use client";

import { useEffect, useRef } from "react";
import clsx from "clsx";
import type { LogEntry } from "@/lib/types";

interface Props {
  logs: LogEntry[];
}

const LEVEL_STYLES: Record<LogEntry["level"], string> = {
  info: "text-ink-400",
  ok: "text-emerald-400",
  warn: "text-amber-400",
  error: "text-rose-400",
};

const LEVEL_PREFIX: Record<LogEntry["level"], string> = {
  info: "·",
  ok: "✓",
  warn: "◎",
  error: "✗",
};

export function LogPanel({ logs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="h-full overflow-y-auto px-4 py-3 space-y-0.5">
      {logs.length === 0 ? (
        <div className="h-full flex items-center justify-center">
          <p className="text-ink-700 text-xs font-mono">
            Waiting for agent to start…
          </p>
        </div>
      ) : (
        logs.map((entry) => (
          <div
            key={entry.id}
            className={clsx(
              "flex gap-3 text-xs font-mono py-0.5 animate-slide-up",
              LEVEL_STYLES[entry.level]
            )}
          >
            <span className="text-ink-600 flex-shrink-0 w-14 tabular-nums">
              {entry.timestamp}
            </span>
            <span className="flex-shrink-0 opacity-60">
              {LEVEL_PREFIX[entry.level]}
            </span>
            <span className="leading-relaxed break-all">{entry.message}</span>
          </div>
        ))
      )}
      <div ref={bottomRef} />
    </div>
  );
}
