import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { patchArtistSpotify, patchArtistStatus } from "@/api/queries";
import type { ArtistListItem, ArtistStatus, PaginatedResponse, RecommendationItem } from "@/api/types";

export const queryKeys = {
  recommendations: (page: number) => ["recommendations", page] as const,
  tracked: (page: number) => ["tracked", page] as const,
  following: (
    page: number,
    genre: string | null = null,
    sortBy: "first_seen_at" | "scrobble_count" | "first_play_at" = "first_seen_at",
    order: "asc" | "desc" = "desc",
  ) => ["following", page, genre, sortBy, order] as const,
};

type PageData = PaginatedResponse<RecommendationItem | ArtistListItem>;

export function useStatusMutation(queryKey: readonly unknown[]) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ArtistStatus }) =>
      patchArtistStatus(id, status),

    onMutate: async ({ id }) => {
      await qc.cancelQueries({ queryKey });
      const previous = qc.getQueryData<PageData>(queryKey);
      qc.setQueryData<PageData>(queryKey, (old) => {
        if (!old) return old;
        return { ...old, items: old.items.filter((a) => a.id !== id) };
      });
      return { previous };
    },

    onError: (_err, _vars, ctx) => {
      if (ctx?.previous !== undefined) qc.setQueryData(queryKey, ctx.previous);
      toast.error("ACTION FAILED — REVERTED");
    },

    onSettled: () => {
      const category = (queryKey as unknown[])[0];
      qc.invalidateQueries({ queryKey: [category] });
    },
  });
}

export function useSpotifyMutation(queryKey: readonly unknown[]) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ id, spotifyId }: { id: string; spotifyId: string }) =>
      patchArtistSpotify(id, spotifyId),

    onSuccess: (_data, { id, spotifyId }) => {
      type SpotifyPatchable = { id: string; spotify_id?: string | null };
      qc.setQueryData<PaginatedResponse<SpotifyPatchable>>(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((a) =>
            a.id === id ? { ...a, spotify_id: spotifyId } : a,
          ),
        };
      });
      toast("SPOTIFY.UPDATED");
    },

    onError: () => {
      toast.error("SPOTIFY UPDATE FAILED");
    },
  });
}
