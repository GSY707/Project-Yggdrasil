export type AsyncStatus = "idle" | "loading" | "success" | "error";

export interface AsyncState<T> {
  status: AsyncStatus;
  data?: T;
  error?: unknown;
}

export function createIdleState<T>(): AsyncState<T> {
  return { status: "idle" };
}
