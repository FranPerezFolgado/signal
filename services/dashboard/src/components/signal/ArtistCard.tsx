import { cn } from "@/lib/utils";
import type { EvidenceTrack, ScoreBreakdown } from "@/api/types";
import { GenreBadge } from "./GenreBadge";
import { SourceIcon } from "./SourceIcon";
import { ScoreReadout } from "./ScoreReadout";
import { ChevronRight, Pencil, Check, X } from "lucide-react";
import { useState, useRef } from "react";

type CardArtist = {
  id: string;
  name: string;
  high_priority: boolean;
  genres: string[];
  scrobble_count?: number;
  score?: number;
  breakdown?: ScoreBreakdown | null;
  evidence_tracks?: EvidenceTrack[];
  source?: string | null;
  origin_artist_name?: string | null;
  spotify_id?: string | null;
};

type Action = { label: string; tone: "primary" | "destructive"; onClick: () => void };

export function ArtistCard({
  artist,
  actions,
  meta,
  onSpotifyUpdate,
}: {
  artist: CardArtist;
  actions: Action[];
  meta?: { label: string; value: string }[];
  onSpotifyUpdate?: (spotifyId: string) => Promise<unknown>;
}) {
  const [editingSpotify, setEditingSpotify] = useState(false);
  const [spotifyInput, setSpotifyInput] = useState("");
  const [spotifySaving, setSpotifySaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function startEdit() {
    setSpotifyInput(artist.spotify_id ?? "");
    setEditingSpotify(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  async function confirmEdit() {
    const trimmed = spotifyInput.trim();
    if (!trimmed || !onSpotifyUpdate) {
      setEditingSpotify(false);
      return;
    }
    setSpotifySaving(true);
    try {
      await onSpotifyUpdate(trimmed);
    } finally {
      setSpotifySaving(false);
      setEditingSpotify(false);
    }
  }
  return (
    <article
      className={cn(
        "relative flex border border-border bg-panel transition-colors row-hover",
        artist.high_priority && "border-l-[4px] border-l-signal-orange",
      )}
    >
      {/* ID gutter */}
      <div className="hidden w-14 shrink-0 flex-col items-start justify-between gap-2 border-r border-border bg-panel-raised px-3 py-4 md:flex">
        <span className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">ID</span>
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
              {editingSpotify ? (
                <span className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  <input
                    ref={inputRef}
                    value={spotifyInput}
                    onChange={(e) => setSpotifyInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") confirmEdit();
                      if (e.key === "Escape") setEditingSpotify(false);
                    }}
                    disabled={spotifySaving}
                    placeholder="Spotify artist ID"
                    className="mono h-5 w-44 border border-zinc-500 bg-zinc-900 px-1.5 text-[10px] text-zinc-200 focus:border-[#1DB954] focus:outline-none"
                  />
                  <button
                    onClick={confirmEdit}
                    disabled={spotifySaving}
                    className="text-[#1DB954] hover:opacity-75 disabled:opacity-40"
                  >
                    <Check className="h-3 w-3" />
                  </button>
                  <button
                    onClick={() => setEditingSpotify(false)}
                    disabled={spotifySaving}
                    className="text-zinc-500 hover:text-zinc-300"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ) : (
                <span className="flex items-center gap-1">
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
                  {onSpotifyUpdate && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        startEdit();
                      }}
                      className="text-zinc-600 hover:text-zinc-400 transition-colors"
                      title="Edit Spotify artist ID"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                  )}
                </span>
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
                VIA → <span className="text-zinc-300">{artist.origin_artist_name}</span>
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
              {artist.evidence_tracks.map((t) => {
                const spotifyId = t.track_id?.startsWith("spotify:track:")
                  ? t.track_id.slice("spotify:track:".length)
                  : (t.track_id ?? null);
                return (
                  <li
                    key={t.text}
                    className="mono flex items-center gap-3 px-1 py-1.5 text-[12px] text-zinc-300"
                  >
                    <ChevronRight className="h-3 w-3 shrink-0 text-zinc-600" />
                    <span className="truncate flex-1">{t.text}</span>
                    {spotifyId && (
                      <a
                        href={`https://open.spotify.com/track/${spotifyId}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="shrink-0 border border-zinc-700 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-zinc-500 hover:border-[#1DB954] hover:text-[#1DB954] transition-colors"
                      >
                        SPT
                      </a>
                    )}
                  </li>
                );
              })}
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
