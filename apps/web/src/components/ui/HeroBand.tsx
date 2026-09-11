import { cn } from "@/lib/cn";

type HeroBandProps = {
  children: React.ReactNode;
  className?: string;
};

export function HeroBand({ children, className }: HeroBandProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-3xl p-6 shadow-card sm:p-8 md:p-10",
        className,
      )}
      style={{
        backgroundImage:
          "linear-gradient(158.78deg, rgb(249, 241, 255) 0%, rgb(255, 255, 255) 50%, rgba(226, 223, 255, 0.35) 100%)",
      }}
    >
      <div
        className="pointer-events-none absolute -right-20 -top-24 size-96 rounded-full bg-[rgba(255,218,211,0.4)] blur-[32px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute bottom-[-96px] left-[30%] h-80 w-80 rounded-full bg-[rgba(194,193,255,0.35)] blur-[32px]"
        aria-hidden
      />
      <div className="relative z-10">{children}</div>
    </section>
  );
}
