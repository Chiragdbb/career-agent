"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AuthSplitPanel } from "@/components/marketing/AuthSplitPanel";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
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

    if (signInError) {
      setLoading(false);
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
        <Button type="submit" loading={loading} className="w-full">
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="text-center text-sm text-text-muted">
        No account?{" "}
        <Link href="/signup" className="font-semibold text-mkt-indigo hover:underline">
          Create one
        </Link>
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <AuthSplitPanel
      title="Your job search, finally calm."
      subtitle="Connect jobs, applications, contacts, and outreach — with your seal required before anything leaves."
      footer={null}
    >
      <h1 className="text-2xl font-semibold tracking-[-0.02em] text-mkt-ink">Sign in</h1>
      <p className="mt-2 text-sm text-mkt-muted">
        Use your email and password to access your workspace.
      </p>
      <div className="mt-8 flex flex-col gap-6">
        <Suspense fallback={<p className="text-sm text-mkt-muted">Loading…</p>}>
          <LoginForm />
        </Suspense>
      </div>
    </AuthSplitPanel>
  );
}
