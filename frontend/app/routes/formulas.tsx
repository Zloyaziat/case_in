import { useEffect, useState } from "react";
import { Link } from "react-router";

import {
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
  calculateFormula,
  getFormula,
  listFormulas,
  type CalcResult,
  type FormulaDetail,
  type FormulaSummary,
} from "~/lib/api";
import { chemText, fmtNum } from "~/lib/format";

export function meta() {
  return [
    { title: "Формулы — пульт оператора" },
    {
      name: "description",
      content:
        "Цепочки стадий малотоннажного производства: уравнения реакций, массы реагентов, диапазоны датчиков и расчёт выхода продукта.",
    },
  ];
}

function RangeCell({ r }: { r?: { min?: number | null; max?: number | null } | null }) {
  if (!r || (r.min == null && r.max == null)) return <span className="text-steel-400">—</span>;
  return (
    <span className="num">
      {r.min ?? "−∞"} … {r.max ?? "+∞"}
    </span>
  );
}

/** Карточка стадии формулы: уравнение, массы, датчики с диапазонами. */
function StepCard({ step }: { step: FormulaDetail["steps"][number] }) {
  const entries = Object.entries(step.sensors);
  return (
    <article className="panel">
      <div className="panel-head">
        <span className="chip chip--reagent">Стадия {step.step}</span>
        <h3 className="panel-title font-mono text-[13px] font-medium">{chemText(step.step_key)}</h3>
        {step.amount_time_min != null && (
          <span className="panel-note ml-auto">план: {fmtNum(step.amount_time_min, 0)} мин</span>
        )}
      </div>
      <div className="grid gap-4 p-3.5 md:grid-cols-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-steel-500">До реакции, кг</p>
          <ul className="mt-1 space-y-0.5 text-sm">
            {Object.entries(step.in_data).map(([k, v]) => (
              <li key={k} className="flex justify-between gap-3">
                <span className="font-mono">{chemText(k)}</span>
                <span className="num text-steel-700">{fmtNum(v)}</span>
              </li>
            ))}
            {!Object.keys(step.in_data).length && <li className="text-steel-400">—</li>}
          </ul>
        </div>
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-steel-500">После, кг</p>
          <ul className="mt-1 space-y-0.5 text-sm">
            {Object.entries(step.out_data).map(([k, v]) => (
              <li key={k} className="flex justify-between gap-3">
                <span className="font-mono">{chemText(k)}</span>
                <span className="num text-steel-700">{fmtNum(v)}</span>
              </li>
            ))}
            {!Object.keys(step.out_data).length && <li className="text-steel-400">—</li>}
          </ul>
        </div>
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-steel-500">Константы</p>
          <ul className="mt-1 space-y-0.5 text-sm">
            {Object.entries(step.constant).map(([k, v]) => (
              <li key={k} className="flex justify-between gap-3">
                <span className="font-mono">{k}</span>
                <span className="num text-steel-700">{fmtNum(v, 3)}</span>
              </li>
            ))}
            {!Object.keys(step.constant).length && <li className="text-steel-400">—</li>}
          </ul>
        </div>
      </div>
      {entries.length > 0 && (
        <TableScroll>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Датчик</th>
                <th scope="col">Параметр</th>
                <th scope="col">до стадии</th>
                <th scope="col">во время</th>
                <th scope="col">после</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([tag, s]) => (
                <tr key={tag}>
                  <td><span className="tagplate">{tag}</span></td>
                  <td>
                    {s.parameter}
                    {s.unit ? <span className="text-steel-500">, {s.unit}</span> : null}
                  </td>
                  <td><RangeCell r={s.limits.pre} /></td>
                  <td><RangeCell r={s.limits.during} /></td>
                  <td><RangeCell r={s.limits.post} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      )}
    </article>
  );
}

/** Форма расчёта массы конечного продукта (POST /api/formulas/{id}/calculate). */
function CalcForm({ formulaId }: { formulaId: number }) {
  const [spread, setSpread] = useState("0");
  const [tolerance, setTolerance] = useState("10");
  const [inputsRaw, setInputsRaw] = useState("");
  const [result, setResult] = useState<CalcResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      let inputs: Record<string, number> | undefined;
      if (inputsRaw.trim()) {
        try {
          inputs = JSON.parse(inputsRaw);
        } catch {
          throw new Error("Массы реагентов: невалидный JSON. Пример: {\"C3H6O3\": 123}");
        }
      }
      const res = await calculateFormula(formulaId, {
        spread_pct: Number(spread) || 0,
        tolerance_pct: Number(tolerance) || 10,
        ...(inputs ? { inputs } : {}),
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Расчёт выхода продукта" note="массы в кг, по уравнениям стадий">
      <div className="flex flex-wrap items-end gap-3">
        <label className="field">
          <span className="field-label">Разброс констант, ±%</span>
          <input
            className="input input--num w-24"
            type="number" min="0" max="50" step="1"
            value={spread}
            onChange={(e) => setSpread(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">Допуск качества, %</span>
          <input
            className="input input--num w-24"
            type="number" min="1" max="100" step="1"
            value={tolerance}
            onChange={(e) => setTolerance(e.target.value)}
          />
        </label>
        <label className="field min-w-52 flex-1">
          <span className="field-label">Массы реагентов 1-й стадии, JSON (необязательно)</span>
          <input
            className="input font-mono"
            placeholder='{"C3H6O3": 123}'
            value={inputsRaw}
            onChange={(e) => setInputsRaw(e.target.value)}
          />
        </label>
        <button className="btn btn--primary" onClick={run} disabled={busy}>
          {busy ? "Считаю…" : "Рассчитать"}
        </button>
      </div>

      {error && (
        <div className="mt-3">
          <Notice tone="--alarm">{error}</Notice>
        </div>
      )}

      {result && (
        <div className="mt-4">
          <div className="grid grid-cols-2 gap-4 rounded-sm border border-steel-200 bg-steel-50 p-3.5 sm:grid-cols-4">
            <StatBlock
              label={result.final_product}
              value={fmtNum(result.final_mass_kg)}
              unit="кг"
            />
            <StatBlock label="Теоретически" value={fmtNum(result.final_theoretical_kg)} unit="кг" />
            <StatBlock label="Общий выход" value={fmtNum(result.total_yield_pct)} unit="%" />
            <StatBlock
              label="Качество"
              value={result.quality != null ? fmtNum(result.quality, 2) : "—"}
              tone={result.quality != null ? (result.quality > 0.7 ? "--ok" : "--warn") : undefined}
            />
          </div>
          {result.final_mass_range_kg && (
            <p className="mt-2 text-sm text-steel-600">
              Диапазон при ±{result.spread_pct}% к константам:{" "}
              <span className="num">
                {fmtNum(result.final_mass_range_kg[0])} … {fmtNum(result.final_mass_range_kg[1])} кг
              </span>
            </p>
          )}

          <TableScroll>
            <table className="data-table mt-3">
              <thead>
                <tr>
                  <th scope="col">Стадия</th>
                  <th scope="col">Лимитирует</th>
                  <th scope="col" data-num>Теор., кг</th>
                  <th scope="col" data-num>Коэфф.</th>
                  <th scope="col" data-num>Практ., кг</th>
                  <th scope="col" data-num>Ожидание</th>
                  <th scope="col" data-num>Откл., %</th>
                </tr>
              </thead>
              <tbody>
                {result.steps.map((s) => (
                  <tr key={s.step}>
                    <td className="font-mono text-xs">{chemText(s.equation)}</td>
                    <td className="font-mono">{chemText(s.limiting)}</td>
                    <td data-num>{fmtNum(s.theoretical_kg[s.product])}</td>
                    <td data-num>{fmtNum(s.factor, 3)}</td>
                    <td data-num>{fmtNum(s.practical_kg[s.product])}</td>
                    <td data-num>{s.expected_kg != null ? fmtNum(s.expected_kg) : "—"}</td>
                    <td data-num>
                      {s.deviation_pct != null ? (
                        <span className={Math.abs(s.deviation_pct) > 10 ? "text-lamp-warn" : ""}>
                          {fmtNum(s.deviation_pct)}
                        </span>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>

          {result.warnings.length > 0 && (
            <div className="mt-3 space-y-2">
              {result.warnings.map((w) => (
                <Notice key={w} tone="--warn">{w}</Notice>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-steel-500">{result.quality_basis}</p>
        </div>
      )}
    </Panel>
  );
}

export default function Formulas() {
  const [formulas, setFormulas] = useState<FormulaSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<FormulaDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    listFormulas()
      .then((v) => {
        if (!alive) return;
        setFormulas(v);
        // по умолчанию открываем формулу 15 (рабочая в дампе БД) либо первую
        const preferred = v.find((f) => f.id === 15) ?? v[0];
        if (preferred) setSelectedId(preferred.id);
      })
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    let alive = true;
    setDetail(null);
    getFormula(selectedId)
      .then((v) => alive && setDetail(v))
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, [selectedId]);

  return (
    <>
      <PageHead
        kicker="Технология"
        title="Формулы"
        lead="Цепочки стадий: уравнения реакций, массы реагентов, допустимые диапазоны датчиков и расчёт выхода продукта."
        aside={
          <Link to="/formulas/import" className="btn btn--primary">
            Приёмка формул
          </Link>
        }
      />

      {error && (
        <div className="mb-4">
          <Notice tone="--alarm">{error}</Notice>
        </div>
      )}

      {!formulas && !error && <Spinner label="Загружаю формулы…" />}

      {formulas && formulas.length === 0 && (
        <Panel>
          <Empty>
            В базе пока нет формул. Загрузите демонстрационную или свою на странице{" "}
            <Link to="/formulas/import" className="link">приёмки формул</Link>.
          </Empty>
        </Panel>
      )}

      {formulas && formulas.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
          <Panel title="В базе" bodyClassName="p-0">
            <ul className="divide-y divide-steel-100">
              {formulas.map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(f.id)}
                    aria-current={selectedId === f.id ? "true" : undefined}
                    className={`flex w-full items-baseline gap-2 px-3.5 py-2.5 text-left text-sm transition-colors hover:bg-steel-50 ${
                      selectedId === f.id ? "bg-reagent-50 hover:bg-reagent-50" : ""
                    }`}
                  >
                    <span className={`num text-xs ${selectedId === f.id ? "text-reagent-700" : "text-steel-400"}`}>
                      №{f.id}
                    </span>
                    <span className={selectedId === f.id ? "font-medium text-reagent-700" : "text-steel-800"}>
                      {f.name}
                    </span>
                    <span className="ml-auto font-mono text-xs text-steel-500">v{f.version}</span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>

          <div className="min-w-0 space-y-4">
            {!detail && selectedId != null && <Spinner label="Загружаю формулу…" />}
            {detail && (
              <>
                <div className="space-y-3">
                  {detail.steps.map((s) => (
                    <StepCard key={s.step} step={s} />
                  ))}
                </div>
                <CalcForm formulaId={detail.id} />
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
