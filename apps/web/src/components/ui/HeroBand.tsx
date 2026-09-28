import { cn } from "@/lib/cn";

type HeroBandProps = {
  children: React.ReactNode;
  className?: string;
  dark?: boolean;
};

export function HeroBand({ children, className, dark = false }: HeroBandProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-2xl border p-6 shadow-card sm:p-8 md:p-10",
        dark
          ? "border-white/10 text-white aurora-mesh-dark"
          : "border-line bg-white",
        className,
      )}
    >
      {!dark ? (
        <>
          <div
            className="pointer-events-none absolute -right-16 -top-20 size-80 rounded-full bg-[rgba(91,84,255,0.16)] blur-[48px]"
            aria-hidden
          />
          <div
            className="pointer-events-none absolute bottom-[-80px] left-[20%] h-64 w-64 rounded-full bg-[rgba(34,211,238,0.12)] blur-[40px]"
            aria-hidden
          />
        </>
      ) : null}
      <div className="relative z-10">{children}</div>
    </section>
  );
}
