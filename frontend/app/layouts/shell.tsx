import { NavLink, Outlet } from "react-router";

const NAV = [
  { to: "/", label: "Пульт", end: true },
  { to: "/sensors", label: "Датчики" },
  { to: "/formulas", label: "Формулы" },
  { to: "/batches", label: "Партии" },
  { to: "/simulation", label: "Симуляция" },
  { to: "/demo", label: "Демо" },
];

/** Логотип: капля реагента в ромбе — мотив, который повторяется на страницах. */
function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
      <path
        d="M13 1.5 24.5 13 13 24.5 1.5 13Z"
        fill="none"
        stroke="var(--color-reagent-500)"
        strokeWidth="1.6"
      />
      <path
        d="M13 6.5c2.6 3 4 5.2 4 7.2a4 4 0 0 1-8 0c0-2 1.4-4.2 4-7.2Z"
        fill="var(--color-reagent-500)"
      />
    </svg>
  );
}

export default function Shell() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-steel-300 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2.5" aria-label="На главную">
            <Logo />
            <span className="leading-tight">
              <span className="block text-sm font-bold tracking-tight text-steel-900">
                Реактор&nbsp;· малотонажная химия
              </span>
              <span className="block font-mono text-[11px] text-steel-500">
                пульт оператора
              </span>
            </span>
          </NavLink>
          <nav aria-label="Разделы" className="-mx-1 flex flex-1 flex-wrap items-center gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `rounded-sm px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-reagent-50 text-reagent-700"
                      : "text-steel-600 hover:bg-steel-100 hover:text-steel-800"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <hr className="pipe-rule" />
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>

      <footer className="border-t border-steel-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-xs text-steel-500 sm:px-6">
          <span>Пульт оператора малотоннажного производства</span>
          <span className="hidden sm:inline" aria-hidden="true">·</span>
          <NavLink to="/about" className="link">О системе</NavLink>
          <span className="ml-auto font-mono">API: /api · docs: порт 8000</span>
        </div>
      </footer>
    </div>
  );
}
