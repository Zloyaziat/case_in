import { useEffect, useRef, useState } from "react";

/**
 * Периодический опрос с защитой от наложения запросов и паузой, когда
 * вкладка не видна (оператор может держать пульт открытым всю смену).
 *
 * fetch — колбэк, возвращающий промис; вызывается сразу и дальше каждые ms,
 * пока enabled. Ошибки копятся в error (последняя), данные — в data.
 */
export function usePoll<T>(
  fetch: () => Promise<T>,
  ms: number,
  enabled = true,
): { data: T | null; error: string | null; refresh: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cb = useRef(fetch);
  cb.current = fetch;
  const inflight = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    const tick = async () => {
      if (inflight.current || document.hidden) return;
      inflight.current = true;
      try {
        const value = await cb.current();
        if (!cancelled) {
          setData(value);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        inflight.current = false;
      }
    };

    tick();
    const timer = setInterval(tick, ms);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [ms, enabled]);

  const refresh = () => {
    void (async () => {
      try {
        const value = await cb.current();
        setData(value);
        setError(null);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  };

  return { data, error, refresh };
}
