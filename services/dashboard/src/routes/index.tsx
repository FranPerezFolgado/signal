import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search } from "lucide-react";
import { ArtistCard } from "@/components/signal/ArtistCard";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { queryKeys, useStatusMutation } from "@/store/signal";
import { fetchRecommendations } from "@/api/queries";

export const Route = createFileRoute("/")({
  component: QueuePage,
});

function QueuePage() {
  const [page, setPage] = React.useState(1);
  const [q, setQ] = React.useState("");
  const [genre, setGenre] = React.useState("all");

  const qKey = queryKeys.recommendations(page);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: qKey,
    queryFn: () => fetchRecommendations(page),
  });
  const mutation = useStatusMutation(qKey);

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
  const allGenres = Array.from(new Set(items.flatMap((a) => a.genres))).sort();

  const filtered = items.filter((a) => {
    if (q && !a.name.toLowerCase().includes(q.toLowerCase())) return false;
    if (genre !== "all" && !a.genres.includes(genre)) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="sticky top-12 z-20 -mx-4 grid grid-cols-[1fr_auto_auto] items-center gap-3 border-b border-border-strong bg-panel px-4 py-3 md:-mx-6 md:px-6">
        <div className="relative min-w-0">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="SEARCH ARTIST…"
            className="mono h-9 w-full rounded-none border-border bg-background pl-9 text-[12px] uppercase tracking-[0.12em] placeholder:text-zinc-600"
          />
        </div>
        <div className="w-44">
          <Select value={genre} onValueChange={setGenre}>
            <SelectTrigger className="mono h-9 w-full rounded-none border-border bg-background text-[11px] uppercase tracking-[0.12em]">
              <SelectValue placeholder="GENRE" />
            </SelectTrigger>
            <SelectContent className="mono rounded-none border-border bg-panel text-[11px] uppercase tracking-[0.12em]">
              <SelectItem value="all">ALL GENRES</SelectItem>
              {allGenres.map((g) => (
                <SelectItem key={g} value={g}>
                  {g}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="mono border border-signal-orange bg-signal-orange px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.15em] text-black">
          {filtered.length}/{data?.total ?? 0}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          QUEUE EMPTY.
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
              actions={[
                {
                  label: "FOLLOW",
                  tone: "primary",
                  onClick: () => {
                    mutation.mutate(
                      { id: a.id, status: "FOLLOWING" },
                      {
                        onSuccess: () =>
                          toast("ARTIST.FOLLOWED", { description: a.name.toUpperCase() }),
                      },
                    );
                  },
                },
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

      {data && data.pages > 1 && (
        <div className="mono flex items-center justify-between border-t border-border pt-4 text-[11px] uppercase tracking-[0.15em]">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="border border-border px-3 py-1.5 text-muted-foreground disabled:opacity-30 hover:bg-panel-raised"
          >
            ← PREV
          </button>
          <span className="text-muted-foreground">
            PAGE <span className="text-foreground">{page}</span> / {data.pages}
          </span>
          <button
            disabled={page >= data.pages}
            onClick={() => setPage((p) => p + 1)}
            className="border border-border px-3 py-1.5 text-muted-foreground disabled:opacity-30 hover:bg-panel-raised"
          >
            NEXT →
          </button>
        </div>
      )}
    </div>
  );
}
