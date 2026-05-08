// src/hooks/useAgentStream.ts
"use client";

import { useState, useCallback, useRef } from "react";
import { streamAgent } from "@/lib/api";
import type {
  LogEntry,
  NodeState,
  PipelineNodeId,
  RunRequest,
  SSEDoneEvent,
  SSEStepEvent,
  TaskStatus,
} from "@/lib/types";

type PipelineState = Record<PipelineNodeId, NodeState>;

const INITIAL_PIPELINE: PipelineState = {
  memory_retrieval: "idle",
  planner: "idle",
  executor: "idle",
  validator: "idle",
};

export interface AgentStreamState {
  running: boolean;
  jobId: string | null;
  status: TaskStatus | null;
  pipeline: PipelineState;
  logs: LogEntry[];
  finalOutput: string | null;
  validationScore: number | null;
  stepHistory: string[];
  elapsedSeconds: number | null;
  error: string | null;
}

let logCounter = 0;
function makeLog(message: string, level: LogEntry["level"]): LogEntry {
  const now = new Date();
  const ts = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((n) => String(n).padStart(2, "0"))
    .join(":");
  return { id: String(++logCounter), timestamp: ts, message, level };
}

export function useAgentStream() {
  const [state, setState] = useState<AgentStreamState>({
    running: false,
    jobId: null,
    status: null,
    pipeline: INITIAL_PIPELINE,
    logs: [],
    finalOutput: null,
    validationScore: null,
    stepHistory: [],
    elapsedSeconds: null,
    error: null,
  });

  const stopRef = useRef<(() => void) | null>(null);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const addLog = useCallback((message: string, level: LogEntry["level"]) => {
    setState((s) => ({ ...s, logs: [...s.logs, makeLog(message, level)] }));
  }, []);

  const setNode = useCallback((node: PipelineNodeId, nodeState: NodeState) => {
    setState((s) => ({
      ...s,
      pipeline: { ...s.pipeline, [node]: nodeState },
    }));
  }, []);

  const run = useCallback(
    (req: RunRequest) => {
      // Reset
      if (timerRef.current) clearInterval(timerRef.current);
      startTimeRef.current = Date.now();

      setState({
        running: true,
        jobId: null,
        status: "in_progress",
        pipeline: INITIAL_PIPELINE,
        logs: [makeLog("Starting agent pipeline…", "info")],
        finalOutput: null,
        validationScore: null,
        stepHistory: [],
        elapsedSeconds: null,
        error: null,
      });

      // Live elapsed timer
      timerRef.current = setInterval(() => {
        setState((s) => ({
          ...s,
          elapsedSeconds: parseFloat(
            ((Date.now() - startTimeRef.current) / 1000).toFixed(1)
          ),
        }));
      }, 200);

      stopRef.current = streamAgent(
        req,
        (eventType, data) => {
          const d = data as Record<string, unknown>;

          if (eventType === "start") {
            setState((s) => ({ ...s, jobId: d.job_id as string }));
            addLog(`Job started: ${(d.job_id as string).slice(0, 8)}…`, "info");
          } else if (eventType === "step_start") {
            const node = d.node as PipelineNodeId;
            setNode(node, "active");
            addLog(`▶ ${node.replace(/_/g, " ")}…`, "warn");
          } else if (eventType === "step_done") {
            const node = d.node as PipelineNodeId;
            const msg = d.message as string;
            setNode(node, msg?.startsWith("❌") ? "error" : "done");
            addLog(msg || `✅ ${node} done`, msg?.startsWith("❌") ? "error" : "ok");
          } else if (eventType === "done") {
            const done = d as unknown as SSEDoneEvent;
            const elapsed = parseFloat(
              ((Date.now() - startTimeRef.current) / 1000).toFixed(1)
            );
            if (timerRef.current) clearInterval(timerRef.current);
            addLog(`✅ Completed in ${elapsed}s`, "ok");
            setState((s) => ({
              ...s,
              running: false,
              status: done.status as TaskStatus,
              finalOutput: done.final_output,
              validationScore: done.validation_score ?? null,
              stepHistory: done.step_history || [],
              elapsedSeconds: elapsed,
            }));
          } else if (eventType === "error") {
            const errMsg = d.error as string;
            if (timerRef.current) clearInterval(timerRef.current);
            addLog(`❌ ${errMsg}`, "error");
            setState((s) => ({
              ...s,
              running: false,
              status: "failed",
              error: errMsg,
            }));
          }
        },
        (err) => {
          if (timerRef.current) clearInterval(timerRef.current);
          const msg = err.message || "Connection failed";
          addLog(`❌ ${msg}`, "error");
          setState((s) => ({
            ...s,
            running: false,
            status: "failed",
            error: msg,
          }));
        }
      );
    },
    [addLog, setNode]
  );

  const stop = useCallback(() => {
    stopRef.current?.();
    if (timerRef.current) clearInterval(timerRef.current);
    setState((s) => ({ ...s, running: false }));
    addLog("⏹ Stopped by user", "warn");
  }, [addLog]);

  const reset = useCallback(() => {
    stopRef.current?.();
    if (timerRef.current) clearInterval(timerRef.current);
    setState({
      running: false,
      jobId: null,
      status: null,
      pipeline: INITIAL_PIPELINE,
      logs: [],
      finalOutput: null,
      validationScore: null,
      stepHistory: [],
      elapsedSeconds: null,
      error: null,
    });
  }, []);

  return { state, run, stop, reset };
}
