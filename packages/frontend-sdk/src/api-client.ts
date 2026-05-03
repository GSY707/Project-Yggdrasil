import type { ServiceHealthSnapshot } from "./types";

export interface ApiClientOptions {
  baseUrl: string;
  headers?: Record<string, string>;
}

export class FrontendApiClient {
  private readonly baseUrl: string;
  private readonly headers: Record<string, string>;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.headers = options.headers ?? {};
  }

  async getHealth(signal?: AbortSignal): Promise<ServiceHealthSnapshot> {
    return this.getJson<ServiceHealthSnapshot>("/health", signal);
  }

  async getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await fetch(this.resolvePath(path), {
      method: "GET",
      headers: this.headers,
      signal,
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`API request failed (${response.status}) at ${path}`);
    }

    return (await response.json()) as T;
  }

  private resolvePath(path: string): string {
    return path.startsWith("http") ? path : `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  }
}
