import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";

import {
  Chip,
  Empty,
  Notice,
  PageHead,
  Panel,
  Spinner,
  TableScroll,
} from "~/components/ui";
import {
  ApiError,
  createBatch,
  getFormula,
  listBatches,
  listFormulas,
  startBatch,
  type BatchSummary,
  type FormulaSummary,
} from "~/lib/api";
import { fmtDateTime, fmtDict, fmtNum, phaseLabel, phaseTone } from "~/lib/format";

export function meta() {
  return [
    { title: "Партии — пульт оператора" },
    {
      name: "description",
      content:
        "Журнал партий малотоннажного производства: создание партии по формуле, ввод сырья, запуск приёма показаний и завершение с фиксацией качества.",
    },
  ];
}

const SPEEDS = [1, 5, 10, 30, 60];

/** Форма «выбрать формулу -> сырьё -> старт» (POST /api/batches + /start). */
function CreateBatchForm() {
  const navigate = useNavigate();
  const [formulas, setFormulas] = useState<FormulaSummary[]>([]);
  const [formulaId, setFormulaId] = useState<number | null>(null);
  const [vin, setVin] = useState<Record<string, number>>({});
  const [speed, setSpeed] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingVin, setLoadingVin] = useState(false);

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

  // поля сырья — по реагентам первой стадии выбранной формулы
  useEffect(() => {
    if (formulaId == null) return;
    let alive = true;
    setLoadingVin(true);
    getFormula(formulaId)
      .then((f) => {
        if (!alive) return;
        const first = f.steps[0];
        setVin(Object.fromEntries(Object.entries(first?.in_data ?? {})));
      })
      .catch((e) => alive && setError((e as Error).message))
      .finally(() => alive && setLoadingVin(false));
    return () => {
      alive = false;
    };
  }, [formulaId]);

  const submit = async () => {
    if (formulaId == null) return;
    setBusy(true);
    setError(null);
    try {
      const b = await createBatch(formulaId, vin);
      await startBatch(b.id, { speed });
      navigate(`/batches/${b.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
      setBusy(false);
    }
  };

  return (
    <Panel title="Новая партия" note="формула → сырьё → старт приёма показаний">
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

        {loadingVin && <Spinner label="Читаю состав сырья…" />}
        {!loadingVin &&
          Object.keys(vin).map((k) => (
            <label key={k} className="field w-28">
              <span className="field-label font-mono">{k}, кг</span>
              <input
                className="input input--num"
                type="number"
                min="0"
                step="any"
                value={vin[k]}
                onChange={(e) =>
                  setVin((v) => ({ ...v, [k]: e.target.value === "" ? NaN : Number(e.target.value) }))
                }
              />
            </label>
          ))}

        <div className="field">
          <span className="field-label">Ускорение времени</span>
          <div className="flex gap-1" role="group" aria-label="Ускорение времени">
            {SPEEDS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSpeed(s)}
                aria-pressed={speed === s}
                className={`btn btn--sm ${speed === s ? "btn--primary" : ""}`}
              >
                ×{s}
              </button>
            ))}
          </div>
        </div>

        <button
          className="btn btn--primary"
          onClick={submit}
          disabled={busy || formulaId == null || Object.values(vin).some((v) => !(v > 0))}
        >
          {busy ? "Запускаю…" : "Создать и запустить"}
        </button>
      </div>
      <p className="mt-2 text-xs text-steel-500">
        Показания берутся из файла opc_formula15.txt в папке data/ на сервере (имитация OPC).
        Ход партии откроется на отдельной странице.
      </p>
      {error && (
        <div className="mt-3">
          <Notice tone="--alarm">{error}</Notice>
        </div>
      )}
    </Panel>
  );
}

export default function Batches() {
  const [batches, setBatches] = useState<BatchSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyRunning, setOnlyRunning] = useState(false);
  const [onlyReference, setOnlyReference] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      listBatches()
        .then((v) => {
          if (alive) {
            setBatches(v);
            setError(null);
          }
        })
        .catch((e) => alive && setError((e as Error).message));
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const filtered = useMemo(() => {
    let list = batches ?? [];
    if (onlyRunning) list = list.filter((b) => b.status === "running");
    if (onlyReference) list = list.filter((b) => b.is_reference);
    return list;
  }, [batches, onlyRunning, onlyReference]);

  return (
    <>
      <PageHead
        kicker="Производство"
        title="Партии"
        lead="Журнал партий: какая формула, сколько сырья, чем закончилась. Активная партия открывается в отдельном окне ведения."
      />

      <div className="mb-4">
        <CreateBatchForm />
      </div>

      {error && (
        <div className="mb-4">
          <Notice tone="--alarm">{error}</Notice>
        </div>
      )}

      <Panel
        title="Журнал"
        note={batches ? `${filtered.length} из ${batches.length}` : undefined}
        actions={
          <div className="flex gap-3 text-sm">
            <label className="flex items-center gap-1.5 text-steel-600">
              <input type="checkbox" checked={onlyRunning} onChange={(e) => setOnlyRunning(e.target.checked)} />
              только в работе
            </label>
            <label className="flex items-center gap-1.5 text-steel-600">
              <input type="checkbox" checked={onlyReference} onChange={(e) => setOnlyReference(e.target.checked)} />
              только эталонные
            </label>
          </div>
        }
        bodyClassName="p-0"
      >
        {!batches && !error ? (
          <div className="panel-body">
            <Spinner label="Загружаю журнал…" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="panel-body">
            <Empty>Партий пока нет — создайте первую формой выше.</Empty>
          </div>
        ) : (
          <TableScroll>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">№</th>
                  <th scope="col">Формула</th>
                  <th scope="col">Статус</th>
                  <th scope="col">Старт</th>
                  <th scope="col">Сырьё, кг</th>
                  <th scope="col" data-num>Выход</th>
                  <th scope="col" data-num>Качество</th>
                  <th scope="col"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((b) => (
                  <tr key={b.id}>
                    <td className="num">{b.id}</td>
                    <td className="num text-steel-600">№{b.formula_id}</td>
                    <td>
                      <span className="flex items-center gap-1.5">
                        <Chip tone={phaseTone(b.phase)} lamp={b.status === "running"}>
                          {phaseLabel(b.phase)}
                        </Chip>
                        {b.is_reference && <Chip tone="--ok">эталон</Chip>}
                      </span>
                    </td>
                    <td className="text-steel-600">{fmtDateTime(b.started_at)}</td>
                    <td className="text-steel-600">{fmtDict(b.v_in)}</td>
                    <td data-num>{b.v_finish != null ? fmtNum(b.v_finish) : "—"}</td>
                    <td data-num>
                      {b.quality != null ? `${fmtNum(b.quality)} ${b.quality_unit ?? ""}` : "—"}
                    </td>
                    <td className="text-right">
                      <Link to={`/batches/${b.id}`} className="btn btn--sm">
                        Открыть
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
      </Panel>
    </>
  );
}
