import * as React from "react";
import { X } from "lucide-react";
import type { GraphNodeAttributes } from "@/api/types";

const STATUS_COLORS: Record<string, string> = {
  FOLLOWING: "bg-signal-orange text-black",
  TRACKED: "bg-signal-green text-black",
  PUBLISHED: "bg-blue-500 text-white",
  BLACKLISTED: "bg-zinc-500 text-white",
};

interface ArtistGraphPanelProps {
  artist: GraphNodeAttributes | null;
  onClose: () => void;
}

export function ArtistGraphPanel({ artist, onClose }: ArtistGraphPanelProps) {
  React.useEffect(() => {
    if (!artist) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [artist, onClose]);

  if (!artist) return null;

  const score = artist.score != null ? artist.score.toFixed(2) : "—";
  const statusClass = STATUS_COLORS[artist.status ?? ""] ?? "bg-zinc-500 text-white";

  return (
    <div className="absolute right-0 top-0 z-10 h-full w-64 border-l border-border bg-panel p-4 shadow-lg">
      <div className="mb-4 flex items-start justify-between gap-2">
        <h2 className="mono truncate text-[13px] font-bold uppercase tracking-[0.12em]">
          {artist.label}
        </h2>
        <button
          onClick={onClose}
          className="shrink-0 rounded-none p-0.5 text-muted-foreground hover:text-foreground"
          aria-label="Close panel"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-3">
        <div>
          <p className="mono mb-1 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            STATUS
          </p>
          <span
            className={`mono inline-block px-2 py-0.5 text-[11px] font-bold uppercase tracking-[0.12em] ${statusClass}`}
          >
            {artist.status ?? "UNKNOWN"}
          </span>
        </div>

        <div>
          <p className="mono mb-1 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            SCORE
          </p>
          <p className="mono text-[13px] tabular-nums">{score}</p>
        </div>

        {artist.genres && artist.genres.length > 0 && (
          <div>
            <p className="mono mb-1.5 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              GENRES
            </p>
            <div className="flex flex-wrap gap-1.5">
              {artist.genres.map((g) => (
                <span
                  key={g}
                  className="mono inline-block border border-border px-2 py-0.5 text-[10px] uppercase tracking-[0.1em]"
                >
                  {g}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
