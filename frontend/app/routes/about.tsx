import { Link } from "react-router";

import { Panel, PageHead } from "~/components/ui";

export function meta() {
  return [
    { title: "О системе — пульт оператора" },
    { name: "description", content: "Как устроен пульт оператора малотоннажного производства." },
  ];
}

export default function About() {
  return (
    <>
      <PageHead
        kicker="Справка"
        title="О системе"
        lead="Пульт оператора малотоннажного химического производства: приёмка формул, ведение партий по показаниям датчиков и симуляция стадий."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Как это работает">
          <ol className="list-inside list-decimal space-y-2 text-sm text-steel-700">
            <li>
              Технолог загружает <Link to="/formulas/import" className="link">формулу</Link>:
              стадии с уравнениями реакций, массами реагентов и допустимыми диапазонами
              датчиков (до стадии / во время / после).
            </li>
            <li>
              Оператор создаёт <Link to="/batches" className="link">партию</Link>: выбирает
              формулу, вводит массы сырья и запускает приём показаний.
            </li>
            <li>
              Пульт усредняет показания по окнам, сравнивает с эталонными партиями и
              выдаёт рекомендации: «Нужно повысить температуру до 39 °C на датчике F-TT-01!».
            </li>
            <li>
              В конце партии оператор фиксирует выход продукта и качество; удачную партию
              можно сделать эталонной — она пополнит базу сравнения.
            </li>
          </ol>
        </Panel>

        <Panel title="Разделы пульта">
          <ul className="space-y-2 text-sm text-steel-700">
            <li>
              <Link to="/" className="link font-medium">Пульт</Link> — сводка: текущая партия,
              установка, симуляция.
            </li>
            <li>
              <Link to="/sensors" className="link font-medium">Датчики</Link> — паспорта
              приборов: тег, параметр, единицы, физические пределы.
            </li>
            <li>
              <Link to="/formulas" className="link font-medium">Формулы</Link> — цепочки
              стадий и расчёт массы конечного продукта.
            </li>
            <li>
              <Link to="/batches" className="link font-medium">Партии</Link> — журнал партий,
              создание и ведение партии.
            </li>
            <li>
              <Link to="/simulation" className="link font-medium">Симуляция</Link> — прогон
              стадий на файловых или синтетических данных, сигналы оператору.
            </li>
          </ul>
        </Panel>

        <Panel title="Обозначения" className="lg:col-span-2">
          <div className="grid gap-4 text-sm text-steel-700 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="font-medium">Тег датчика</p>
              <p className="mt-1"><span className="tagplate">F-TT-01</span> — шильдик прибора;
                первая буква — измеряемая величина (T — температура, pH — кислотность).</p>
            </div>
            <div>
              <p className="font-medium">Окно усреднения</p>
              <p className="mt-1">Показания за короткое окно (по умолчанию 2 с) усредняются —
                так шум датчика не порождает ложных рекомендаций.</p>
            </div>
            <div>
              <p className="font-medium">Эталонная партия</p>
              <p className="mt-1">Партия с подтверждённым качеством; средние по эталонам —
                база сравнения для текущего хода стадии.</p>
            </div>
            <div>
              <p className="font-medium">Рекомендация</p>
              <p className="mt-1">Порог: |отклонение| &gt; max(k·σ эталона, допуск датчика).
                Превышен — пульт подсказывает, что изменить.</p>
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}
