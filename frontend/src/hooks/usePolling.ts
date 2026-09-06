import { useState, useEffect, useRef } from 'react';

export function usePolling<T>(
  fetcher: () => Promise<T>,
  interval: number = 2000,
  enabled: boolean = true
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  const savedFetcher = useRef(fetcher);

  useEffect(() => {
    savedFetcher.current = fetcher;
  }, [fetcher]);

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
