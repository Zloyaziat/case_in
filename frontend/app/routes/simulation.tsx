import { useEffect, useState } from "react";

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
  simGetReference,
  simRuns,
  simStart,
  simStatus,
  simStop,
  type FormulaSummary,
  type ReferenceStep,
  type SimRunSummary,
  type SimStatus,
} from "~/lib/api";
import { fmtDateTime, fmtNum, readingTone } from "~/lib/format";
import { usePoll } from "~/lib/usePoll";

export function meta() {
  return [
    { title: "Симуляция — пульт оператора" },
    {
      name: "description",
      content:
        "Симуляция стадий: прогон формулы на файловых или синтетических показаниях датчиков, эталонные полосы и сигналы оператору.",
    },
  ];
}

const STATUS_TONE: Record<string, "" | "--ok" | "--warn" | "--alarm" | "--reagent"> = {
  running: "--reagent",
  finished: "--ok",
  stopped: "--warn",
  failed: "--alarm",
};

function StartForm({ onStarted }: { onStarted: () => void }) {
  const [formulas, setFormulas] = useState<FormulaSummary[]>([]);
  const [formulaId, setFormulaId] = useState<number | null>(null);
  const [tick, setTick] = useState("0.5");
  const [stepSeconds, setStepSeconds] = useState("14");
  const [source, setSource] = useState<"auto" | "file" | "synthetic">("auto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    listFormulas()
      .then((v) => {
        if (!alive) return;
        setFormulas(v);
        const preferred = v.find((f) => f.id === 15) ?? v[0];
        if (preferred) setFormulaId(preferred.id);
      })
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, []);

  const submit = async () => {
    if (formulaId == null) return;
    setBusy(true);
    setError(null);
    try {
      await simStart({
        formula_id: formulaId,
        tick_seconds: Number(tick) || 0.5,
        step_seconds: stepSeconds ? Number(stepSeconds) : null,
        source,
      });
      onStarted();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Запуск прогона" note="стадии идут по очереди, датчики опрашиваются каждый тик">
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
        <label className="field w-28">
          <span className="field-label">Стадия, с</span>
          <input className="input input--num" type="number" min="1" step="1" value={stepSeconds} onChange={(e) => setStepSeconds(e.target.value)} />
        </label>
        <label className="field w-28">
          <span className="field-label">Тик, с</span>
          <input className="input input--num" type="number" min="0.05" max="60" step="0.05" value={tick} onChange={(e) => setTick(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Источник данных</span>
          <select className="select" value={source} onChange={(e) => setSource(e.target.value as typeof source)}>
            <option value="auto">авто</option>
            <option value="file">файл CSV</option>
            <option value="synthetic">синтетика</option>
          </select>
        </label>
        <button className="btn btn--primary" onClick={submit} disabled={busy || formulaId == null}>
          {busy ? "Запускаю…" : "Запустить симуляцию"}
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

function ReferenceView({ formulaId }: { formulaId: number | null }) {
  const [steps, setSteps] = useState<ReferenceStep[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (formulaId == null) return;
    let alive = true;
    setSteps(null);
    simGetReference(formulaId)
      .then((v) => alive && setSteps(v.steps))
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, [formulaId]);

  if (formulaId == null) return null;
  if (error) return <Notice tone="--warn">Эталоны: {error}</Notice>;
  if (!steps) return <Spinner label="Загружаю эталонные полосы…" />;

  const rows = steps.flatMap((s) =>
    s.sensors.map((sn) => ({ step: s.step, key: s.step_key, sn })),
  );
  if (!rows.length) return <Empty>Эталонных партий для этой формулы пока нет — они появятся после первого прогона.</Empty>;

  return (
    <TableScroll>
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Стадия</th>
            <th scope="col">Датчик</th>
            <th scope="col">Параметр</th>
            <th scope="col" data-num>Эталон: начало</th>
            <th scope="col" data-num>Эталон: конец</th>
            <th scope="col">Полоса (нач. → кон.)</th>
            <th scope="col" data-num>Партий</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ step, sn }) => (
            <tr key={`${step}-${sn.tag}`}>
              <td className="num">{step}</td>
              <td><span className="tagplate">{sn.tag}</span></td>
              <td>
                {sn.parameter ?? "—"}
                {sn.unit ? <span className="text-steel-500">, {sn.unit}</span> : null}
              </td>
              <td data-num>{fmtNum(sn.start_mean)}</td>
              <td data-num>{fmtNum(sn.end_mean)}</td>
              <td className="num text-xs text-steel-600">
                {sn.band_start?.min ?? "—"}…{sn.band_start?.max ?? "—"} →{" "}
                {sn.band_end?.min ?? "—"}…{sn.band_end?.max ?? "—"}
              </td>
              <td data-num>{sn.n_batches ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}

export default function Simulation() {
  const [formulaFilter, setFormulaFilter] = useState<number | null>(null);
  const { data: status, error: statusError, refresh } = usePoll(() => simStatus(), 1000, true);
  const [runs, setRuns] = useState<SimRunSummary[] | null>(null);
  const [stopError, setStopError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  const loadRuns = () => simRuns().then(setRuns).catch(() => {});
  useEffect(() => {
    loadRuns();
    const t = setInterval(loadRuns, 5000);
    return () => clearInterval(t);
  }, []);

  const stop = async () => {
    setStopping(true);
    setStopError(null);
    try {
      await simStop();
      refresh();
      loadRuns();
    } catch (e) {
      setStopError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setStopping(false);
    }
  };

  const running = status?.running ?? false;
  const alerts = status?.recent_alerts ?? [];
  const progress =
    running && status?.duration_s
      ? Math.min(100, (status.elapsed_s / status.duration_s) * 100)
      : null;

  return (
    <>
      <PageHead
        kicker="Проверка"
        title="Симуляция стадий"
        lead="Прогон формулы на реальных (файл CSV) или синтетических показаниях: сверка с эталонными полосами и сигналы оператору. Одновременно идёт только один прогон."
      />

      {statusError && (
        <div className="mb-4">
          <Notice tone="--alarm">{statusError}</Notice>
        </div>
      )}
      {stopError && (
        <div className="mb-4">
          <Notice tone="--alarm">{stopError}</Notice>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="min-w-0 space-y-4">
          {/* живой прогон */}
          <Panel
            title="Текущий прогон"
            actions={
              status && (
                <>
                  <Chip tone={running ? "--reagent" : "--ok"} lamp={running}>
                    {running
                      ? `идёт · run №${status.run_id ?? "—"}`
                      : status.status === "failed"
                        ? "сбой"
                        : status.run_id
                          ? `${status.status ?? "остановлен"} · run №${status.run_id}`
                          : "не запущен"}
                  </Chip>
                  {running && (
                    <button className="btn btn--danger btn--sm" onClick={stop} disabled={stopping}>
                      {stopping ? "Останавливаю…" : "Остановить"}
                    </button>
                  )}
                </>
              )
            }
          >
            {!status ? (
              <Spinner label="Опрашиваю сервер…" />
            ) : status.run_id == null && !running ? (
              <Empty>Прогонов ещё не было — запустите первый формой справа.</Empty>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <StatBlock label="Стадия" value={status.step ?? "—"} />
                  <StatBlock
                    label="Время стадии"
                    value={fmtNum(status.elapsed_s, 1)}
                    unit={status.duration_s ? `/ ${fmtNum(status.duration_s, 0)} с` : "с"}
                  />
                  <StatBlock label="Показаний" value={status.readings} />
                  <StatBlock label="Сигналов" value={status.alerts} tone={status.alerts ? "--warn" : "--ok"} />
                </div>
                {progress != null && (
                  <div className="gauge mt-3">
                    <div className="gauge-fill" style={{ width: `${progress}%` }} />
                  </div>
                )}
              </>
            )}

            {alerts.length > 0 && (
              <div className="mt-4 space-y-2 border-t border-steel-200 pt-3">
                <p className="text-[11px] font-medium uppercase tracking-wide text-steel-500">
                  Последние сигналы
                </p>
                {alerts.slice().reverse().map((a, i) => (
                  <div
                    key={`${a.at}-${i}`}
                    className={`notice notice${a.status === "ok" ? "--ok" : "--warn"} flex flex-wrap items-baseline gap-x-2 gap-y-0.5`}
                  >
                    <span className="tagplate">{a.tag}</span>
                    <span className="text-sm text-steel-800">{a.message}</span>
                    <span className="num ml-auto text-xs text-steel-500">
                      стадия {a.step} · {fmtDateTime(a.at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          {/* эталонные полосы */}
          <Panel
            title="Эталонные полосы"
            note="средние по эталонным партиям + допуск"
            actions={
              <label className="flex items-center gap-2 text-sm text-steel-600">
                формула
                <select
                  className="select h-9"
                  value={formulaFilter ?? ""}
                  onChange={(e) => setFormulaFilter(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">не выбрана</option>
                  {(runs ? [...new Set(runs.map((r) => r.formula_id))] : []).map((id) => (
                    <option key={id} value={id}>№{id}</option>
                  ))}
                </select>
              </label>
            }
          >
            <ReferenceView formulaId={formulaFilter} />
          </Panel>
        </div>

        <div className="space-y-4">
          <StartForm
            onStarted={() => {
              refresh();
              loadRuns();
            }}
          />

          <Panel title="Журнал прогонов" bodyClassName="p-0">
            {!runs?.length ? (
              <div className="panel-body">
                <Empty>Пусто.</Empty>
              </div>
            ) : (
              <TableScroll>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Run</th>
                      <th scope="col">Формула</th>
                      <th scope="col">Статус</th>
                      <th scope="col">Старт</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.run_id}>
                        <td className="num">{r.run_id}</td>
                        <td className="num">№{r.formula_id}</td>
                        <td>
                          <Chip tone={STATUS_TONE[r.status] ?? ""}>{r.status}</Chip>
                        </td>
                        <td className="text-steel-600">{fmtDateTime(r.started_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScroll>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
