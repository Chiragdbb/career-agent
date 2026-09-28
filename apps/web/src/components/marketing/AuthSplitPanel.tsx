import Link from "next/link";

import { TrailMark } from "@/components/ui/Illustrations";

type AuthSplitPanelProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
};

export function AuthSplitPanel({ title, subtitle, children, footer }: AuthSplitPanelProps) {
  return (
    <main className="marketing-shell flex min-h-screen bg-mkt-canvas">
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden p-12 lg:flex">
        <div className="absolute inset-0 bg-[linear-gradient(145deg,#0c1222_0%,#151d33_42%,#2a265c_100%)]" />
        <div className="absolute -right-20 top-24 h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(85,81,255,0.45),transparent_68%)]" />
        <div className="relative flex items-center gap-2.5">
          <Link href="/" className="flex items-center gap-2.5">
            <TrailMark size={28} />
            <span className="text-sm font-bold text-white">Waypoint</span>
          </Link>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-[-0.03em] text-white">
            {title}
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-white/72">{subtitle}</p>
        </div>
        <p className="relative text-xs text-white/45">
          Human approval on every outbound action
        </p>
      </div>

      <div className="flex flex-1 flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Link href="/" className="mb-4 inline-flex items-center gap-2.5">
              <TrailMark size={28} />
              <span className="text-sm font-bold text-mkt-ink">Waypoint</span>
            </Link>
          </div>
          {children}
          {footer ? <div className="mt-6">{footer}</div> : null}
        </div>
      </div>
    </main>
  );
}
