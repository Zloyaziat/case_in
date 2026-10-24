import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { Empty, Notice, PageHead, Panel, TableScroll } from "~/components/ui";
import {
  ApiError,
  createFormula,
  listFormulas,
  listSensors,
  type FormulaSummary,
  type Sensor,
} from "~/lib/api";

export function meta() {
  return [
    { title: "Приёмка формул — пульт оператора" },
    {
      name: "description",
      content: "Проверка и загрузка технологических формул в базу: локальная валидация диапазонов датчиков и отправка на сервер.",
    },
  ];
}

const PHASES = ["pre", "during", "post"] as const;

type FileFormula = {
  name: string;
  version: number;
  steps: {
    step: number;
    step_key: string;
    step_value: string;
    in_data?: Record<string, number>;
    out_data?: Record<string, number>;
    constant?: Record<string, number>;
    amount_time?: number;
    dict_PLC_id?: Record<string, Record<string, { min?: number; max?: number }>>;
  }[];
};

type LogLine = { text: string; tone: "ok" | "err" | "warn" | "" };

/** Локальная проверка — зеркало серверных правил (app/routers/formulas.py). */
function validate(formulas: FileFormula[], sensors: Sensor[]): string[] {
  const known = new Map(sensors.map((s) => [s.tag, s]));
  const problems: string[] = [];
  const seen = new Set<string>();

  formulas.forEach((f, fi) => {
    const where = `[${fi + 1}] ${f.name} v${f.version}`;
    const nv = `${f.name}#${f.version}`;
    if (seen.has(nv)) problems.push(`${where}: дубль name+version в файле`);
    seen.add(nv);

    const steps = f.steps || [];
    if (!steps.length) problems.push(`${where}: нет шагов`);
    const nums = steps.map((s) => s.step);
    const keys = steps.map((s) => s.step_key);
    if (new Set(nums).size !== nums.length) problems.push(`${where}: номера шагов не уникальны`);
    if (new Set(keys).size !== keys.length) problems.push(`${where}: step_key не уникальны`);

    steps.forEach((s) => {
      const at = `${where}, шаг ${s.step}`;
      if (!s.step_key) problems.push(`${at}: пустая формула (step_key)`);
      if (!s.step_value) problems.push(`${at}: пустой результат (step_value)`);
      for (const [k, v] of Object.entries(s.in_data || {}))
        if (!(v > 0)) problems.push(`${at}: in_data['${k}'] (кг) должна быть > 0`);
      for (const [k, v] of Object.entries(s.out_data || {}))
        if (!(v >= 0)) problems.push(`${at}: out_data['${k}'] (кг) < 0`);
      for (const [k, v] of Object.entries(s.constant || {})) {
        if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(k))
          problems.push(`${at}: ключ константы '${k}' должен быть латиницей`);
        if (!(v > 0)) problems.push(`${at}: constant['${k}'] должна быть > 0`);
      }
      if (s.amount_time != null && !(s.amount_time > 0))
        problems.push(`${at}: amount_time (минуты) должен быть > 0`);

      for (const [tag, limits] of Object.entries(s.dict_PLC_id || {})) {
        const sensor = known.get(tag);
        if (sensors.length && !sensor) problems.push(`${at}: датчика '${tag}' нет в БД`);
        for (const ph of PHASES) {
          const r = limits[ph];
          if (!r) continue;
          if (r.min == null && r.max == null) problems.push(`${at}, ${tag}/${ph}: нужен min или max`);
          if (r.min != null && r.max != null && r.min > r.max)
            problems.push(`${at}, ${tag}/${ph}: min > max`);
          if (sensor?.valid_min != null && r.min != null && r.min < sensor.valid_min)
            problems.push(`${at}, ${tag}/${ph}: min ${r.min} < valid_min ${sensor.valid_min}`);
          if (sensor?.valid_max != null && r.max != null && r.max > sensor.valid_max)
            problems.push(`${at}, ${tag}/${ph}: max ${r.max} > valid_max ${sensor.valid_max}`);
        }
      }
    });
  });
  return problems;
}

function uniqueTags(f: FileFormula): Set<string> {
  const tags = new Set<string>();
  for (const s of f.steps || [])
    for (const t of Object.keys(s.dict_PLC_id || {})) tags.add(t);
  return tags;
}

export default function FormulasImport() {
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [formulas, setFormulas] = useState<FileFormula[] | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [dbFormulas, setDbFormulas] = useState<FormulaSummary[] | null>(null);
  const [log, setLog] = useState<LogLine[]>([]);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const pushLog = (text: string, tone: LogLine["tone"] = "") =>
    setLog((l) => [...l, { text, tone }]);

  useEffect(() => {
    listSensors()
      .then((v) => {
        setSensors(v);
        pushLog(`Датчиков в БД: ${v.length}`, v.length ? "ok" : "warn");
        if (!v.length) pushLog("Датчиков нет: выполните sql/seed_demo_sensors.sql", "warn");
      })
      .catch((e) => pushLog(`GET /api/sensors: ${(e as Error).message}`, "err"));
    listFormulas()
      .then(setDbFormulas)
      .catch(() => {});
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log]);

  const setFromFile = (json: unknown, source: string) => {
    const list = Array.isArray(json)
      ? json
      : (json as { formulas?: unknown })?.formulas;
    if (!Array.isArray(list)) {
      pushLog('Ожидался массив формул или {"formulas": [...]}', "err");
      return;
    }
    setFormulas(list as FileFormula[]);
    setSourceName(source);
    pushLog(`Загружено формул: ${list.length} (${source})`, "ok");
  };

  const loadDemo = async () => {
    try {
      const res = await fetch("/formulas.json");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setFromFile(await res.json(), "демо-файл");
    } catch (e) {
      pushLog(`Не нашёл демо-файл: ${(e as Error).message}`, "err");
    }
  };

  const loadFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        setFromFile(JSON.parse(String(reader.result)), file.name);
      } catch (e) {
        pushLog(`Невалидный JSON: ${(e as Error).message}`, "err");
      }
    };
    reader.readAsText(file);
  };

  const check = (): boolean => {
    if (!formulas?.length) {
      pushLog("Сначала загрузите формулы.", "warn");
      return false;
    }
    const problems = validate(formulas, sensors);
    if (problems.length) {
      problems.forEach((p) => pushLog(p, "err"));
      pushLog(`Проблем: ${problems.length}`, "err");
      return false;
    }
    pushLog("Локальная проверка пройдена.", "ok");
    return true;
  };

  const send = async () => {
    if (!formulas || !check()) return;
    setBusy(true);
    for (const f of formulas) {
      const label = `${f.name} v${f.version}`;
      try {
        const r = await createFormula(f);
        pushLog(`${label}: сохранено, id=${r.id}, шагов ${r.steps_count}`, "ok");
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) pushLog(`${label}: уже есть в БД (409)`, "warn");
        else pushLog(`${label}: ${e instanceof Error ? e.message : String(e)}`, "err");
      }
    }
    setBusy(false);
    listFormulas().then(setDbFormulas).catch(() => {});
  };

  return (
    <>
      <PageHead
        kicker="Технология"
        title="Приёмка формул"
        lead="Проверьте файл формул локально и отправьте его в базу. Диапазоны датчиков сверяются с физическими пределами из таблицы sensors."
        aside={
          <Link to="/formulas" className="btn">
            К списку формул
          </Link>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="min-w-0 space-y-4">
          <Panel title="1. Файл формул">
            <div className="flex flex-wrap gap-2">
              <button className="btn btn--primary" onClick={loadDemo}>
                Взять демо-файл
              </button>
              <button className="btn" onClick={() => fileRef.current?.click()}>
                Выбрать JSON…
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".json,application/json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) loadFile(f);
                  e.target.value = "";
                }}
              />
            </div>

            {formulas ? (
              <div className="mt-3">
                <p className="mb-2 text-sm text-steel-600">
                  Источник: <span className="font-medium">{sourceName}</span>
                </p>
                <TableScroll>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">#</th>
                        <th scope="col">Название</th>
                        <th scope="col" data-num>Версия</th>
                        <th scope="col" data-num>Шагов</th>
                        <th scope="col">Датчики</th>
                      </tr>
                    </thead>
                    <tbody>
                      {formulas.map((f, i) => (
                        <tr key={i}>
                          <td className="num">{i + 1}</td>
                          <td>{f.name}</td>
                          <td data-num>{f.version}</td>
                          <td data-num>{(f.steps || []).length}</td>
                          <td>
                            <span className="flex flex-wrap gap-1">
                              {[...uniqueTags(f)].map((t) => (
                                <span key={t} className="tagplate">{t}</span>
                              ))}
                              {!uniqueTags(f).size && <span className="text-steel-400">—</span>}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableScroll>
              </div>
            ) : (
              <div className="mt-3">
                <Empty>Файл не загружен. Формат — как в демо: {"{ formulas: [ { name, version, steps: […] } ] }"}.</Empty>
              </div>
            )}
          </Panel>

          <Panel title="2. Проверка и отправка">
            <div className="flex flex-wrap gap-2">
              <button className="btn" onClick={check} disabled={!formulas}>
                Проверить локально
              </button>
              <button className="btn btn--primary" onClick={send} disabled={!formulas || busy}>
                {busy ? "Отправляю…" : "Отправить в БД"}
              </button>
            </div>
            <p className="mt-2 text-xs text-steel-500">
              Отправка идёт по одной формуле: POST /api/formulas. Дубликат name+version сервер
              отклонит кодом 409.
            </p>
          </Panel>

          <Panel title="3. Журнал" bodyClassName="p-0">
            <div
              ref={logRef}
              className="h-56 overflow-y-auto bg-steel-900 p-3 font-mono text-xs leading-relaxed text-steel-200"
              aria-live="polite"
            >
              {log.length === 0 && <span className="text-steel-500">пусто</span>}
              {log.map((l, i) => (
                <div
                  key={i}
                  className={
                    l.tone === "ok"
                      ? "text-[#7fce9f]"
                      : l.tone === "err"
                        ? "text-[#e5938a]"
                        : l.tone === "warn"
                          ? "text-[#e3bf7e]"
                          : undefined
                  }
                >
                  {l.text}
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Датчики в БД" note={`${sensors.length} шт.`}>
            {sensors.length ? (
              <ul className="space-y-1.5">
                {sensors.map((s) => (
                  <li key={s.id} className="flex items-baseline gap-2 text-sm">
                    <span className="tagplate">{s.tag}</span>
                    <span className="text-steel-600">{s.parameter}</span>
                    <span className="num ml-auto text-xs text-steel-500">
                      {s.valid_min ?? "—"}…{s.valid_max ?? "—"} {s.unit}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>Нет данных. Проверьте, что бэкенд запущен и дамп БД загружен.</Empty>
            )}
          </Panel>

          <Panel title="Формулы в БД">
            {dbFormulas?.length ? (
              <ul className="space-y-1 text-sm">
                {dbFormulas.map((f) => (
                  <li key={f.id} className="flex items-baseline gap-2">
                    <span className="num text-xs text-steel-400">№{f.id}</span>
                    <Link to="/formulas" className="link">{f.name}</Link>
                    <span className="ml-auto font-mono text-xs text-steel-500">v{f.version}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>В базе пока нет формул.</Empty>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
