"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { AuthSplitPanel } from "@/components/marketing/AuthSplitPanel";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    const supabase = createClient();
    const { data, error: signUpError } = await supabase.auth.signUp({
      email,
      password,
    });

    if (signUpError) {
      setLoading(false);
      setError(signUpError.message);
      return;
    }

    if (data.session) {
      router.replace("/dashboard");
      router.refresh();
      return;
    }

    setLoading(false);
    setMessage("Check your email to confirm your account, then sign in.");
  }

  return (
    <AuthSplitPanel
      title="Start your intentional search."
      subtitle="Free for 14 days · No credit card · Cancel anytime"
      footer={
        <p className="text-center text-sm text-mkt-muted">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-mkt-indigo hover:underline">
            Sign in
          </Link>
        </p>
      }
    >
      <h1 className="text-2xl font-semibold tracking-[-0.02em] text-mkt-ink">
        Create account
      </h1>
      <p className="mt-2 text-sm text-mkt-muted">Email and password via secure auth.</p>
      <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-4">
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
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {message ? <p className="text-sm text-mkt-indigo">{message}</p> : null}
        <Button type="submit" loading={loading} className="w-full">
          {loading ? "Creating…" : "Sign up"}
        </Button>
      </form>
    </AuthSplitPanel>
  );
}
