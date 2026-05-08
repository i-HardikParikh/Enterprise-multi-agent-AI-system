// src/components/ProviderBar.tsx
"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { fetchHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

type ConnStatus = "connecting" | "online" | "offline";

export function ProviderBar() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<ConnStatus>("connecting");

  useEffect(() => {
    const check = async () => {
      try {
        const h = await fetchHealth();
        setHealth(h);
        setStatus("online");
      } catch {
        setStatus("offline");
      }
    };

    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, []);

  const providerColors: Record<string, string> = {
    groq: "text-violet-400",
    gemini: "text-blue-400",
    ollama: "text-emerald-400",
  };

  return (
    <div className="flex items-center gap-4 text-[11px] font-mono">
      {/* Connection dot */}
      <div className="flex items-center gap-1.5">
        <span
          className={clsx("w-1.5 h-1.5 rounded-full", {
            "bg-amber-400 animate-pulse": status === "connecting",
            "bg-emerald-400": status === "online",
            "bg-rose-500": status === "offline",
          })}
        />
        <span
          className={clsx({
            "text-amber-400": status === "connecting",
            "text-emerald-400": status === "online",
            "text-rose-400": status === "offline",
          })}
        >
          {status === "connecting"
            ? "connecting…"
            : status === "online"
            ? "API online"
            : "API offline"}
        </span>
      </div>

      {/* Provider info */}
      {health && status === "online" && (
        <>
          <span className="text-ink-700">|</span>
          <span className={clsx(providerColors[health.llm_provider] ?? "text-ink-400")}>
            {health.llm_provider.toUpperCase()}
          </span>
          <span className="text-ink-600">{health.llm_model}</span>
          <span className="text-ink-700">|</span>
          <span className="text-ink-500">v{health.version}</span>
        </>
      )}

      {status === "offline" && (
        <>
          <span className="text-ink-700">|</span>
          <span className="text-ink-600">
            Start backend: uvicorn api.main:app --port 8000
          </span>
        </>
      )}
    </div>
  );
}
