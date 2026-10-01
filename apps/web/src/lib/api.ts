import { createClient } from "@/lib/supabase/client";

const apiBase =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

let cachedAccessToken: string | null = null;
let tokenExpiresAt = 0;
let authListenerStarted = false;

function ensureAuthListener() {
  if (authListenerStarted || typeof window === "undefined") return;
  authListenerStarted = true;
  const supabase = createClient();
  supabase.auth.onAuthStateChange((_event, session) => {
    cachedAccessToken = session?.access_token ?? null;
    tokenExpiresAt = session?.expires_at
      ? session.expires_at * 1000
      : 0;
  });
}

async function getAccessToken(): Promise<string> {
  ensureAuthListener();
  const now = Date.now();
  if (cachedAccessToken && tokenExpiresAt > now + 30_000) {
    return cachedAccessToken;
  }

  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    cachedAccessToken = null;
    tokenExpiresAt = 0;
    throw new Error("Not authenticated");
  }

  cachedAccessToken = session.access_token;
  tokenExpiresAt = session.expires_at ? session.expires_at * 1000 : now + 3_600_000;
  return session.access_token;
}

/**
 * Call the Career Agent API with the current Supabase access token.
 * Never send the service role key from the browser.
 */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = await getAccessToken();

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  // Let the browser set multipart boundary for FormData uploads.
  if (
    !headers.has("Content-Type") &&
    init.body &&
    !(init.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }

  const url = path.startsWith("http") ? path : `${apiBase}${path}`;
  return fetch(url, { ...init, headers });
}
