import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

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
  abortBatch,
  ApiError,
  batchRecommendations,
  finishBatch,
  getBatch,
  nextStep,
  type BatchDetail as BatchDetailType,
  type LiveWindow,
  type Recommendation,
} from "~/lib/api";
import {
  chemText,
  fmtDict,
  fmtDuration,
  fmtNum,
  fmtTime,
  phaseLabel,
  phaseTone,
} from "~/lib/format";
import { usePoll } from "~/lib/usePoll";

export function meta() {
  return [
    { title: "Ведение партии — пульт оператора" },
    {
      name: "description",
      content:
        "Живое ведение партии: ход стадий, усреднённые показания датчиков по окнам, рекомендации оператору и завершение с фиксацией качества.",
    },
  ];
}

const POLL_MS = 1500;

/** Живой график средних значений по окнам: одна линия на датчик. */
function WindowsChart({ windows }: { windows: LiveWindow[] }) {
  const series = useMemo<Series[]>(() => {
    const byTag = new Map<string, { x: number; y: number | null }[]>();
    for (const w of windows) {
      for (const [tag, v] of Object.entries(w.values)) {
        if (!byTag.has(tag)) byTag.set(tag, []);
        byTag.get(tag)!.push({ x: w.time_s, y: v });
      }
    }
    return [...byTag.entries()].map(([name, points]) => ({
      name,
      points: points.sort((a, b) => a.x - b.x),
    }));
  }, [windows]);

  if (!windows.length) return <Empty>Окон усреднения пока нет.</Empty>;
  return (
    <SeriesChart
      series={series}
      height={200}
      xLabel="секунды от начала партии"
      yLabel="среднее по окну"
    />
  );
}

/** Последние окна в виде таблицы (как в старом пульте, но компактнее). */
function WindowsTable({ windows }: { windows: LiveWindow[] }) {
  if (!windows.length) return null;
  return (
    <TableScroll>
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col" data-num>Шаг</th>
            <th scope="col" data-num>Окно, с</th>
            <th scope="col">Средние (V)</th>
            <th scope="col" data-num>Точек</th>
          </tr>
        </thead>
        <tbody>
          {windows.map((w, i) => (
            <tr key={`${w.step}-${w.time_s}-${i}`}>
              <td data-num>{w.step}</td>
              <td data-num>{fmtNum(w.time_s, 1)}</td>
              <td>
                <span className="flex flex-wrap gap-x-3 gap-y-0.5">
                  {Object.entries(w.values).map(([k, v]) => (
                    <span key={k} className="font-mono text-xs">
                      <span className="text-steel-500">{k}=</span>
                      {fmtNum(v)}
                    </span>
                  ))}
                </span>
              </td>
              <td data-num>{w.n_samples}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

function StepTimeline({ batch }: { batch: BatchDetailType }) {
  if (!batch.steps.length) return <Empty>Шаги ещё не начаты.</Empty>;
  return (
    <ol className="space-y-2">
      {batch.steps.map((s) => {
        const running = s.status === "running";
        const progress =
          running && batch.live?.step === s.step && batch.live.step_planned_s
            ? Math.min(100, (batch.live.step_elapsed_s! / batch.live.step_planned_s) * 100)
            : s.status === "done"
              ? 100
              : 0;
        const tone =
          s.status === "done" ? "--done" : s.status === "aborted" ? "--alarm" : "";
        return (
          <li key={s.step} className="flex items-center gap-3">
            <span className="num w-6 flex-none text-center font-mono text-sm text-steel-500">
              {s.step}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className={`text-sm ${running ? "font-medium text-reagent-700" : "text-steel-700"}`}>
                  Стадия {s.step}
                  {running && batch.live?.step === s.step && (
                    <span className="num ml-2 text-xs text-steel-500">
                      {fmtNum(batch.live.step_elapsed_s, 1)} / {fmtNum(batch.live.step_planned_s, 0)} с
                    </span>
                  )}
                </span>
                <span className="flex-none text-xs text-steel-500">
                  {s.status === "done"
                    ? `готово${s.ended_by === "operator" ? " (оператор)" : ""}`
                    : s.status === "aborted"
                      ? "прервано"
                      : running
                        ? "идёт"
                        : s.status}
                </span>
              </div>
              <div className="gauge mt-1">
                <div className={`gauge-fill gauge-fill${tone}`} style={{ width: `${progress}%` }} />
              </div>
            </div>
            <span className="num hidden w-16 flex-none text-right font-mono text-xs text-steel-500 sm:block">
              {fmtTime(s.started_at)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

type RecRow = Pick<
  Recommendation,
  "step" | "time_s" | "tag" | "value" | "ref_avg" | "delta" | "message"
> & { id?: number; ref_std?: number };

function Recommendations({
  batchId,
  liveRecs,
}: {
  batchId: number;
  liveRecs: RecRow[];
}) {
  // Полная история из БД (after_id — подгрузка только новых); пока сессия жива,
  // последние рекомендации дублируются в live.recommendations — ими и подстраховываемся.
  const [all, setAll] = useState<RecRow[]>([]);
  const lastId = useRef(0);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const rows = await batchRecommendations(batchId, { after_id: lastId.current });
        if (!alive || !rows.length) return;
        setAll((prev) => [...prev, ...rows]);
        lastId.current = rows[rows.length - 1].id;
      } catch {
        /* не критично: live.recommendations продолжает показывать свежее */
      }
    };
    load();
    const t = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [batchId]);

  const list = all.length ? all.slice().reverse() : liveRecs.slice().reverse();

  return (
    <div className="space-y-2">
      {list.length === 0 ? (
        <Empty>Рекомендаций пока нет — значения в пределах эталонной полосы.</Empty>
      ) : (
        list.map((rec, i) => (
          <div
            key={rec.id ?? `live-${i}`}
            className="notice notice--warn flex flex-wrap items-baseline gap-x-2 gap-y-1"
          >
            <span className="tagplate">{rec.tag}</span>
            <span className="text-sm text-steel-800">{rec.message}</span>
            <span className="num ml-auto text-xs text-steel-500">
              стадия {rec.step} · {fmtNum(rec.time_s, 1)} с · сейчас {fmtNum(rec.value)}, эталон{" "}
              {fmtNum(rec.ref_avg)}
              {rec.ref_std != null ? ` ± ${fmtNum(rec.ref_std)}` : ""}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

function FinishForm({ batchId, onDone }: { batchId: number; onDone: () => void }) {
  const [vFinish, setVFinish] = useState("");
  const [quality, setQuality] = useState("");
  const [unit, setUnit] = useState("%");
  const [isRef, setIsRef] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (vFinish === "" || quality === "") {
      setError("Введите выход продукта и качество.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await finishBatch(batchId, {
        v_finish: Number(vFinish),
        quality: Number(quality),
        quality_unit: unit || "%",
        is_reference: isRef,
      });
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
      setBusy(false);
    }
  };

  return (
    <Panel title="Завершение партии" note="выход продукта и качество">
      <div className="flex flex-wrap items-end gap-3">
        <label className="field w-28">
          <span className="field-label">Выход, кг</span>
          <input className="input input--num" type="number" min="0" step="any" value={vFinish} onChange={(e) => setVFinish(e.target.value)} />
        </label>
        <label className="field w-28">
          <span className="field-label">Качество</span>
          <input className="input input--num" type="number" min="0" step="any" value={quality} onChange={(e) => setQuality(e.target.value)} />
        </label>
        <label className="field w-20">
          <span className="field-label">Ед.</span>
          <input className="input" value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={16} />
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm text-steel-700">
          <input type="checkbox" checked={isRef} onChange={(e) => setIsRef(e.target.checked)} />
          сделать эталонной
        </label>
        <button className="btn btn--primary" onClick={submit} disabled={busy}>
          {busy ? "Завершаю…" : "Завершить партию"}
        </button>
      </div>
      {error && (
        <div className="mt-3">
          <Notice tone="--alarm">{error}</Notice>
        </div>
      )}
    </Panel>
  );
}

export default function BatchDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const batchId = Number(id);
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const { data: batch, error } = usePoll(
    () => getBatch(batchId),
    POLL_MS,
    Number.isFinite(batchId) && batchId > 0,
  );

  const running = batch?.status === "running";
  const live = batch?.live ?? null;

  const doAction = async (fn: () => Promise<unknown>, okMsg?: string) => {
    setActing(true);
    setActionError(null);
    try {
      await fn();
      if (okMsg) setActionError(null);
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setActing(false);
    }
  };

  if (!Number.isFinite(batchId) || batchId <= 0) {
    return (
      <>
        <PageHead kicker="Производство" title="Партия не найдена" />
        <Notice tone="--alarm">Некорректный номер партии.</Notice>
      </>
    );
  }

  if (error && !batch) {
    return (
      <>
        <PageHead kicker="Производство" title="Партия" aside={<Link to="/batches" className="btn">К журналу</Link>} />
        <Notice tone="--alarm">{error}</Notice>
      </>
    );
  }

  if (!batch) {
    return (
      <>
        <PageHead kicker="Производство" title={`Партия №${batchId}`} />
        <Spinner label="Загружаю партию…" />
      </>
    );
  }

  const windows = live?.last_windows ?? [];

  return (
    <>
      <PageHead
        kicker={`Формула №${batch.formula_id}`}
        title={`Партия №${batch.id}`}
        lead={
          <span className="flex flex-wrap items-center gap-2">
            <Chip tone={phaseTone(batch.phase)} lamp={running}>
              {phaseLabel(batch.phase)}
            </Chip>
            {batch.is_reference && <Chip tone="--ok">эталонная</Chip>}
            {live?.receiving && (
              <span className="text-steel-500">приём показаний · ускорение ×{fmtNum(live.speed, 0)}</span>
            )}
          </span>
        }
        aside={
          <>
            {running && batch.current_step != null && (
              <button className="btn" onClick={() => doAction(() => nextStep(batchId))} disabled={acting}>
                Завершить шаг досрочно
              </button>
            )}
            {running && (
              <button className="btn btn--danger" onClick={() => doAction(() => abortBatch(batchId))} disabled={acting}>
                Прервать партию
              </button>
            )}
            <Link to="/batches" className="btn">К журналу</Link>
          </>
        }
      />

      {actionError && (
        <div className="mb-4">
          <Notice tone="--alarm">{actionError}</Notice>
        </div>
      )}
      {live?.error && (
        <div className="mb-4">
          <Notice tone="--alarm">Сбой обработки показаний: {live.error}</Notice>
        </div>
      )}

      {/* живая сводка */}
      <Panel className="mb-4" title="Ход партии" note={live ? `процессное время ${fmtNum(live.process_time_s, 1)} с` : "приём не активен"}>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatBlock label="Текущая стадия" value={batch.current_step ?? "—"} />
          <StatBlock
            label="Процессное время"
            value={fmtNum(live?.process_time_s ?? batch.t_total_sec, 1)}
            unit="с"
          />
          <StatBlock label="Сырьё" value={<span className="text-sm font-normal">{fmtDict(batch.v_in)}</span>} />
          <StatBlock
            label="Эталонов в сравнении"
            value={live?.reference_batches.length ?? "—"}
          />
          <StatBlock
            label="Окно усреднения"
            value={live ? fmtNum(live.window_s, 1) : "—"}
            unit="с"
          />
        </div>

        {live && (
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t border-steel-200 pt-3 font-mono text-xs text-steel-500">
            <span>
              показаний: принято <b className="text-lamp-ok">{live.readings.accepted}</b>, не этой стадии{" "}
              {live.readings.ignored}, мусор <b className={live.readings.bad_value ? "text-lamp-alarm" : ""}>{live.readings.bad_value}</b>,
              вне пределов <b className={live.readings.out_of_range ? "text-lamp-warn" : ""}>{live.readings.out_of_range}</b>
            </span>
            <span>
              OPC-файл: {live.opc.read}/{live.opc.total} строк
            </span>
          </div>
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Стадии">
          <StepTimeline batch={batch} />
        </Panel>

        <Panel title="Показания по окнам" note={windows.length ? "последние окна" : undefined}>
          <WindowsChart windows={windows} />
          <div className="mt-3">
            <WindowsTable windows={windows} />
          </div>
        </Panel>
      </div>

      <div className="mt-4">
        <Panel
          title="Рекомендации оператору"
          note={batch.recommendations_total ? `всего ${batch.recommendations_total}` : undefined}
        >
          <Recommendations batchId={batchId} liveRecs={live?.recommendations ?? []} />
        </Panel>
      </div>

      {running && (
        <div className="mt-4">
          <FinishForm batchId={batchId} onDone={() => navigate(`/batches/${batchId}`)} />
        </div>
      )}

      {!running && batch.status !== "created" && (
        <div className="mt-4">
          <Panel title="Итог партии">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatBlock label="Выход" value={batch.v_finish != null ? fmtNum(batch.v_finish) : "—"} unit="кг" />
              <StatBlock
                label="Качество"
                value={batch.quality != null ? fmtNum(batch.quality) : "—"}
                unit={batch.quality_unit ?? ""}
                tone={batch.quality != null ? "--ok" : undefined}
              />
              <StatBlock label="Длительность" value={fmtDuration(batch.t_total_sec)} />
              <StatBlock label="Статус" value={phaseLabel(batch.phase)} />
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
