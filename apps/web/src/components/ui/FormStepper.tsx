import { cn } from "@/lib/cn";

type FormStepperProps = {
  steps: readonly { label: string }[];
  activeStep: number;
  className?: string;
};

export function FormStepper({ steps, activeStep, className }: FormStepperProps) {
  return (
    <div className={cn("-mx-1 overflow-x-auto pb-1", className)}>
      <div className="flex min-w-[28rem] items-start justify-between gap-2 px-1 sm:min-w-0">
        {steps.map((step, index) => {
          const isComplete = index < activeStep;
          const isActive = index === activeStep;
          return (
            <div
              key={step.label}
              className="flex flex-1 flex-col items-center gap-2"
            >
              <div className="relative flex w-full items-center justify-center">
                {index > 0 ? (
                  <div
                    className={cn(
                      "absolute right-1/2 top-4 h-px w-full",
                      isComplete || isActive ? "bg-primary/40" : "bg-border",
                    )}
                  />
                ) : null}
                {index < steps.length - 1 ? (
                  <div
                    className={cn(
                      "absolute left-1/2 top-4 h-px w-full",
                      isComplete ? "bg-primary/40" : "bg-border",
                    )}
                  />
                ) : null}
                <div
                  className={cn(
                    "relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-semibold",
                    isComplete
                      ? "border-primary bg-primary text-primary-foreground"
                      : isActive
                        ? "border-primary bg-background text-primary"
                        : "border-border bg-background text-muted-foreground",
                  )}
                >
                  {index + 1}
                </div>
              </div>
              <span
                className={cn(
                  "text-center text-[10px] sm:text-[11px]",
                  isActive ? "font-medium text-foreground" : "text-muted-foreground",
                )}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
