import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArtistCard } from "@/components/signal/ArtistCard";
import { queryKeys, useStatusMutation } from "@/store/signal";
import { fetchFollowingArtists } from "@/api/queries";
import { Pagination } from "@/components/signal/Pagination";

export const Route = createFileRoute("/following")({
  component: FollowingPage,
});

function FollowingPage() {
  const [page, setPage] = React.useState(1);
  const qKey = queryKeys.following(page);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: qKey,
    queryFn: () => fetchFollowingArtists(page),
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

  return (
    <div className="space-y-4">
      <div className="mono border-b border-border-strong pb-3 text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
        TRACKING <span className="text-foreground">{data?.total ?? 0}</span> ARTISTS
      </div>

      {items.length === 0 ? (
        <div className="faceplate mono p-8 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO ACTIVE TRACKING. PROMOTE FROM QUEUE.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((a) => (
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
