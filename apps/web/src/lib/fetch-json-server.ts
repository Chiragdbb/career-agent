import "server-only";

import { apiFetchServer } from "@/lib/api-server";

export async function fetchJsonServer<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await apiFetchServer(path, init);

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message || `API ${response.status}`);
  }

  return (await response.json()) as T;
}
