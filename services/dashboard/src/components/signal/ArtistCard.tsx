import { cn } from "@/lib/utils";
import type { ScoreBreakdown } from "@/api/types";
import { GenreBadge } from "./GenreBadge";
import { SourceIcon } from "./SourceIcon";
import { ScoreReadout } from "./ScoreReadout";
import { ChevronRight } from "lucide-react";

type CardArtist = {
  id: string;
  name: string;
  high_priority: boolean;
  genres: string[];
  scrobble_count?: number;
  score?: number;
  breakdown?: ScoreBreakdown | null;
  evidence_tracks?: string[];
  source?: string | null;
  origin_artist_name?: string | null;
  spotify_id?: string | null;
};

type Action = { label: string; tone: "primary" | "destructive"; onClick: () => void };

export function ArtistCard({
  artist,
  actions,
  meta,
}: {
  artist: CardArtist;
  actions: Action[];
  meta?: { label: string; value: string }[];
}) {
  return (
    <article
      className={cn(
        "relative flex border border-border bg-panel transition-colors row-hover",
        artist.high_priority && "border-l-[4px] border-l-signal-orange",
      )}
    >
      {/* ID gutter */}
      <div className="hidden w-14 shrink-0 flex-col items-start justify-between gap-2 border-r border-border bg-panel-raised px-3 py-4 md:flex">
        <span className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          ID
        </span>
        <span className="mono text-[10px] text-zinc-400">{artist.id.slice(-4).toUpperCase()}</span>
      </div>

      <div className="flex-1 min-w-0 p-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {artist.high_priority && (
                <span className="mono bg-signal-orange px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.18em] text-black">
                  PRIORITY
                </span>
              )}
              <h3 className="mono truncate text-lg font-bold uppercase tracking-[0.04em] text-foreground">
                {artist.name}
              </h3>
              {artist.spotify_id && (
                <a
                  href={`https://open.spotify.com/artist/${artist.spotify_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="mono shrink-0 border border-zinc-600 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-zinc-400 hover:border-[#1DB954] hover:text-[#1DB954] transition-colors"
                >
                  SPT
                </a>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {artist.genres.map((g) => (
                <GenreBadge key={g}>{g}</GenreBadge>
              ))}
              {artist.source && (
                <>
                  <span className="mono mx-1 text-border-strong">/</span>
                  <SourceIcon source={artist.source} withLabel />
                </>
              )}
            </div>
            {artist.origin_artist_name && (
              <div className="mono mt-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                VIA →{" "}
                <span className="text-zinc-300">{artist.origin_artist_name}</span>
              </div>
            )}
            {meta && (
              <div className="mono mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                {meta.map((m) => (
                  <span key={m.label}>
                    {m.label} <span className="text-foreground">{m.value}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
          {artist.score !== undefined && (
            <ScoreReadout score={artist.score} breakdown={artist.breakdown ?? null} />
          )}
        </div>

        {/* Evidence */}
        {artist.evidence_tracks && artist.evidence_tracks.length > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <div className="mono mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              <span>EVIDENCE</span>
              <span>{artist.evidence_tracks.length} TRACKS</span>
            </div>
            <ul className="divide-y divide-border border-y border-border">
              {artist.evidence_tracks.map((t) => (
                <li
                  key={t}
                  className="mono flex items-center gap-3 px-1 py-1.5 text-[12px] text-zinc-300"
                >
                  <ChevronRight className="h-3 w-3 text-zinc-600" />
                  <span className="truncate">{t}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {actions.map((a) => (
            <button
              key={a.label}
              onClick={a.onClick}
              className={cn(
                "mono inline-flex items-center gap-2 border px-3.5 py-2 text-[11px] font-bold uppercase tracking-[0.15em] transition-colors active:shadow-[inset_0_0_0_1px_rgba(0,0,0,0.5)]",
                a.tone === "primary" &&
                  "border-signal-orange bg-signal-orange text-black hover:bg-[#ff7a2a]",
                a.tone === "destructive" &&
                  "border-signal-red text-signal-red hover:bg-signal-red hover:text-white",
              )}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}
