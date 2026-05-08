// src/lib/types.ts

export type TaskStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "needs_retry"
  | "awaiting_human";

export type AgentType = "research" | "analysis" | "writer";

export type OutputFormat = "markdown" | "json";

export interface SubTask {
  id: string;
  description: string;
  agent_type: AgentType;
  status: TaskStatus;
  result?: string;
  error?: string;
}

export interface ValidationResult {
  passed: boolean;
  score: number;
  factual_accuracy: number;
  task_completion: number;
  format_compliance: number;
  feedback: string;
  requires_retry: boolean;
}

export interface RunRequest {
  user_input: string;
  session_id?: string;
  output_format: OutputFormat;
}

export interface RunResponse {
  job_id: string;
  status: TaskStatus;
  final_output?: string;
  validation_score?: number;
  step_history: string[];
  error_log: string[];
  tokens_used: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_provider: string;
  llm_model: string;
  llm_type: string;
}

export interface EvalDimension {
  score: number;
  reasoning: string;
  examples: string[];
}

export interface EvalResult {
  faithfulness: EvalDimension;
  answer_relevance: EvalDimension;
  completeness: EvalDimension;
  clarity: EvalDimension;
  overall_score: number;
  passed: boolean;
  summary: string;
  latency_ms: number;
}

// SSE event payloads
export interface SSEStartEvent {
  job_id: string;
}

export interface SSEStepEvent {
  node: string;
  job_id: string;
  message?: string;
}

export interface SSEDoneEvent {
  job_id: string;
  status: string;
  final_output: string;
  validation_score?: number;
  step_history: string[];
}

export interface SSEErrorEvent {
  error: string;
  job_id: string;
}

export type LogLevel = "info" | "ok" | "warn" | "error";

export interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  level: LogLevel;
}

export type PipelineNodeId =
  | "memory_retrieval"
  | "planner"
  | "executor"
  | "validator";

export type NodeState = "idle" | "active" | "done" | "error";
