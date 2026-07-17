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
}

export interface AgentEvent {
  node: string;
  status: string;
  ts: number;
  [k: string]: any;
}

export const PIPELINE_STEPS = [
  { node: "planner", label: "Planning" },
  { node: "schema_retriever", label: "Retrieving schema" },
  { node: "sql_generator", label: "Writing SQL" },
  { node: "sql_validator", label: "Validating" },
  { node: "executor", label: "Running" },
  { node: "forecaster", label: "Forecasting" },
  { node: "narrator", label: "Narrating" },
] as const;
