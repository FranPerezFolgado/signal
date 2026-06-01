import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ScoreBreakdown } from "@/api/types";

export function ScoreReadout({
  score,
  breakdown,
}: {
  score: number;
  breakdown: ScoreBreakdown | null;
}) {
  const display = (
    <div className="flex flex-col items-end leading-none cursor-help">
      <span className="mono text-foreground text-4xl font-bold tabular-nums">
        {Math.round(score * 100)}
      </span>
      <span className="mono mt-1.5 text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
        / 100 · SCORE
      </span>
    </div>
  );

  if (!breakdown) return display;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{display}</TooltipTrigger>
      <TooltipContent
        side="left"
        className="mono border border-border bg-panel px-3 py-2 text-[11px] text-foreground rounded-none"
      >
        <div className="space-y-0.5">
          <Row k="genre_novelty" v={breakdown.genre_novelty} />
          <Row k="popularity_norm" v={breakdown.popularity_norm} />
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function Row({ k, v }: { k: string; v: number }) {
  return (
    <div className="flex items-center justify-between gap-6 uppercase tracking-[0.12em]">
      <span className="text-muted-foreground">{k}</span>
      <span className="text-signal-orange">{v.toFixed(2)}</span>
    </div>
  );
}
