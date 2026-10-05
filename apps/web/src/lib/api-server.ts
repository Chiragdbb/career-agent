import { createClient } from "@/lib/supabase/server";

const apiBase =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

/**
 * Server-side API fetch using the Supabase session cookie.
 */
export async function apiFetchServer(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Not authenticated");
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);
  if (
    !headers.has("Content-Type") &&
    init.body &&
    !(init.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }

  const url = path.startsWith("http") ? path : `${apiBase}${path}`;
  return fetch(url, { ...init, headers, cache: "no-store" });
}
