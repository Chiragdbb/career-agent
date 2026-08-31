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
        "flex flex-col gap-4 pb-5 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between md:pb-7",
        className,
      )}
    >
      <div className="min-w-0 flex flex-col gap-2">
        {eyebrow ? (
          <p className="text-xs font-medium tracking-wide text-muted-foreground">
            {eyebrow}
          </p>
        ) : null}
        <h1
          className={cn(
            "leading-tight text-foreground",
            large
              ? "font-serif text-3xl sm:text-4xl"
              : serif
                ? "font-serif text-xl sm:text-[22px]"
                : "text-xl font-bold sm:text-[22px]",
          )}
        >
          {title}
        </h1>
        {subtitle ? (
          <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
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
