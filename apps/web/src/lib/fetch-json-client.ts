import { apiFetch } from "@/lib/api";

export async function fetchJsonClient<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await apiFetch(path, init);

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message || `API ${response.status}`);
  }

  return (await response.json()) as T;
}
