import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-6 px-6">
      <div>
        <p className="text-sm uppercase tracking-wide text-zinc-500">
          Career Agent
        </p>
        <h1 className="mt-1 text-3xl font-semibold text-zinc-900">
          AI Career Agent
        </h1>
        <p className="mt-3 text-zinc-600">
          Minimal web shell for Supabase Auth. Sign in to reach the protected
          dashboard placeholder.
        </p>
      </div>
      <div className="flex gap-3">
        <Link
          href="/login"
          className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white"
        >
          Sign in
        </Link>
        <Link
          href="/signup"
          className="rounded border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-900"
        >
          Sign up
        </Link>
      </div>
    </main>
  );
}
