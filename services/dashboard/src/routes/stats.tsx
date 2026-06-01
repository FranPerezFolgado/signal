import { createFileRoute } from "@tanstack/react-router";
import { FaceplatePanel } from "@/components/signal/FaceplatePanel";

export const Route = createFileRoute("/stats")({
  component: StatsPage,
});

function StatsPage() {
  return (
    <FaceplatePanel slug="04" label="STATS" meta="PENDING">
      <div className="mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        <div className="text-signal-orange text-lg font-bold mb-3">// TODO</div>
        <p>STATS MODULE PENDING.</p>
        <p className="mt-1 text-zinc-600">AWAITING STATS-COLLECTOR SERVICE (v5).</p>
      </div>
    </FaceplatePanel>
  );
}
