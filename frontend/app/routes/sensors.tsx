import { useEffect, useMemo, useState } from "react";

import { Empty, Notice, PageHead, Panel, Spinner, TableScroll } from "~/components/ui";
import { listSensors, type Sensor } from "~/lib/api";
import { fmtNum } from "~/lib/format";

export function meta() {
  return [
    { title: "Датчики — пульт оператора" },
    {
      name: "description",
      content: "Паспорта приборов установки: теги, измеряемые параметры, единицы и физические пределы датчиков.",
    },
  ];
}

/** Значок параметра: первая буква тега по ISA-5.1 (T — температура, P — давление…). */
function TagGlyph({ tag }: { tag: string }) {
  const letter = (tag.match(/[A-Za-z]/) ?? ["?"])[0].toUpperCase();
  return (
    <span
      className="inline-flex h-7 w-7 flex-none items-center justify-center rounded-full border border-steel-300 bg-steel-50 font-mono text-xs font-semibold text-steel-700"
      aria-hidden="true"
    >
      {letter}
    </span>
  );
}

export default function Sensors() {
  const [sensors, setSensors] = useState<Sensor[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    listSensors()
      .then((v) => alive && setSensors(v))
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, []);

  const filtered = useMemo(() => {
    if (!sensors) return [];
    const q = query.trim().toLowerCase();
    if (!q) return sensors;
    return sensors.filter((s) =>
      [s.tag, s.parameter, s.unit, s.instrument].some((v) => v?.toLowerCase().includes(q)),
    );
  }, [sensors, query]);

  const byParameter = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of sensors ?? []) m.set(s.parameter, (m.get(s.parameter) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [sensors]);

  return (
    <>
      <PageHead
        kicker="Установка"
        title="Датчики"
        lead="Паспорта приборов из базы: тег — то, что приходит с PLC, физические пределы — за их рамками показание считается сбоем датчика."
        aside={
          sensors && (
            <span className="chip chip--reagent">
              <span className="lamp lamp--reagent" /> {sensors.length} в базе
            </span>
          )
        }
      />

      {error && (
        <div className="mb-4">
          <Notice tone="--alarm">{error}</Notice>
        </div>
      )}

      {!sensors && !error && <Spinner label="Загружаю датчики…" />}

      {sensors && (
        <>
          {byParameter.length > 1 && (
            <div className="mb-4 flex flex-wrap gap-2" aria-label="Состав по параметрам">
              {byParameter.map(([p, n]) => (
                <span key={p} className="chip">
                  {p} <span className="num text-steel-500">{n}</span>
                </span>
              ))}
            </div>
          )}

          <Panel
            title="Приборы"
            actions={
              <label className="flex items-center gap-2">
                <span className="sr-only">Поиск по датчикам</span>
                <input
                  type="search"
                  className="input h-9 w-44 sm:w-56"
                  placeholder="тег, параметр, прибор…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
            }
            bodyClassName="p-0"
          >
            {filtered.length === 0 ? (
              <div className="panel-body">
                <Empty>Ничего не найдено{query ? ` по запросу «${query}»` : ""}.</Empty>
              </div>
            ) : (
              <TableScroll>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Тег</th>
                      <th scope="col">Параметр</th>
                      <th scope="col">Ед.</th>
                      <th scope="col">Прибор</th>
                      <th scope="col" data-num>Предел min</th>
                      <th scope="col" data-num>Предел max</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <span className="flex items-center gap-2">
                            <TagGlyph tag={s.tag} />
                            <span className="tagplate">{s.tag}</span>
                          </span>
                        </td>
                        <td>{s.parameter}</td>
                        <td className="num">{s.unit}</td>
                        <td className="text-steel-600">{s.instrument}</td>
                        <td data-num>{fmtNum(s.valid_min)}</td>
                        <td data-num>{fmtNum(s.valid_max)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScroll>
            )}
          </Panel>
        </>
      )}
    </>
  );
}
