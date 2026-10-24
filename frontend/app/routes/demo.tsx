import { useEffect, useMemo, useRef, useState } from "react";

import { SeriesChart, type Series } from "~/components/chart";
import {
  Chip,
  Empty,
  Notice,
  PageHead,
  Panel,
  Spinner,
  StatBlock,
  TableScroll,
} from "~/components/ui";
import {
  ApiError,
  listFormulas,
  simRunReadings,
  simRunSteps,
  simStart,
  simStatus,
  simStop,
  type FormulaSummary,
  type SimReading,
  type SimStepRun,
} from "~/lib/api";
import { chemText, fmtNum } from "~/lib/format";
import { usePoll } from "~/lib/usePoll";

export function meta() {
  return [
    { title: "Демонстрация — диаграммы процесса" },
    {
      name: "description",
      content:
        "Диаграммы каждого этапа производства с цветовым выделением датчиков и сравнением отклонений от предписанных значений в реальном времени.",
    },
  ];
}

/* ---------- палитра датчиков: 12 визуально различимых цветов ---------- */

const SENSOR_PALETTE = [
  "#0e7490",
  "#c2410c",
  "#7c3aed",
  "#15803d",
  "#be123c",
  "#1d4ed8",
  "#a16207",
  "#9333ea",
  "#0f766e",
  "#be185d",
  "#4338ca",
  "#b45309",
];

/* =================================================================== */
/*  DeviationGauge — горизонтальная полоса: позиция значения в допуске  */
/* =================================================================== */

function DeviationGauge({
  value,
  expected,
  bandMin,
  bandMax,
  color,
  unit,
}: {
  value: number;
  expected: number | null;
  bandMin: number | null;
  bandMax: number | null;
  color: string;
  unit: string | null;
}) {
  const W = 300;
  const H = 40;
  const Y = 8;
  const BH = 16;

  const lo = bandMin ?? Math.min(value, expected ?? value) - 1;
  const hi = bandMax ?? Math.max(value, expected ?? value) + 1;
  const range = hi - lo || 1;
  const pad = range * 0.2;
  const vMin = lo - pad;
  const vMax = hi + pad;
  const vRange = vMax - vMin;

  const sx = (v: number) =>
    Math.max(0, Math.min(W, ((v - vMin) / vRange) * W));

  const bx0 = sx(bandMin ?? lo);
  const bx1 = sx(bandMax ?? hi);
  const vx = sx(value);
  const ex = expected != null ? sx(expected) : null;

  const inBand =
    (bandMin == null || value >= bandMin) &&
    (bandMax == null || value <= bandMax);
  const dotColor = inBand ? color : "var(--color-lamp-alarm)";
  const delta = expected != null ? value - expected : null;

  return (
    <div className="flex items-center gap-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-10 w-full max-w-[300px] flex-none">
        {/* трек */}
        <rect x={0} y={Y} width={W} height={BH} rx={3} fill="var(--color-steel-200)" />
        {/* допустимая полоса */}
        {bandMin != null && bandMax != null && (
          <rect x={bx0} y={Y} width={bx1 - bx0} height={BH} rx={3} fill={color} opacity={0.13} />
        )}
        {/* границы полосы */}
        {bandMin != null && (
          <line x1={bx0} y1={Y - 1} x2={bx0} y2={Y + BH + 1} stroke={color} strokeWidth={1.2} opacity={0.45} />
        )}
        {bandMax != null && (
          <line x1={bx1} y1={Y - 1} x2={bx1} y2={Y + BH + 1} stroke={color} strokeWidth={1.2} opacity={0.45} />
        )}
        {/* ожидание (пунктир) */}
        {ex != null && (
          <line
            x1={ex} y1={Y - 3} x2={ex} y2={Y + BH + 3}
            stroke="var(--color-steel-400)" strokeWidth={1.5} strokeDasharray="3 2"
          />
        )}
        {/* точка значения */}
        <circle cx={vx} cy={Y + BH / 2} r={6} fill={dotColor} stroke="#fff" strokeWidth={1.8} />
        {/* подписи */}
        {bandMin != null && (
          <text x={bx0} y={Y + BH + 12} fontSize={9} fill="var(--color-steel-500)" textAnchor="middle">
            {fmtNum(bandMin)}
          </text>
        )}
        {bandMax != null && (
          <text x={bx1} y={Y + BH + 12} fontSize={9} fill="var(--color-steel-500)" textAnchor="middle">
            {fmtNum(bandMax)}
          </text>
        )}
      </svg>

      <span className="num flex flex-none flex-col text-right text-sm leading-tight">
        <span style={{ color: dotColor }}>{fmtNum(value)}</span>
        {unit && <span className="readout-unit">{unit}</span>}
      </span>

      {delta != null && (
        <span className={`num flex-none text-xs ${inBand ? "text-lamp-ok" : "text-lamp-alarm"}`}>
          Δ&nbsp;{delta > 0 ? "+" : ""}
          {fmtNum(delta)}
        </span>
      )}
    </div>
  );
}

/* =================================================================== */
/*  SensorChart — серия факт + ожидание + полоса для одного датчика     */
/* =================================================================== */

function SensorChart({
  tag,
  color,
  readings,
  unit,
}: {
  tag: string;
  color: string;
  readings: SimReading[];
  unit: string | null;
}) {
  const series = useMemo<Series[]>(() => {
    const sorted = [...readings]
      .filter((r) => r.value != null)
      .sort((a, b) => a.elapsed_s - b.elapsed_s);
    if (sorted.length < 2) return [];

    const actual: Series = {
      name: `${tag} факт`,
      color,
      points: sorted.map((r) => ({ x: r.elapsed_s, y: r.value })),
      band: sorted
        .filter((r) => r.band_min != null && r.band_max != null)
        .map((r) => ({ x: r.elapsed_s, min: r.band_min!, max: r.band_max! })),
    };

    const expPts = sorted.filter((r) => r.expected != null);
    if (expPts.length >= 2) {
      return [
        actual,
        {
          name: "ожидание",
          color: "#9aa8b7",
          points: expPts.map((r) => ({ x: r.elapsed_s, y: r.expected })),
        },
      ];
    }

    return [actual];
  }, [readings, tag, color]);

  if (series.length === 0) {
    return <Empty>Мало точек для графика.</Empty>;
  }

  return (
    <SeriesChart
      series={series}
      height={170}
      xLabel="секунды"
      yLabel={unit ?? undefined}
    />
  );
}

/* =================================================================== */
/*  DeviationTimeChart — отклонения всех датчиков на одной оси (%)     */
/* =================================================================== */

function DeviationTimeChart({
  readingsByTag,
  tagColors,
}: {
  readingsByTag: Map<string, SimReading[]>;
  tagColors: Map<string, string>;
}) {
  const series = useMemo<Series[]>(() => {
    return [...readingsByTag.entries()]
      .map(([tag, rr]) => ({
        name: tag,
        color: tagColors.get(tag),
        points: rr
          .filter((r) => r.value != null && r.expected != null && r.expected !== 0)
          .map((r) => ({
            x: r.elapsed_s,
            y: ((r.value! - r.expected!) / Math.abs(r.expected!)) * 100,
          }))
          .sort((a, b) => a.x - b.x),
      }))
      .filter((s) => s.points.length >= 2);
  }, [readingsByTag, tagColors]);

  const zeroBand = useMemo<Series["band"]>(() => {
    if (!series.length) return undefined;
    const xs = series.flatMap((s) => s.points.map((p) => p.x));
    const lo = Math.min(...xs);
    const hi = Math.max(...xs);
    return [
      { x: lo, min: -5, max: 5 },
      { x: hi, min: -5, max: 5 },
    ];
  }, [series]);

  if (series.length === 0) return null;

  // добавляем «полосу нормы ±5 %» как первую серию (невидимая линия, видна только полоса)
  const withBand: Series[] = [
    {
      name: "±5 % норма",
      color: "var(--color-lamp-ok)",
      points: [],
      band: zeroBand,
    },
    ...series,
  ];

  return (
    <SeriesChart
      series={withBand}
      height={150}
      xLabel="секунды"
      yLabel="отклонение, %"
    />
  );
}

/* =================================================================== */
/*  StepSection — один этап: диаграммы + отклонения + таблица           */
/* =================================================================== */

function StepSection({
  step,
  stepKey,
  tagColors,
  readingsByTag,
  isActive,
  currentElapsed,
  plannedDuration,
}: {
  step: number;
  stepKey: string;
  tagColors: Map<string, string>;
  readingsByTag: Map<string, SimReading[]>;
  isActive: boolean;
  currentElapsed: number | null;
  plannedDuration: number | null;
}) {
  const tags = [...readingsByTag.keys()].sort();
  const progress =
    isActive && currentElapsed != null && plannedDuration != null && plannedDuration > 0
      ? Math.min(100, (currentElapsed / plannedDuration) * 100)
      : null;

  return (
    <section
      className={`panel ${isActive ? "ring-2 ring-reagent-200" : ""}`}
      aria-label={`Стадия ${step}`}
    >
      {/* заголовок стадии */}
      <div className="panel-head">
        <span className={`chip ${isActive ? "chip--reagent" : ""}`}>
          {isActive && <span className="lamp lamp--reagent lamp--pulse" />}
          Стадия {step}
        </span>
        <h3 className="panel-title font-mono text-[13px] font-medium">{chemText(stepKey)}</h3>
        {plannedDuration != null && (
          <span className="panel-note ml-auto">{fmtNum(plannedDuration, 0)} с</span>
        )}
      </div>

      {/* прогресс-бар */}
      {progress != null && (
        <div className="gauge mx-3 mt-3">
          <div className="gauge-fill" style={{ width: `${progress}%` }} />
        </div>
      )}

      {/* ----- диаграммы датчиков ----- */}
      <div className="grid gap-5 p-4 lg:grid-cols-2">
        {tags.map((tag) => {
          const rr = readingsByTag.get(tag) ?? [];
          const color = tagColors.get(tag) ?? "#666";
          const last = rr[rr.length - 1];
          const unit = last?.unit ?? null;

          return (
            <div key={tag} className="min-w-0 space-y-2">
              {/* шильдик датчика */}
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 flex-none rounded-full"
                  style={{ background: color }}
                  aria-hidden="true"
                />
                <span className="tagplate tagplate--live">{tag}</span>
                {unit && (
                  <span className="text-xs text-steel-500">{unit}</span>
                )}
                {last && last.value != null && (
                  <span className="num ml-auto text-sm font-medium" style={{ color }}>
                    {fmtNum(last.value)}
                  </span>
                )}
              </div>

              {/* график значения + ожидания */}
              <SensorChart tag={tag} color={color} readings={rr} unit={unit} />

              {/* полоса отклонения */}
              {last && last.value != null && (
                <DeviationGauge
                  value={last.value}
                  expected={last.expected}
                  bandMin={last.band_min}
                  bandMax={last.band_max}
                  color={color}
                  unit={unit}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* ----- совмещённый график отклонений ----- */}
      <div className="border-t border-steel-200 px-4 py-3">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-steel-500">
          Отклонения от ожидания, % — все датчики
        </p>
        <DeviationTimeChart readingsByTag={readingsByTag} tagColors={tagColors} />
      </div>

      {/* ----- сводная таблица ----- */}
      {tags.length > 0 && (
        <div className="border-t border-steel-200 px-4 py-3">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-steel-500">
            Сводка отклонений
          </p>
          <TableScroll>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Датчик</th>
                  <th scope="col" data-num>Факт</th>
                  <th scope="col" data-num>Ожидание</th>
                  <th scope="col" data-num>Δ абс.</th>
                  <th scope="col" data-num>Δ, %</th>
                  <th scope="col" data-num>Мин</th>
                  <th scope="col" data-num>Макс</th>
                  <th scope="col" data-num>Позиция</th>
                  <th scope="col">Статус</th>
                </tr>
              </thead>
              <tbody>
                {tags.map((tag) => {
                  const rr = readingsByTag.get(tag) ?? [];
                  const last = rr[rr.length - 1];
                  if (!last || last.value == null) return null;
                  const color = tagColors.get(tag) ?? "#666";
                  const delta =
                    last.expected != null ? last.value - last.expected : null;
                  const deltaPct =
                    delta != null && last.expected
                      ? (delta / Math.abs(last.expected)) * 100
                      : null;
                  const inBand =
                    (last.band_min == null || last.value >= last.band_min) &&
                    (last.band_max == null || last.value <= last.band_max);
                  const bandPos =
                    last.band_min != null &&
                    last.band_max != null &&
                    last.band_max !== last.band_min
                      ? ((last.value - last.band_min) /
                          (last.band_max - last.band_min)) *
                        100
                      : null;

                  return (
                    <tr key={tag}>
                      <td>
                        <span className="flex items-center gap-2">
                          <span
                            className="inline-block h-2.5 w-2.5 flex-none rounded-full"
                            style={{ background: color }}
                          />
                          <span className="tagplate">{tag}</span>
                        </span>
                      </td>
                      <td data-num>{fmtNum(last.value)}</td>
                      <td data-num>
                        {last.expected != null ? fmtNum(last.expected) : "—"}
                      </td>
                      <td data-num>
                        <span
                          className={
                            inBand ? "text-lamp-ok" : "text-lamp-alarm"
                          }
                        >
                          {delta != null
                            ? `${delta > 0 ? "+" : ""}${fmtNum(delta)}`
                            : "—"}
                        </span>
                      </td>
                      <td data-num>
                        {deltaPct != null
                          ? `${deltaPct > 0 ? "+" : ""}${fmtNum(deltaPct, 1)}%`
                          : "—"}
                      </td>
                      <td data-num>{fmtNum(last.band_min)}</td>
                      <td data-num>{fmtNum(last.band_max)}</td>
                      <td data-num>
                        {bandPos != null ? (
                          <span
                            className={
                              bandPos >= 0 && bandPos <= 100
                                ? ""
                                : "text-lamp-alarm"
                            }
                          >
                            {fmtNum(bandPos, 0)}%
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        <Chip
                          tone={inBand ? "--ok" : "--alarm"}
                          lamp
                        >
                          {inBand ? "норма" : last.status}
                        </Chip>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableScroll>
        </div>
      )}
    </section>
  );
}

/* =================================================================== */
/*  DemoPage — главная страница демонстрации                           */
/* =================================================================== */

export default function Demo() {
  /* --- загрузка справочника формул --- */
  const [formulas, setFormulas] = useState<FormulaSummary[]>([]);
  const [formulaId, setFormulaId] = useState<number | null>(null);

  useEffect(() => {
    listFormulas()
      .then((v) => {
        setFormulas(v);
        const preferred = v.find((f) => f.id === 15) ?? v[0];
        if (preferred) setFormulaId(preferred.id);
      })
      .catch(() => {});
  }, []);

  /* --- живой статус симуляции --- */
  const { data: status, refresh: refreshStatus } = usePoll(
    () => simStatus(),
    900,
    true,
  );

  /* --- отслеживаемый run --- */
  const [trackedRunId, setTrackedRunId] = useState<number | null>(null);
  const [readings, setReadings] = useState<SimReading[]>([]);
  const [stepInfo, setStepInfo] = useState<SimStepRun[]>([]);
  const lastId = useRef(0);

  // новый run → сбросить данные и начать накопление
  useEffect(() => {
    const rid = status?.run_id ?? null;
    if (rid != null && rid !== trackedRunId) {
      setTrackedRunId(rid);
      setReadings([]);
      lastId.current = 0;
      simRunSteps(rid).then(setStepInfo).catch(() => {});
    }
  }, [status?.run_id, trackedRunId]);

  // непрерывный опрос показаний
  useEffect(() => {
    if (trackedRunId == null) return;
    let alive = true;

    const poll = async () => {
      try {
        const rows = await simRunReadings(trackedRunId, {
          after_id: lastId.current,
          limit: 2000,
        });
        if (!alive || !rows.length) return;
        setReadings((prev) => [...prev, ...rows]);
        lastId.current = rows[rows.length - 1].id;
      } catch {
        /* не критично */
      }
    };

    poll(); // первый раз сразу
    const timer = setInterval(poll, 800);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [trackedRunId]);

  /* --- старт / стоп --- */
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepSec, setStepSec] = useState("14");
  const [tickSec, setTickSec] = useState("0.5");
  const [faultRate, setFaultRate] = useState("0.08");

  const start = async () => {
    if (formulaId == null) return;
    setStarting(true);
    setError(null);
    try {
      await simStart({
        formula_id: formulaId,
        step_seconds: Number(stepSec) || 14,
        tick_seconds: Number(tickSec) || 0.5,
        fault_rate: Number(faultRate) || 0.05,
        source: "auto",
      });
      refreshStatus();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const stop = async () => {
    try {
      await simStop();
      refreshStatus();
    } catch {}
  };

  const running = status?.running ?? false;

  /* --- производные данные --- */
  const allTags = useMemo(() => {
    const s = new Set<string>();
    for (const r of readings) s.add(r.tag);
    return [...s].sort();
  }, [readings]);

  const tagColors = useMemo(() => {
    const m = new Map<string, string>();
    allTags.forEach((t, i) => m.set(t, SENSOR_PALETTE[i % SENSOR_PALETTE.length]));
    return m;
  }, [allTags]);

  const byStep = useMemo(() => {
    const m = new Map<number, Map<string, SimReading[]>>();
    for (const r of readings) {
      if (r.value == null) continue;
      if (!m.has(r.step)) m.set(r.step, new Map());
      const step = m.get(r.step)!;
      if (!step.has(r.tag)) step.set(r.tag, []);
      step.get(r.tag)!.push(r);
    }
    return m;
  }, [readings]);

  const sortedSteps = [...byStep.keys()].sort((a, b) => a - b);

  /* --- общие статистики --- */
  const totalReadings = readings.length;
  const alertCount = readings.filter(
    (r) => r.status !== "ok" && r.status !== "no_limits",
  ).length;

  /* =================================================================== */
  return (
    <>
      <PageHead
        kicker="Демонстрация"
        title="Диаграммы процесса"
        lead="Диаграммы каждого этапа производства. Каждый датчик выделен цветом. Отклонения от предписанных значений обновляются в реальном времени."
      />

      {/* ---------- управление ---------- */}
      <Panel className="mb-5" title="Управление симуляцией">
        <div className="flex flex-wrap items-end gap-3">
          <label className="field min-w-56">
            <span className="field-label">Формула</span>
            <select
              className="select"
              value={formulaId ?? ""}
              onChange={(e) => setFormulaId(Number(e.target.value))}
            >
              {formulas.map((f) => (
                <option key={f.id} value={f.id}>
                  №{f.id} · {f.name} v{f.version}
                </option>
              ))}
            </select>
          </label>
          <label className="field w-24">
            <span className="field-label">Стадия, с</span>
            <input
              className="input input--num"
              type="number"
              min={1}
              step={1}
              value={stepSec}
              onChange={(e) => setStepSec(e.target.value)}
            />
          </label>
          <label className="field w-24">
            <span className="field-label">Тик, с</span>
            <input
              className="input input--num"
              type="number"
              min={0.05}
              max={60}
              step={0.05}
              value={tickSec}
              onChange={(e) => setTickSec(e.target.value)}
            />
          </label>
          <label className="field w-24">
            <span className="field-label">Сбои, %</span>
            <input
              className="input input--num"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={faultRate}
              onChange={(e) => setFaultRate(e.target.value)}
            />
          </label>

          {!running ? (
            <button
              className="btn btn--primary"
              onClick={start}
              disabled={starting || formulaId == null}
            >
              {starting ? "Запускаю…" : "▶ Запустить"}
            </button>
          ) : (
            <button className="btn btn--danger" onClick={stop}>
              ■ Остановить
            </button>
          )}
        </div>

        {/* статус */}
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <Chip tone={running ? "--reagent" : status?.run_id ? "--ok" : ""} lamp={running}>
            {running
              ? `идёт · стадия ${status?.step ?? "—"} · ${fmtNum(status?.elapsed_s, 1)} с`
              : status?.run_id
                ? `${status?.status ?? "завершена"} · run №${status.run_id}`
                : "не запущена"}
          </Chip>

          {totalReadings > 0 && (
            <div className="flex gap-4">
              <StatBlock label="Показаний" value={totalReadings} />
              <StatBlock
                label="Отклонений"
                value={alertCount}
                tone={alertCount > 0 ? "--warn" : "--ok"}
              />
              <StatBlock label="Датчиков" value={allTags.length} />
            </div>
          )}
        </div>

        {error && (
          <div className="mt-3">
            <Notice tone="--alarm">{error}</Notice>
          </div>
        )}
      </Panel>

      {/* ---------- легенда датчиков ---------- */}
      {allTags.length > 0 && (
        <div className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-sm border border-steel-200 bg-white px-4 py-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-steel-500">
            Датчики:
          </span>
          {allTags.map((tag) => {
            const color = tagColors.get(tag) ?? "#666";
            const lastR = readings.filter((r) => r.tag === tag).at(-1);
            return (
              <span key={tag} className="flex items-center gap-2 text-sm">
                <span
                  className="inline-block h-3.5 w-3.5 flex-none rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,.12)]"
                  style={{ background: color }}
                />
                <span className="tagplate tagplate--live">{tag}</span>
                {lastR?.unit && (
                  <span className="text-xs text-steel-500">{lastR.unit}</span>
                )}
                {lastR?.value != null && (
                  <span className="num text-xs font-medium" style={{ color }}>
                    {fmtNum(lastR.value)}
                  </span>
                )}
              </span>
            );
          })}
        </div>
      )}

      {/* ---------- нет данных ---------- */}
      {sortedSteps.length === 0 && !running && (
        <Panel>
          <Empty>
            Данных пока нет. Выберите формулу и нажмите «Запустить» — диаграммы
            каждого этапа появятся в реальном времени, с цветовым выделением
            датчиков и сравнением отклонений.
          </Empty>
        </Panel>
      )}

      {sortedSteps.length === 0 && running && (
        <Panel>
          <Spinner label="Ожидаю первые показания…" />
        </Panel>
      )}

      {/* ---------- блоки стадий ---------- */}
      <div className="space-y-5">
        {sortedSteps.map((step) => {
          const info = stepInfo.find((s) => s.step === step);
          const isActive = running && status?.step === step;
          return (
            <StepSection
              key={step}
              step={step}
              stepKey={info?.key ?? `Стадия ${step}`}
              tagColors={tagColors}
              readingsByTag={byStep.get(step)!}
              isActive={isActive}
              currentElapsed={
                isActive ? (status?.elapsed_s ?? null) : null
              }
              plannedDuration={
                info?.duration_s ?? (status?.duration_s ?? null)
              }
            />
          );
        })}
      </div>
    </>
  );
}
