import * as React from "react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function FaceplatePanel({
  label,
  meta,
  slug,
  info,
  children,
  className,
  bodyClassName,
}: {
  label?: string;
  meta?: React.ReactNode;
  slug?: string;
  info?: string;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("faceplate", className)}>
      {(label || meta) && (
        <header className="flex items-center justify-between border-b border-border bg-panel-raised px-3 py-2">
          <div className="flex items-center gap-3">
            {slug && (
              <span className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                § {slug}
              </span>
            )}
            <span className="mono text-[11px] font-bold uppercase tracking-[0.15em] text-foreground">
              {label}
            </span>
            {info && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="flex h-[14px] w-[14px] items-center justify-center rounded-full border border-muted-foreground/40 text-muted-foreground/60 hover:border-muted-foreground hover:text-muted-foreground mono text-[9px] leading-none transition-colors"
                  >
                    ?
                  </button>
                </TooltipTrigger>
                <TooltipContent
                  side="bottom"
                  className="max-w-[260px] whitespace-normal leading-relaxed"
                >
                  {info}
                </TooltipContent>
              </Tooltip>
            )}
          </div>
          {meta && (
            <span className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {meta}
            </span>
          )}
        </header>
      )}
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}
