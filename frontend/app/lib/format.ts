/** Общие форматтеры — одни и те же соглашения на всех страницах. */

export const PHASE_LABEL: Record<string, string> = {
  created: "создана",
  running: "идёт",
  awaiting_finish: "ждёт завершения",
  finished: "завершена",
  aborted: "прервана",
};

export function phaseLabel(phase: string): string {
  return PHASE_LABEL[phase] ?? phase;
}

/** Фаза партии -> css-модификатор чипа (см. .chip--* в app.css). */
export function phaseTone(phase: string): "" | "--ok" | "--warn" | "--alarm" | "--reagent" {
  switch (phase) {
    case "running":
      return "--reagent";
    case "awaiting_finish":
      return "--warn";
    case "finished":
      return "--ok";
    case "aborted":
      return "--alarm";
    default:
      return "";
  }
}

/** Статус показания симуляции -> тон чипа. */
export function readingTone(status: string): "" | "--ok" | "--warn" | "--alarm" {
  switch (status) {
    case "ok":
    case "no_limits":
      return "--ok";
    case "low":
    case "high":
      return "--warn";
    case "bad_value":
    case "sensor_fault":
    case "unit_error":
      return "--alarm";
    default:
      return "";
  }
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
}

/** 450 -> "7:30"; секунды процесса/таймеры партии. */
export function fmtDuration(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec)) return "—";
  const s = Math.max(0, Math.round(sec));
  if (s < 60) return `${s} с`;
  const m = Math.floor(s / 60);
  const rest = s % 60;
  if (m < 60) return `${m}:${String(rest).padStart(2, "0")} мин`;
  return `${Math.floor(m / 60)} ч ${m % 60} мин`;
}

/** Число для табло: убираем хвостовые нули, но держим моноширинный вид. */
export function fmtNum(x: number | null | undefined, digits = 2): string {
  if (x == null || !Number.isFinite(x)) return "—";
  const s = x.toFixed(digits);
  return s.replace(/\.?0+$/, "") || "0";
}

/** v_in / детекторы окна: {"CaO": 62.5} -> "CaO 62,5" через запятую. */
export function fmtDict(d: Record<string, number> | null | undefined): string {
  if (!d || !Object.keys(d).length) return "—";
  return Object.entries(d)
    .map(([k, v]) => `${k} ${fmtNum(v)}`)
    .join(", ");
}

/** Химическая формула -> с подстрочными индексами: C3H6O3 -> C₃H₆O₃. */
const SUBS: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
  "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
};

export function chemText(formula: string): string {
  return (formula ?? "").replace(/(\d+)/g, (m) =>
    [...m].map((c) => SUBS[c] ?? c).join(""),
  );
}
