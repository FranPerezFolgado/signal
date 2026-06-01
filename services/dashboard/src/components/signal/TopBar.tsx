import * as React from "react";
import { useLocation } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";

const TITLES: Record<string, { name: string; index: string }> = {
  "/": { name: "QUEUE", index: "01" },
  "/discovery": { name: "DISCOVERY", index: "02" },
  "/following": { name: "FOLLOWING", index: "03" },
  "/stats": { name: "STATS", index: "04" },
};

export function TopBar() {
  const loc = useLocation();
  const meta = TITLES[loc.pathname] ?? { name: "—", index: "00" };
  const now = new Date().toISOString().slice(11, 19);

  const qc = useQueryClient();
  const [hasError, setHasError] = React.useState(false);

  React.useEffect(() => {
    return qc.getQueryCache().subscribe(() => {
      const queries = qc.getQueryCache().getAll();
      setHasError(queries.some((q) => q.state.status === "error"));
    });
  }, [qc]);

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-border-strong bg-panel px-4">
      <div className="flex items-center gap-4">
        <span className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          § {meta.index}
        </span>
        <h1 className="mono text-sm font-bold uppercase tracking-[0.18em] text-foreground">
          {meta.name}
        </h1>
      </div>
      <div className="mono flex items-center gap-5 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        <span>
          SYS:
          {hasError ? (
            <span className="text-signal-red">ERR</span>
          ) : (
            <span className="text-signal-orange">OK</span>
          )}
        </span>
        <span className="hidden sm:inline">
          <span className="text-foreground">{now}</span> UTC
        </span>
      </div>
    </header>
  );
}
