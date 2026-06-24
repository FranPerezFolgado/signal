import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { GenreGraph } from "@/components/signal/GenreGraph";
import { fetchGraphData } from "@/api/queries";
import type { GraphFilters } from "@/api/types";

export const Route = createFileRoute("/graph")({
  component: GraphPage,
});

const STATUS_OPTIONS = ["FOLLOWING", "TRACKED", "PUBLISHED", "BLACKLISTED"] as const;
const LIMIT_OPTIONS = [100, 250, 500, 1000] as const;

const DEFAULT_FILTERS: GraphFilters = { limit: 500 };

function useDebounce<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

function GraphPage() {
  const [filters, setFilters] = React.useState<GraphFilters>(DEFAULT_FILTERS);
  const [genreInput, setGenreInput] = React.useState("");
  const [minScore, setMinScore] = React.useState(0);
  const [minGenreArtists, setMinGenreArtists] = React.useState(2);

  const debouncedGenre = useDebounce(genreInput.trim(), 200);

  const activeFilters: GraphFilters = React.useMemo(() => {
    const f: GraphFilters = { ...filters };
    if (debouncedGenre) f.genre = debouncedGenre;
    else delete f.genre;
    if (minScore > 0) f.min_score = minScore;
    else delete f.min_score;
    if (minGenreArtists !== 2) f.min_genre_artists = minGenreArtists;
    else delete f.min_genre_artists;
    return f;
  }, [filters, debouncedGenre, minScore, minGenreArtists]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["graph", activeFilters],
    queryFn: () => fetchGraphData(activeFilters),
  });

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setFilters((f) => ({ ...f, status: val || undefined }));
  };

  const handleLimitChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters((f) => ({ ...f, limit: Number(e.target.value) }));
  };

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="-mx-4 grid grid-cols-[auto_1fr_auto_auto_auto_auto] items-center gap-3 border-b border-border-strong bg-panel px-4 py-3 md:-mx-6 md:px-6">
        <span className="mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
          STATUS
        </span>
        <select
          value={filters.status ?? ""}
          onChange={handleStatusChange}
          className="mono h-9 rounded-none border border-border bg-background px-3 text-[11px] uppercase tracking-[0.12em]"
        >
          <option value="">ALL</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        <div className="relative">
          <input
            type="text"
            value={genreInput}
            onChange={(e) => setGenreInput(e.target.value)}
            placeholder="GENRE…"
            className="mono h-9 w-40 rounded-none border border-border bg-background px-3 text-[11px] uppercase tracking-[0.12em] placeholder:text-zinc-600"
          />
          {genreInput && (
            <button
              onClick={() => setGenreInput("")}
              className="mono absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-muted-foreground hover:text-foreground"
              aria-label="Clear genre"
            >
              ×
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            MIN SCORE {minScore > 0 ? minScore.toFixed(2) : "—"}
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-24 accent-signal-orange"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            MIN GENRE ARTISTS {minGenreArtists}
          </span>
          <input
            type="range"
            min={1}
            max={10}
            step={1}
            value={minGenreArtists}
            onChange={(e) => setMinGenreArtists(Number(e.target.value))}
            className="w-20 accent-signal-orange"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            LIMIT
          </span>
          <select
            value={filters.limit ?? 500}
            onChange={handleLimitChange}
            className="mono h-9 rounded-none border border-border bg-background px-3 text-[11px] uppercase tracking-[0.12em]"
          >
            {LIMIT_OPTIONS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error banner */}
      {isError && (
        <div className="mono flex items-center justify-between border border-signal-red bg-signal-red/10 px-4 py-2 text-[11px] uppercase tracking-[0.15em] text-signal-red">
          <span>SIGNAL LOST — {String(error)}</span>
          <button
            onClick={() => refetch()}
            className="mono ml-4 border border-signal-red px-3 py-1 text-[10px] font-bold uppercase tracking-[0.12em] hover:bg-signal-red hover:text-black"
          >
            RETRY
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          MAPPING GRAPH…
        </div>
      )}

      {/* Empty result state */}
      {!isLoading && !isError && data && data.nodes.length === 0 && (
        <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO SIGNAL — ADJUST FILTERS
        </div>
      )}

      {/* Graph canvas */}
      {!isLoading && !isError && data && data.nodes.length > 0 && <GenreGraph data={data} />}
    </div>
  );
}
