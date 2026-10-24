import type { ReactNode } from "react";

/** Общий заголовок страницы: номер-кик, название, пояснение. */
export function PageHead({
  kicker,
  title,
  lead,
  aside,
}: {
  kicker: string;
  title: string;
  lead?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-reagent-600">
          {kicker}
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-steel-900">{title}</h1>
        {lead && <p className="mt-1 max-w-2xl text-sm text-steel-600">{lead}</p>}
      </div>
      {aside && <div className="flex flex-wrap items-center gap-2">{aside}</div>}
    </div>
  );
}

export function Panel({
  title,
  note,
  actions,
  children,
  className = "",
  bodyClassName = "panel-body",
}: {
  title?: ReactNode;
  note?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <div className="panel-head">
          {title && <h2 className="panel-title">{title}</h2>}
          {note && <span className="panel-note">{note}</span>}
          {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function Chip({
  tone = "",
  children,
  lamp = false,
}: {
  tone?: "" | "--ok" | "--warn" | "--alarm" | "--reagent";
  children: ReactNode;
  lamp?: boolean;
}) {
  return (
    <span className={`chip chip${tone}`}>
      {lamp && (
        <span
          className={`lamp ${tone === "--reagent" ? "lamp--reagent lamp--pulse" : ""} ${
            tone === "--ok" ? "lamp--ok" : ""
          } ${tone === "--warn" ? "lamp--warn" : ""} ${tone === "--alarm" ? "lamp--alarm" : ""}`}
        />
      )}
      {children}
    </span>
  );
}

export function Notice({
  tone = "",
  children,
}: {
  tone?: "" | "--ok" | "--warn" | "--alarm";
  children: ReactNode;
}) {
  return <div className={`notice notice${tone}`} role={tone === "--alarm" ? "alert" : undefined}>{children}</div>;
}

export function Spinner({ label = "Загрузка…" }: { label?: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-steel-500" aria-live="polite">
      <span className="lamp lamp--reagent lamp--pulse" aria-hidden="true" />
      {label}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-steel-500">{children}</p>;
}

/** Обёртка широкой таблицы: на узком экране скроллится внутри панели. */
export function TableScroll({ children }: { children: ReactNode }) {
  return (
    <div className="-mx-3.5 overflow-x-auto px-3.5">
      <div className="min-w-full">{children}</div>
    </div>
  );
}

export function StatBlock({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  tone?: "--ok" | "--warn" | "--alarm";
}) {
  const color =
    tone === "--ok"
      ? "text-lamp-ok"
      : tone === "--warn"
        ? "text-lamp-warn"
        : tone === "--alarm"
          ? "text-lamp-alarm"
          : undefined;
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-medium uppercase tracking-wide text-steel-500">{label}</p>
      <p className={`readout mt-0.5 truncate ${color ?? ""}`}>
        {value}
        {unit && <span className="readout-unit">{unit}</span>}
      </p>
    </div>
  );
}
