"use client";

import { startTransition, useEffect, useRef, useState } from "react";

async function responseErrorMessage(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const payload = JSON.parse(text) as { detail?: unknown; message?: unknown };
    const detail = typeof payload.detail === "string" ? payload.detail : typeof payload.message === "string" ? payload.message : null;
    if (detail) {
      return detail;
    }
  } catch {
    // Fall back to the response text below.
  }
  return text || `Request failed with status ${response.status}.`;
}

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
          throw new Error(await responseErrorMessage(response));
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
    throw new Error(await responseErrorMessage(response));
  }
  return (await response.json()) as T;
}

export async function deleteApiJson<T>(path: string): Promise<T> {
  const response = await fetch(`/api/core${path}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return (await response.json()) as T;
}
