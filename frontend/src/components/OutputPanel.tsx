// src/components/OutputPanel.tsx
"use client";

import { useState } from "react";
import { Copy, Check, Download } from "lucide-react";
import clsx from "clsx";
import { ScoreBadge } from "./ScoreBadge";
import { MetricCard } from "./MetricCard";
import { EvalPanel } from "./EvalPanel";

interface Props {
  output: string;
  validationScore: number | null;
  stepCount: number;
  elapsedSeconds: number | null;
  outputFormat: string;
  jobId: string | null;
}

function renderMarkdown(text: string): string {
  return text
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/```(\w+)?\n([\s\S]+?)```/g, "<pre><code>$2</code></pre>")
    .replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>")
    .replace(/^\| (.+) \|$/gm, (_, row) => {
      const cells = row.split(" | ").map((c: string) => c.trim());
      return "<tr>" + cells.map((c: string) => `<td>${c}</td>`).join("") + "</tr>";
    })
    .replace(/^---$/gm, "<hr>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>(\n|$))+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\n\n/g, "</p><p>")
    .replace(/^(?!<[hupboli])(.+)$/gm, (m) => (m.trim() ? `<p>${m}</p>` : ""));
}

export function OutputPanel({
  output,
  validationScore,
  stepCount,
  elapsedSeconds,
  outputFormat,
  jobId,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState<"output" | "eval">("output");

  const handleCopy = async () => {
    await navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const ext = outputFormat === "json" ? "json" : "md";
    const blob = new Blob([output], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-output.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-800">
        <div className="flex items-center gap-3">
          <h2 className="font-display font-semibold text-sm text-ink-200">
            Output
          </h2>
          <ScoreBadge score={validationScore} size="sm" />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            className="p-1.5 text-ink-500 hover:text-ink-300 hover:bg-ink-800 rounded-lg transition-all"
            title="Download"
          >
            <Download size={14} />
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-ink-500 hover:text-ink-300 hover:bg-ink-800 rounded-lg transition-all text-xs font-mono"
          >
            {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-2 px-5 py-3 border-b border-ink-800">
        <MetricCard
          label="Steps"
          value={stepCount}
          accent="violet"
        />
        <MetricCard
          label="Time"
          value={elapsedSeconds ? `${elapsedSeconds}s` : "—"}
          accent="emerald"
        />
        <MetricCard
          label="Format"
          value={outputFormat}
          accent="default"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 px-5 py-2 border-b border-ink-800">
        {(["output", "eval"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-mono transition-all",
              tab === t
                ? "bg-ink-800 text-ink-200"
                : "text-ink-500 hover:text-ink-300"
            )}
          >
            {t === "output" ? "◆ Result" : "◈ Evaluate"}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {tab === "output" ? (
          outputFormat === "json" ? (
            <pre className="text-xs font-mono text-emerald-300 leading-relaxed whitespace-pre-wrap break-all">
              {(() => {
                try {
                  return JSON.stringify(JSON.parse(output), null, 2);
                } catch {
                  return output;
                }
              })()}
            </pre>
          ) : (
            <div
              className="output-content text-sm text-ink-300"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(output) }}
            />
          )
        ) : (
          <div className="py-1">
            {jobId ? (
              <EvalPanel jobId={jobId} />
            ) : (
              <p className="text-ink-600 text-xs font-mono text-center py-4">
                No job ID available for evaluation.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
