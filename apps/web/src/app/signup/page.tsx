"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TrailMark } from "@/components/ui/Illustrations";
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

    setLoading(false);
    if (signUpError) {
      setError(signUpError.message);
      return;
    }

    if (data.session) {
      router.replace("/dashboard");
      router.refresh();
      return;
    }

    setMessage("Check your email to confirm your account, then sign in.");
  }

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
            Start your intentional search.
          </h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-white/70">
            Free for 14 days · No credit card · Cancel anytime
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
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            Create account
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            Email and password via secure auth.
          </p>
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
            {message ? <p className="text-sm text-coral">{message}</p> : null}
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Creating…" : "Sign up"}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-text-muted">
            Already have an account?{" "}
            <Link href="/login" className="font-semibold text-coral hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
