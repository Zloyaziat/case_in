import { useId, useMemo } from "react";

/**
 * Лёгкие SVG-графики в стиле приборной панели — без внешних библиотек,
 * чтобы линия читалась как тренд на мнемосхеме, а не как «стоковый чарт».
 * Все размеры через viewBox: график тянется по ширине контейнера.
 */

export type Point = { x: number; y: number | null };

export type Series = {
  name: string;
  color?: string;
  points: Point[];
  /** необязательная допустимая полоса (min/max) по точкам x */
  band?: { x: number; min: number | null; max: number | null }[];
};

const PALETTE = [
  "var(--color-reagent-500)",
  "var(--color-lamp-warn)",
  "var(--color-lamp-ok)",
  "var(--color-lamp-alarm)",
  "#6f7f8f",
  "#9dcfd9",
];

function extent(values: number[]): [number, number] {
  const finite = values.filter((v) => Number.isFinite(v));
  if (!finite.length) return [0, 1];
  let lo = Math.min(...finite);
  let hi = Math.max(...finite);
  if (lo === hi) {
    lo -= Math.abs(lo) * 0.1 || 1;
    hi += Math.abs(hi) * 0.1 || 1;
  }
  const pad = (hi - lo) * 0.12;
  return [lo - pad, hi + pad];
}

/** Многосерийный линейный график с осями и подписями. */
export function SeriesChart({
  series,
  height = 180,
  xLabel,
  yLabel,
  xTicks = 4,
  yTicks = 4,
}: {
  series: Series[];
  height?: number;
  xLabel?: string;
  yLabel?: string;
  xTicks?: number;
  yTicks?: number;
}) {
  const gid = useId().replace(/:/g, "");
  const W = 640;
  const H = height;
  const pad = { l: 46, r: 12, t: 10, b: 26 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;

  const { xmin, xmax, ymin, ymax } = useMemo(() => {
    const xs: number[] = [];
    const ys: number[] = [];
    for (const s of series) {
      for (const p of s.points) {
        xs.push(p.x);
        if (p.y != null) ys.push(p.y);
      }
      for (const b of s.band ?? []) {
        xs.push(b.x);
        if (b.min != null) ys.push(b.min);
        if (b.max != null) ys.push(b.max);
      }
    }
    const [x0, x1] = extent(xs.length ? xs : [0, 1]);
    const [y0, y1] = extent(ys);
    return {
      xmin: xs.length ? Math.min(...xs) : x0,
      xmax: xs.length ? Math.max(...xs) : x1,
      ymin: y0,
      ymax: y1,
    };
  }, [series]);

  const sx = (x: number) =>
    pad.l + (xmax === xmin ? iw / 2 : ((x - xmin) / (xmax - xmin)) * iw);
  const sy = (y: number) =>
    pad.t + ih - ((y - ymin) / (ymax - ymin || 1)) * ih;

  const line = (pts: Point[]) => {
    let d = "";
    let pen = false;
    for (const p of pts) {
      if (p.y == null) {
        pen = false;
        continue;
      }
      d += `${pen ? "L" : "M"}${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`;
      pen = true;
    }
    return d;
  };

  const bandPath = (band: NonNullable<Series["band"]>) => {
    const withBoth = band.filter((b) => b.min != null && b.max != null);
    if (withBoth.length < 2) return "";
    const top = withBoth.map((b) => `${sx(b.x).toFixed(1)},${sy(b.max as number).toFixed(1)}`);
    const bottom = withBoth
      .slice()
      .reverse()
      .map((b) => `${sx(b.x).toFixed(1)},${sy(b.min as number).toFixed(1)}`);
    return `M${top.join("L")}L${bottom.join("L")}Z`;
  };

  const yGridVals = Array.from({ length: yTicks + 1 }, (_, i) => ymin + ((ymax - ymin) * i) / yTicks);
  const xGridVals = Array.from({ length: xTicks + 1 }, (_, i) => xmin + ((xmax - xmin) * i) / xTicks);

  const fmt = (v: number) =>
    Math.abs(v) >= 1000 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2);

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: "auto" }}
        role="img"
        aria-label={yLabel ? `График: ${yLabel}` : "График показаний"}
      >
        {/* сетка */}
        {yGridVals.map((v, i) => (
          <g key={`y${i}`}>
            <line
              x1={pad.l} x2={W - pad.r} y1={sy(v)} y2={sy(v)}
              stroke="var(--color-steel-200)" strokeWidth="1"
            />
            <text
              x={pad.l - 6} y={sy(v) + 3} textAnchor="end"
              className="num" fontSize="9" fill="var(--color-steel-500)"
            >
              {fmt(v)}
            </text>
          </g>
        ))}
        {xGridVals.map((v, i) => (
          <text
            key={`x${i}`} x={sx(v)} y={H - pad.b + 14} textAnchor="middle"
            className="num" fontSize="9" fill="var(--color-steel-500)"
          >
            {fmt(v)}
          </text>
        ))}

        {/* полосы и линии */}
        {series.map((s, si) => {
          const color = s.color ?? PALETTE[si % PALETTE.length];
          const bp = s.band ? bandPath(s.band) : "";
          return (
            <g key={s.name + si}>
              {bp && <path d={bp} fill={color} opacity="0.1" />}
              <path d={line(s.points)} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
            </g>
          );
        })}

        {/* оси */}
        <line x1={pad.l} x2={pad.l} y1={pad.t} y2={H - pad.b} stroke="var(--color-steel-400)" strokeWidth="1" />
        <line x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="var(--color-steel-400)" strokeWidth="1" />
      </svg>

      {/* легенда */}
      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        {series.map((s, si) => (
          <span key={s.name + si} className="flex items-center gap-1.5 text-xs text-steel-600">
            <span
              className="inline-block h-0.5 w-4 rounded-full"
              style={{ background: s.color ?? PALETTE[si % PALETTE.length] }}
              aria-hidden="true"
            />
            {s.name}
          </span>
        ))}
        {xLabel && <span className="ml-auto font-mono text-[11px] text-steel-500">{xLabel}</span>}
      </figcaption>
    </figure>
  );
}

/** Компактный тренд без осей — для карточек и ячеек. */
export function Sparkline({
  values,
  width = 120,
  height = 28,
  color = "var(--color-reagent-500)",
}: {
  values: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const gid = useId().replace(/:/g, "");
  const pts = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (pts.length < 2) {
    return <span className="text-xs text-steel-400">мало точек</span>;
  }
  const [lo, hi] = extent(pts);
  const step = width / (pts.length - 1);
  const d = pts
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - lo) / (hi - lo || 1)) * (height - 2) - 1;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join("");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden="true">
      <path d={`${d}L${width} ${height}L0 ${height}Z`} fill={color} opacity="0.08" />
      <path d={d} fill="none" stroke={color} strokeWidth="1.4" />
      <circle
        cx={(pts.length - 1) * step}
        cy={height - ((pts[pts.length - 1] - lo) / (hi - lo || 1)) * (height - 2) - 1}
        r="1.8"
        fill={color}
      />
    </svg>
  );
}
