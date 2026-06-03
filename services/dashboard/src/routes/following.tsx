import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search } from "lucide-react";
import { ArtistCard } from "@/components/signal/ArtistCard";
import { Input } from "@/components/ui/input";
import { queryKeys, useStatusMutation } from "@/store/signal";
import { fetchFollowingArtists } from "@/api/queries";
import { Pagination } from "@/components/signal/Pagination";

export const Route = createFileRoute("/following")({
  component: FollowingPage,
});

type SortOption = "date_desc" | "date_asc" | "plays_desc" | "plays_asc" | "listen_desc" | "listen_asc";

const SORT_OPTIONS: {
  value: SortOption;
  label: string;
  sortBy: "first_seen_at" | "scrobble_count" | "first_play_at";
  order: "asc" | "desc";
}[] = [
  { value: "plays_desc",  label: "MOST PLAYS ↓",       sortBy: "scrobble_count", order: "desc" },
  { value: "plays_asc",   label: "FEWEST PLAYS ↑",     sortBy: "scrobble_count", order: "asc"  },
  { value: "listen_desc", label: "LAST LISTENED ↓",    sortBy: "first_play_at",  order: "desc" },
  { value: "listen_asc",  label: "FIRST LISTENED ↑",   sortBy: "first_play_at",  order: "asc"  },
  { value: "date_desc",   label: "ADDED NEWEST ↓",     sortBy: "first_seen_at",  order: "desc" },
  { value: "date_asc",    label: "ADDED OLDEST ↑",     sortBy: "first_seen_at",  order: "asc"  },
];

function FollowingPage() {
  const [page, setPage] = React.useState(1);
  const [q, setQ] = React.useState("");
  const [genre, setGenre] = React.useState<string | null>(null);
  const [sortOption, setSortOption] = React.useState<SortOption>("plays_desc");
  const genreOptionsRef = React.useRef<string[]>([]);

  const { sortBy, order } = SORT_OPTIONS.find((o) => o.value === sortOption)!;

  const qKey = queryKeys.following(page, genre, sortBy, order);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: qKey,
    queryFn: () => fetchFollowingArtists(page, genre, sortBy, order),
  });
  const mutation = useStatusMutation(qKey);

  React.useEffect(() => {
    if (!genre && data?.items) {
      const all = [...new Set(data.items.flatMap((a) => a.genres ?? []))].sort();
      if (all.length) genreOptionsRef.current = all;
    }
  }, [data, genre]);

  const handleGenreChange = (g: string | null) => {
    setGenre(g);
    setPage(1);
  };

  const handleSortChange = (val: SortOption) => {
    setSortOption(val);
    setPage(1);
  };

  if (isLoading) {
    return (
      <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        ACQUIRING SIGNAL…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-signal-red">
        SIGNAL LOST — {String(error)}
      </div>
    );
  }

  const items = data?.items ?? [];
  const filtered = q
    ? items.filter((a) => a.name.toLowerCase().includes(q.toLowerCase()))
    : items;

  return (
    <div className="space-y-4">
      <div className="-mx-4 grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 border-b border-border-strong bg-panel px-4 py-3 md:-mx-6 md:px-6">
        <div className="relative min-w-0">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="SEARCH ARTIST…"
            className="mono h-9 w-full rounded-none border-border bg-background pl-9 text-[12px] uppercase tracking-[0.12em] placeholder:text-zinc-600"
          />
        </div>

        <select
          value={genre ?? ""}
          onChange={(e) => handleGenreChange(e.target.value || null)}
          className="mono h-9 rounded-none border border-border bg-background px-3 text-[11px] uppercase tracking-[0.12em]"
        >
          <option value="">ALL GENRES</option>
          {genreOptionsRef.current.map((g) => (
            <option key={g} value={g}>
              {g.toUpperCase()}
            </option>
          ))}
        </select>

        <select
          value={sortOption}
          onChange={(e) => handleSortChange(e.target.value as SortOption)}
          className="mono h-9 rounded-none border border-border bg-background px-3 text-[11px] uppercase tracking-[0.12em]"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <div className="mono border border-signal-green bg-signal-green px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.15em] text-black">
          {filtered.length}/{data?.total ?? 0}
        </div>
      </div>

      {items.length === 0 && genre !== null ? (
        <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO SIGNAL. ADJUST FILTERS.
        </div>
      ) : items.length === 0 ? (
        <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO ACTIVE TRACKING. PROMOTE FROM QUEUE.
        </div>
      ) : filtered.length === 0 ? (
        <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO SIGNAL. ADJUST FILTERS.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((a) => (
            <ArtistCard
              key={a.id}
              artist={a}
              meta={[{ label: "PLAYS", value: String(a.scrobble_count) }]}
              actions={[
                {
                  label: "BLACKLIST",
                  tone: "destructive",
                  onClick: () => {
                    mutation.mutate(
                      { id: a.id, status: "BLACKLISTED" },
                      {
                        onSuccess: () =>
                          toast("ARTIST.BLACKLISTED", { description: a.name.toUpperCase() }),
                      },
                    );
                  },
                },
              ]}
            />
          ))}
        </div>
      )}

      {data && <Pagination page={page} pages={data.pages} onChange={setPage} />}
    </div>
  );
}
