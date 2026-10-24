import { useEffect, useState } from "react";
import { Link } from "react-router";

import { Chip, Notice, Panel, PageHead, Spinner, StatBlock } from "~/components/ui";
import {
  type BatchSummary,
  type Sensor,
  ApiError,
  listBatches,
  listFormulas,
  listSensors,
  simStatus,
  type SimStatus,
  type FormulaSummary,
} from "~/lib/api";
import { fmtDateTime, fmtDict, phaseLabel, phaseTone } from "~/lib/format";

export function meta() {
  return [
    { title: "Пульт — малотоннажная химия" },
    {
      name: "description",
      content:
        "Операторский пульт: партии, показания датчиков, формулы и симуляция стадий малотоннажного производства.",
    },
  ];
}

/**
 * Трубопровод стадии: текущая партия как цепочка реакторов на мнемосхеме.
 * Заполненный сосуд — шаг пройден, пульсирующий — идёт сейчас.
 */
function StepPipeline({ batch }: { batch: BatchSummary | null }) {
  if (!batch) return null;
  // без live-статуса знаем только текущий шаг; рисуем минимум — 4 сосуда-маркера
  const total = Math.max(batch.current_step ?? 1, 1);
  const vessels = Array.from({ length: Math.min(Math.max(total, 3), 8) }, (_, i) => i + 1);
  return (
    <div className="flex items-end gap-0" role="img" aria-label="Ход стадии партии">
      {vessels.map((n, i) => {
        const done = batch.current_step != null && n < batch.current_step;
        const active = n === batch.current_step;
        return (
          <div key={n} className="flex items-end">
            {i > 0 && (
              <div
                className={`mb-3 h-px w-6 sm:w-9 ${done || active ? "bg-reagent-500" : "bg-steel-300"}`}
                aria-hidden="true"
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <svg width="34" height="44" viewBox="0 0 34 44" aria-hidden="true">
                <path
                  d="M7 6h20v14a10 10 0 0 1-20 0Z"
                  fill="none"
                  stroke={active ? "var(--color-reagent-600)" : "var(--color-steel-400)"}
                  strokeWidth="1.6"
                />
                {(done || active) && (
                  <path
                    d="M8.6 22a8.4 8.4 0 0 0 16.8 0Z"
                    fill={done ? "var(--color-lamp-ok)" : "var(--color-reagent-500)"}
                    opacity={done ? 0.85 : 0.6}
                  >
                    {active && <animate attributeName="opacity" values="0.35;0.75;0.35" dur="2s" repeatCount="indefinite" />}
                  </path>
                )}
                <path d="M4 42h26" stroke="var(--color-steel-300)" strokeWidth="1.6" />
              </svg>
              <span className="font-mono text-[11px] text-steel-500">{n}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const [batches, setBatches] = useState<BatchSummary[] | null>(null);
  const [sensors, setSensors] = useState<Sensor[] | null>(null);
  const [formulas, setFormulas] = useState<FormulaSummary[] | null>(null);
  const [sim, setSim] = useState<SimStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [b, s, f] = await Promise.all([
          listBatches().catch(() => []),
          listSensors().catch(() => []),
          listFormulas().catch(() => []),
        ]);
        if (!alive) return;
        setBatches(b);
        setSensors(s);
        setFormulas(f);
      } catch (e) {
        if (alive) setError(e instanceof ApiError ? e.message : String(e));
      }
    };
    load();
    // статус симуляции — отдельно, он живёт в памяти бэкенда и может быть недоступен
    simStatus()
      .then((v) => alive && setSim(v))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (error && !batches) {
    return (
      <>
        <PageHead kicker="Главная" title="Пульт оператора" />
        <Notice tone="--alarm">{error}</Notice>
      </>
    );
  }
  if (!batches || !sensors || !formulas) {
    return (
      <>
        <PageHead kicker="Главная" title="Пульт оператора" />
        <Spinner label="Опрашиваю сервер…" />
      </>
    );
  }

  const active = batches.find((b) => b.status === "running") ?? null;
  const finished = batches.filter((b) => b.status === "finished");
  const references = batches.filter((b) => b.is_reference);

  return (
    <>
      <PageHead
        kicker="Главная"
        title="Пульт оператора"
        lead="Партии, показания датчиков и формулы малотоннажного производства в одном окне."
        aside={
          <Link to="/batches" className="btn btn--primary">
            Вести партию
          </Link>
        }
      />

      {/* первый экран: текущая партия либо явный призыв её создать */}
      <Panel
        title={active ? `Партия №${active.id} — идёт` : "Сейчас партий в работе нет"}
        note={active ? `формула №${active.formula_id}` : undefined}
        actions={
          active ? (
            <Link to={`/batches/${active.id}`} className="btn btn--sm">
              Открыть партию
            </Link>
          ) : (
            <Link to="/batches" className="btn btn--sm">
              Создать и запустить
            </Link>
          )
        }
        className="mb-4"
      >
        {active ? (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatBlock label="Статус" value={
                <Chip tone={phaseTone(active.phase)} lamp>
                  {phaseLabel(active.phase)}
                </Chip>
              } />
              <StatBlock label="Текущий шаг" value={active.current_step ?? "—"} />
              <StatBlock label="Старт" value={
                <span className="text-lg">{fmtDateTime(active.started_at)}</span>
              } />
              <StatBlock label="Сырьё" value={
                <span className="text-sm font-normal">{fmtDict(active.v_in)}</span>
              } />
            </div>
            <StepPipeline batch={active} />
          </div>
        ) : (
          <p className="text-sm text-steel-600">
            Выберите формулу, задайте сырьё и запустите приём показаний — пульт покажет ход
            стадии и рекомендации по эталонным партиям.{" "}
            <Link to="/batches" className="link">Начать партию</Link>
          </p>
        )}
      </Panel>

      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="Установка" note="по данным БД">
          <div className="grid grid-cols-2 gap-4">
            <StatBlock label="Датчиков" value={sensors.length} />
            <StatBlock label="Формул" value={formulas.length} />
          </div>
          <div className="mt-3 flex gap-2">
            <Link to="/sensors" className="btn btn--sm">Датчики</Link>
            <Link to="/formulas" className="btn btn--sm">Формулы</Link>
          </div>
        </Panel>

        <Panel title="Партии" note={`последние ${Math.min(batches.length, 100)}`}>
          <div className="grid grid-cols-3 gap-4">
            <StatBlock label="Завершено" value={finished.length} tone="--ok" />
            <StatBlock label="Эталонов" value={references.length} />
            <StatBlock label="В работе" value={batches.filter((b) => b.status === "running").length} />
          </div>
          <div className="mt-3">
            <Link to="/batches" className="btn btn--sm">Журнал партий</Link>
          </div>
        </Panel>

        <Panel title="Симуляция стадий">
          {sim ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <StatBlock
                  label="Состояние"
                  value={
                    <Chip tone={sim.running ? "--reagent" : "--ok"} lamp={sim.running}>
                      {sim.running ? `идёт, стадия ${sim.step ?? "—"}` : sim.status ?? "остановлена"}
                    </Chip>
                  }
                />
                <StatBlock label="Сигналов" value={sim.alerts} tone={sim.alerts ? "--warn" : undefined} />
              </div>
              {sim.recent_alerts.length > 0 && (
                <p className="mt-2 text-sm text-steel-600">{sim.recent_alerts[sim.recent_alerts.length - 1].message}</p>
              )}
            </>
          ) : (
            <p className="text-sm text-steel-500">
              Сервер симуляции не отвечает или прогонов ещё не было.
            </p>
          )}
          <div className="mt-3">
            <Link to="/simulation" className="btn btn--sm">Открыть симуляцию</Link>
          </div>
        </Panel>
      </div>

      {error && (
        <div className="mt-4">
          <Notice tone="--warn">{error}</Notice>
        </div>
      )}
    </>
  );
}
