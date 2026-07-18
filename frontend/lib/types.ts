export type Confidence = "HIGH" | "MEDIUM" | "LOW";

export interface ChartSpec {
  type: "line" | "bar" | "grouped_bar" | "scatter" | "kpi" | "table";
  reason: string;
  encodings: Record<string, string | string[]>;
  forecastable?: boolean;
}

export interface Forecast {
  method: string;
  horizon: number;
  periods: string[];
  point: number[];
  lower: number[];
  upper: number[];
  history_periods: string[];
  history_values: number[];
  notes: string[];
}

export interface Anomaly {
  index: number;
  value: number;
  score: number;
  direction: string;
}

export interface AnalysisResult {
  query_id: string;
  question: string;
  blocked: boolean;
  sql: string | null;
  sql_explanation: string | null;
  generator: string;
  columns: string[];
  rows: Record<string, any>[];
  result_meta: { row_count?: number; latency_ms?: number; truncated?: boolean };
  chart_spec: ChartSpec;
  forecast: Forecast | null;
  anomalies: Anomaly[];
  narrative: string;
  confidence: Confidence;
  assumptions: string[];
  validation_errors: string[];
  error: string | null;
  trace_url: string | null;
  conversation_id: string | null;
  resolved_question: string | null;
  suggested_followups: string[];
  rootcause: RootCause | null;
}

export interface RootCauseContributor {
  member: string;
  from: number;
  to: number;
  delta: number;
  contribution_pct: number | null;
}

export interface RootCause {
  available: boolean;
  decomposition_dimension: string;
  period_from: string;
  period_to: string;
  total_from: number;
  total_to: number;
  total_change: number;
  pct_change: number;
  contributors: RootCauseContributor[];
  narrative: string;
}

export interface BriefingMetric {
  label: string;
  column: string;
  unit: string;
  value: number;
  value_fmt: string;
  mom_pct: number;
  direction: "up" | "down";
  sentiment: "good" | "bad" | "neutral";
  anomaly: boolean;
  spark: number[];
  forecast_next: number | null;
  period_label: string;
}

export interface WhatChanged {
  label: string;
  mom_pct: number;
  sentiment: string;
  narrative: string;
  rootcause?: RootCause;
}

export interface Briefing {
  available: boolean;
  reason?: string;
  connection_id: string;
  as_of: string;
  headline: string;
  metrics: BriefingMetric[];
  what_changed: WhatChanged[];
  watchouts: { message: string; severity: string }[];
  forecast_outlook: string | null;
  generated_note: string;
}

export interface AgentEvent {
  node: string;
  status: string;
  ts: number;
  [k: string]: any;
}

export const PIPELINE_STEPS = [
  { node: "context_resolver", label: "Understanding context" },
  { node: "planner", label: "Planning" },
  { node: "schema_retriever", label: "Retrieving schema" },
  { node: "sql_generator", label: "Writing SQL" },
  { node: "sql_validator", label: "Validating" },
  { node: "executor", label: "Running" },
  { node: "rootcause", label: "Root-cause" },
  { node: "forecaster", label: "Forecasting" },
  { node: "narrator", label: "Narrating" },
] as const;
