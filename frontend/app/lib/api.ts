/**
 * Клиент API бэкенда (FastAPI, app/). Все пути относительные: в dev их
 * проксирует vite (vite.config.ts), в контейнере — nginx (docker/nginx.conf).
 * Форматы ответов один в один повторяют app/routers/*.py.
 */

// ------------------------------------------------------------------ типы

export type Sensor = {
  id: number;
  tag: string;
  parameter: string;
  unit: string;
  instrument: string;
  valid_min: number | null;
  valid_max: number | null;
};

export type FormulaSummary = {
  id: number;
  name: string;
  version: number;
  created_at: string | null;
};

export type SensorRange = { min?: number | null; max?: number | null };

export type FormulaStepSensor = {
  limits: { pre?: SensorRange | null; during?: SensorRange | null; post?: SensorRange | null };
  parameter: string;
  unit?: string;
};

export type FormulaStep = {
  step: number;
  step_key: string;
  step_value: string;
  in_data: Record<string, number>;
  out_data: Record<string, number>;
  constant: Record<string, number>;
  amount_time_min: number | null;
  sensors: Record<string, FormulaStepSensor>;
};

export type FormulaDetail = {
  id: number;
  name: string;
  version: number;
  steps: FormulaStep[];
};

export type CalcStepResult = {
  step: number;
  equation: string;
  warnings: string[];
  product: string;
  limiting: string;
  inputs_kg: Record<string, number>;
  unreacted_kg: Record<string, number>;
  theoretical_kg: Record<string, number>;
  constants: Record<string, number>;
  factor: number;
  practical_kg: Record<string, number>;
  expected_kg: number | null;
  deviation_pct: number | null;
  quality: number | null;
};

export type CalcResult = {
  formula: { id: number; name: string; version: number };
  final_product: string;
  final_mass_kg: number;
  final_theoretical_kg: number;
  total_yield_pct: number | null;
  quality: number | null;
  quality_basis: string;
  warnings: string[];
  steps: CalcStepResult[];
  spread_pct?: number;
  final_mass_range_kg?: [number, number];
};

export type BatchPhase = "created" | "running" | "awaiting_finish" | "finished" | "aborted";

export type BatchSummary = {
  id: number;
  formula_id: number;
  status: string;
  phase: BatchPhase;
  v_in: Record<string, number> | null;
  started_at: string | null;
  finished_at: string | null;
  current_step: number | null;
  t_total_sec: number | null;
  v_finish: number | null;
  quality: number | null;
  quality_unit: string | null;
  is_reference: boolean;
};

export type BatchStepRow = {
  step: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  planned_seconds: number | null;
  ended_by: string | null;
};

export type LiveWindow = {
  step: number;
  time_s: number;
  values: Record<string, number>;
  n_samples: number;
};

export type LiveStatus = {
  receiving: boolean;
  process_time_s: number;
  step: number | null;
  step_elapsed_s: number | null;
  step_planned_s: number | null;
  steps_done: boolean;
  speed: number;
  window_s: number;
  reference_batches: number[];
  opc: { read: number; total: number };
  readings: { accepted: number; ignored: number; bad_value: number; out_of_range: number };
  last_windows: LiveWindow[];
  recommendations: LiveRecommendation[];
  error: string | null;
};

export type LiveRecommendation = {
  step: number;
  time_s: number;
  tag: string;
  value: number;
  ref_avg: number;
  delta: number;
  message: string;
};

export type BatchDetail = BatchSummary & {
  steps: BatchStepRow[];
  recommendations_total: number;
  live: LiveStatus | null;
};

export type BatchWindowRow = {
  step: number;
  time_s: number;
  V: Record<string, number>;
  n_samples: number;
};

export type Recommendation = {
  id: number;
  step: number;
  time_s: number;
  tag: string;
  value: number;
  ref_avg: number;
  ref_std: number;
  n_refs: number;
  delta: number;
  threshold: number;
  message: string;
};

export type StartBatchOptions = {
  opc_file?: string | null;
  speed?: number;
  window_seconds?: number;
  k?: number;
  min_ref_quality?: number | null;
  ref_limit?: number;
};

export type StartBatchResult = BatchSummary & {
  opc_file: string;
  reference_batches: number[];
  steps: { step: number; planned_seconds: number | null; sensors: string[] }[];
};

export type FinishBatchInput = {
  v_finish: number;
  quality: number;
  quality_unit?: string;
  is_reference?: boolean;
};

// --- симуляция

export type SimStatus = {
  run_id: number | null;
  running: boolean;
  step: number | null;
  step_key?: string;
  title?: string;
  duration_s?: number | null;
  total_steps: number;
  readings: number;
  alerts: number;
  elapsed_s: number;
  sources?: Record<string, string>;
  status?: string;
  recent_alerts: SimAlertShort[];
};

export type SimAlertShort = {
  at: string;
  step: number;
  tag: string;
  status: string;
  value: number | null;
  target: number | null;
  message: string;
};

export type SimRunSummary = {
  run_id: number;
  formula_id: number;
  status: string;
  tick_seconds: number;
  source: string;
  started_at: string | null;
  finished_at: string | null;
  note: string | null;
};

export type SimStepRun = {
  step: number;
  key: string;
  duration_s: number;
  ticks: number;
  sources: string | null;
  status: string;
};

export type SimReading = {
  id: number;
  step: number;
  elapsed_s: number;
  tag: string;
  value: number | null;
  raw: string | null;
  unit: string | null;
  status: string;
  expected: number | null;
  band_min: number | null;
  band_max: number | null;
  source: string;
  label_anomaly: boolean | null;
  label_type: string | null;
};

export type SimAlert = {
  id: number;
  step: number;
  tag: string;
  kind: string;
  value: number | null;
  target: number | null;
  message: string;
};

export type SimStartInput = {
  formula_id: number;
  steps?: number[] | null;
  tick_seconds?: number;
  step_seconds?: number | null;
  step_durations?: Record<number, number>;
  save_durations?: boolean;
  source?: "auto" | "file" | "synthetic";
  fault_rate?: number;
  seed?: number | null;
  reference_batches?: number;
};

export type ReferenceSensor = {
  tag: string;
  parameter: string | null;
  unit: string | null;
  band_start: SensorRange | null;
  band_end: SensorRange | null;
  start_mean: number | null;
  end_mean: number | null;
  n_batches: number | null;
};

export type ReferenceStep = {
  step: number;
  step_key: string;
  amount_time_seconds: number | null;
  sensors: ReferenceSensor[];
};

// ------------------------------------------------------------------ запросы

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(formatDetail(detail) ?? fallback);
    this.status = status;
    this.detail = detail;
  }
}

/** detail из FastAPI -> человекочитаемая строка (включая ошибки pydantic). */
export function formatDetail(detail: unknown): string | null {
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => `${(e.loc ?? []).slice(1).join(".")}: ${e.msg}`)
      .join("; ");
  }
  if (typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    if (typeof d.error === "string") {
      const extra = d.tags ?? d.items;
      return Array.isArray(extra) && extra.length
        ? `${d.error}: ${extra.join(", ")}`
        : d.error;
    }
    return JSON.stringify(detail);
  }
  return String(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch (e) {
    throw new ApiError(0, null, `Нет связи с сервером: ${(e as Error).message}`);
  }
  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    throw new ApiError(res.status, (body as { detail?: unknown })?.detail ?? body, `HTTP ${res.status}`);
  }
  return body as T;
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// --- датчики
export const listSensors = () => request<Sensor[]>("/api/sensors");

// --- формулы
export const listFormulas = () => request<FormulaSummary[]>("/api/formulas");
export const getFormula = (id: number) => request<FormulaDetail>(`/api/formulas/${id}`);
export const createFormula = (body: unknown) =>
  request<{ id: number; name: string; version: number; steps_count: number }>(
    "/api/formulas",
    json("POST", body),
  );
export const calculateFormula = (
  id: number,
  body: { inputs?: Record<string, number>; constants?: Record<string, number>; spread_pct?: number; tolerance_pct?: number },
) => request<CalcResult>(`/api/formulas/${id}/calculate`, json("POST", body));

// --- партии
export const listBatches = (params?: { formula_id?: number; only_reference?: boolean }) => {
  const q = new URLSearchParams();
  if (params?.formula_id != null) q.set("formula_id", String(params.formula_id));
  if (params?.only_reference) q.set("only_reference", "true");
  const s = q.toString();
  return request<BatchSummary[]>(`/api/batches${s ? `?${s}` : ""}`);
};
export const getBatch = (id: number) => request<BatchDetail>(`/api/batches/${id}`);
export const createBatch = (formula_id: number, v_in?: Record<string, number> | null) =>
  request<BatchSummary>("/api/batches", json("POST", { formula_id, v_in }));
export const setBatchVIn = (id: number, v_in: Record<string, number>) =>
  request<BatchSummary>(`/api/batches/${id}/v_in`, json("PUT", { v_in }));
export const startBatch = (id: number, opts: StartBatchOptions = {}) =>
  request<StartBatchResult>(`/api/batches/${id}/start`, json("POST", { speed: 1, ...opts }));
export const nextStep = (id: number) =>
  request<BatchDetail & { live: LiveStatus | null }>(`/api/batches/${id}/next-step`, { method: "POST" });
export const finishBatch = (id: number, body: FinishBatchInput) =>
  request<BatchSummary>(`/api/batches/${id}/finish`, json("POST", body));
export const abortBatch = (id: number) =>
  request<BatchSummary>(`/api/batches/${id}/abort`, { method: "POST" });
export const setBatchReference = (id: number, is_reference: boolean) =>
  request<BatchSummary>(`/api/batches/${id}/reference`, json("PUT", { is_reference }));
export const batchMetrics = (id: number, step?: number) =>
  request<BatchWindowRow[]>(`/api/batches/${id}/metrics${step != null ? `?step=${step}` : ""}`);
export const batchRecommendations = (id: number, params?: { step?: number; after_id?: number }) => {
  const q = new URLSearchParams();
  if (params?.step != null) q.set("step", String(params.step));
  if (params?.after_id != null) q.set("after_id", String(params.after_id));
  const s = q.toString();
  return request<Recommendation[]>(`/api/batches/${id}/recommendations${s ? `?${s}` : ""}`);
};

// --- симуляция
export const simStatus = () => request<SimStatus>("/api/simulation/status");
export const simStart = (body: SimStartInput) =>
  request<{ run_id: number; status: string; total_seconds: number; steps: SimStepRun[] }>(
    "/api/simulation/start",
    json("POST", body),
  );
export const simStop = () =>
  request<{ stopped: boolean; run_id: number | null }>("/api/simulation/stop", { method: "POST" });
export const simRuns = () => request<SimRunSummary[]>("/api/simulation/runs");
export const simRunSteps = (runId: number) => request<SimStepRun[]>(`/api/simulation/runs/${runId}/steps`);
export const simRunReadings = (
  runId: number,
  params?: { step?: number; tag?: string; only_alerts?: boolean; after_id?: number; limit?: number },
) => {
  const q = new URLSearchParams();
  if (params?.step != null) q.set("step", String(params.step));
  if (params?.tag) q.set("tag", params.tag);
  if (params?.only_alerts) q.set("only_alerts", "true");
  if (params?.after_id != null) q.set("after_id", String(params.after_id));
  q.set("limit", String(params?.limit ?? 200));
  return request<SimReading[]>(`/api/simulation/runs/${runId}/readings?${q}`);
};
export const simRunAlerts = (runId: number, step?: number) =>
  request<SimAlert[]>(`/api/simulation/runs/${runId}/alerts${step != null ? `?step=${step}` : ""}`);
export const simGenerateReference = (body: { formula_id: number; n_batches?: number; seed?: number | null }) =>
  request<{ formula_id: number; n_batches: number; rows_per_step: Record<string, number>; total_rows: number }>(
    "/api/simulation/reference/generate",
    json("POST", body),
  );
export const simGetReference = (formulaId: number) =>
  request<{ formula_id: number; steps: ReferenceStep[] }>(`/api/simulation/reference/${formulaId}`);
export const simSetStepDuration = (formulaId: number, step: number, seconds: number) =>
  request<{ formula_id: number; step: number; amount_time_seconds: number }>(
    `/api/simulation/formulas/${formulaId}/steps/${step}/duration`,
    json("PATCH", { seconds }),
  );
