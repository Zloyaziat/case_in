import { Link } from "react-router";

import { Panel } from "~/components/ui";

export function meta() {
  return [{ title: "404 — страница не найдена" }];
}

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Panel className="max-w-md text-center" bodyClassName="panel-body py-10">
        <p className="readout text-5xl text-steel-300">404</p>
        <h1 className="mt-3 text-lg font-semibold text-steel-800">Такой страницы нет</h1>
        <p className="mt-1 text-sm text-steel-600">
          Возможно, раздел переименован или ссылка устарела.
        </p>
        <Link to="/" className="btn btn--primary mt-5">
          Вернуться на пульт
        </Link>
      </Panel>
    </div>
  );
}
