// src/lib/api.ts
import type {
  RunRequest,
  RunResponse,
  HealthResponse,
  EvalResult,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Health ─────────────────────────────────────────────────────────────────

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("API unavailable");
  return res.json();
}

// ── Run (sync) ─────────────────────────────────────────────────────────────

export async function runAgent(req: RunRequest): Promise<RunResponse> {
  const res = await fetch(`${BASE}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Run failed");
  }
  return res.json();
}

// ── Run Stream (SSE) ───────────────────────────────────────────────────────

export function streamAgent(
  req: RunRequest,
  onEvent: (eventType: string, data: unknown) => void,
  onError: (err: Error) => void
): () => void {
  let active = true;

  (async () => {
    try {
      const res = await fetch(`${BASE}/run/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Stream failed");
      }

      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let currentEvent = "";

      while (active) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const raw = line.slice(5).trim();
            try {
              const parsed = JSON.parse(raw);
              onEvent(currentEvent || "message", parsed);
            } catch {
              // ignore malformed
            }
            currentEvent = "";
          }
        }
      }
    } catch (e) {
      if (active) onError(e as Error);
    }
  })();

  return () => { active = false; };
}

// ── Status ─────────────────────────────────────────────────────────────────

export async function fetchJobStatus(jobId: string): Promise<RunResponse> {
  const res = await fetch(`${BASE}/status/${jobId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Job not found");
  return res.json();
}

// ── Upload ─────────────────────────────────────────────────────────────────

export async function uploadDocument(file: File): Promise<{ message: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

// ── Human Review ───────────────────────────────────────────────────────────

export async function submitHumanReview(
  jobId: string,
  feedback: string,
  approved: boolean
): Promise<{ message: string; status: string }> {
  const res = await fetch(`${BASE}/human-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, feedback, approved }),
  });
  if (!res.ok) throw new Error("Human review failed");
  return res.json();
}

// ── Evaluate ───────────────────────────────────────────────────────────────

export async function evaluateJob(jobId: string): Promise<EvalResult> {
  const res = await fetch(`${BASE}/evaluate/${jobId}`, { method: "POST" });
  if (!res.ok) throw new Error("Evaluation failed");
  return res.json();
}
