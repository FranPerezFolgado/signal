import { Link, useLocation } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "QUEUE", index: "01" },
  { to: "/discovery", label: "DISCOVERY", index: "02" },
  { to: "/following", label: "FOLLOWING", index: "03" },
  { to: "/stats", label: "STATS", index: "04" },
] as const;

export function Sidebar() {
  const loc = useLocation();
  return (
    <aside className="hidden w-[180px] shrink-0 flex-col border-r border-border-strong bg-panel md:flex">
      {/* Brand */}
      <div className="border-b border-border-strong px-4 py-5">
        <div className="mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          // SIGNAL
        </div>
        <div className="mt-1 font-mono text-xl font-bold tracking-tight text-foreground">
          v0.2
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2">
        {NAV.map((item) => {
          const active = loc.pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "mono group block border-b border-border px-4 py-4 text-[11px] uppercase tracking-[0.18em] transition-colors",
                active
                  ? "bg-signal-orange text-black"
                  : "text-muted-foreground hover:bg-panel-raised hover:text-foreground",
              )}
            >
              <div className={cn("text-[9px]", active ? "text-black/70" : "text-zinc-600")}>
                § {item.index}
              </div>
              <div className="mt-1 font-bold">{item.label}</div>
            </Link>
          );
        })}
      </nav>

      {/* Status footer */}
      <div className="border-t border-border-strong px-4 py-3">
        <div className="mono flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          <span>SYS</span>
          <span className="text-signal-orange">OK</span>
        </div>
        <div className="mono mt-1 text-[9px] uppercase tracking-[0.2em] text-zinc-600">
          UPLINK · 24.7KB/S
        </div>
      </div>
    </aside>
  );
}
