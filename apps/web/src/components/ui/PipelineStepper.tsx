import { cn } from "@/lib/cn";

type Step = { label: string; count: number };

type PipelineStepperProps = {
  steps: Step[];
  className?: string;
};

export function PipelineStepper({ steps, className }: PipelineStepperProps) {
  return (
    <div className={cn("-mx-1 overflow-x-auto pb-1", className)}>
      <div className="flex min-w-[32rem] items-start justify-between gap-2 px-1 sm:min-w-0">
        {steps.map((step, i) => (
          <div key={step.label} className="flex flex-1 flex-col items-center gap-2">
            <div className="relative flex w-full items-center justify-center">
              {i > 0 ? (
                <div className="absolute right-1/2 top-4 h-px w-full bg-border" />
              ) : null}
              {i < steps.length - 1 ? (
                <div className="absolute left-1/2 top-4 h-px w-full bg-border" />
              ) : null}
              <div className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 border-border bg-background">
                <span className="text-xs font-semibold text-primary">{step.count}</span>
              </div>
            </div>
            <span className="text-center text-[10px] text-muted-foreground sm:text-[11px]">
              {step.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
