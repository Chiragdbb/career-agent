"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TrailMark } from "@/components/ui/Illustrations";
import { createClient } from "@/lib/supabase/client";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    const supabase = createClient();
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    setLoading(false);
    if (signInError) {
      setError(signInError.message);
      return;
    }

    router.replace(next);
    router.refresh();
  }

  return (
    <>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Input
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <Input
          label="Password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" disabled={loading} className="w-full">
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="text-center text-sm text-text-muted">
        No account?{" "}
        <Link href="/signup" className="font-semibold text-coral hover:underline">
          Create one
        </Link>
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-screen">
      <div
        className="hidden flex-1 flex-col justify-between p-12 lg:flex"
        style={{
          backgroundImage:
            "linear-gradient(160deg, #1e1a24 0%, #2f2936 55%, #b32107 140%)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <TrailMark size={28} />
          <span className="text-sm font-bold text-white">Waypoint</span>
        </div>
        <div>
          <h2 className="text-3xl font-bold leading-tight tracking-tight text-white">
            Your job search,{" "}
            <span className="font-serif italic text-[#ffdad3]">finally calm.</span>
          </h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-white/70">
            Connect jobs, applications, contacts, and outreach — with your seal
            required before anything leaves.
          </p>
        </div>
        <p className="text-xs text-white/50">Thoughtful career intelligence</p>
      </div>

      <div className="flex flex-1 flex-col justify-center bg-paper px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="mb-4 flex items-center gap-2.5">
              <TrailMark size={28} />
              <span className="text-sm font-bold">Waypoint</span>
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Sign in</h1>
          <p className="mt-2 text-sm text-text-muted">
            Use your email and password to access your workspace.
          </p>
          <div className="mt-8 flex flex-col gap-6">
            <Suspense fallback={<p className="text-sm text-text-muted">Loading…</p>}>
              <LoginForm />
            </Suspense>
          </div>
        </div>
      </div>
    </main>
  );
}
