"use client";

import { startTransition, useEffect, useRef, useState } from "react";

export function useApiResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedPathRef = useRef<string | null>(null);

  useEffect(() => {
    if (!path) {
      loadedPathRef.current = null;
      setData(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    const pathChanged = loadedPathRef.current !== path;
    loadedPathRef.current = path;

    async function load() {
      setIsLoading(true);
      setError(null);
      if (pathChanged) {
        setData(null);
      }
      try {
        const response = await fetch(`/api/core${path}`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = (await response.json()) as T;
        if (!cancelled) {
          setData(payload);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : String(loadError));
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [path, reloadToken]);

  return {
    data,
    error,
    isLoading,
    reload: () => {
      startTransition(() => {
        setReloadToken((value) => value + 1);
      });
    },
  };
}

export async function postApiJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/core${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as T;
}
