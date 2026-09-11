import { cn } from "@/lib/cn";

type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  serif?: boolean;
  large?: boolean;
  actions?: React.ReactNode;
  className?: string;
};

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  serif = false,
  large = false,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 pb-6 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between md:pb-8",
        className,
      )}
    >
      <div className="flex min-w-0 flex-col gap-2">
        {eyebrow ? (
          <p className="text-xs font-semibold tracking-wide text-text-muted">
            {eyebrow}
          </p>
        ) : null}
        <h1
          className={cn(
            "leading-tight tracking-tight text-ink",
            large
              ? "text-3xl font-bold sm:text-4xl"
              : serif
                ? "font-serif text-xl sm:text-[22px]"
                : "text-xl font-bold sm:text-[22px]",
          )}
        >
          {title}
        </h1>
        {subtitle ? (
          <p className="max-w-xl text-sm leading-relaxed text-text-muted">
            {subtitle}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex w-full shrink-0 flex-wrap items-center gap-2 sm:w-auto">
          {actions}
        </div>
      ) : null}
    </div>
  );
}
