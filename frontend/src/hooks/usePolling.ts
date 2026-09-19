import { useEffect, useRef, useState } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  interval: number = 2000,
  enabled: boolean = true,
  shouldStop?: (data: T | null) => boolean,
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const savedFetcher = useRef(fetcher);
  const savedShouldStop = useRef(shouldStop);

  useEffect(() => {
    savedFetcher.current = fetcher;
    savedShouldStop.current = shouldStop;
  }, [fetcher, shouldStop]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    let isSubscribed = true;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const result = await savedFetcher.current();
        if (isSubscribed) {
          setData(result);
          setError(null);
          setLoading(false);

          // Terminal state check to prevent infinite polling
          let isTerminal = false;
          if (savedShouldStop.current && savedShouldStop.current(result)) {
            isTerminal = true;
          } else if (result && typeof result === "object") {
            const r: any = result;
            if (
              r.status === "completed" ||
              r.status === "failed" ||
              r.status === "cancelled" ||
              (typeof r.percent === "number" && r.percent >= 100)
            ) {
              isTerminal = true;
            }
          }

          if (isTerminal) {
            isSubscribed = false;
            return;
          }
        }
      } catch (err) {
        if (isSubscribed) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setLoading(false);
        }
      } finally {
        if (isSubscribed) {
          timer = setTimeout(poll, interval);
        }
      }
    };

    setLoading(true);
    poll();

    return () => {
      isSubscribed = false;
      clearTimeout(timer);
    };
  }, [interval, enabled]);

  return { data, loading, error };
}
