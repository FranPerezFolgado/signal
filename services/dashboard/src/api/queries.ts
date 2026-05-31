import { apiFetch } from "./client";
import type { ArtistListItem, ArtistStatus, PaginatedResponse, RecommendationItem } from "./types";

export const PAGE_SIZE = 50;

export function fetchRecommendations(page = 1) {
  return apiFetch<PaginatedResponse<RecommendationItem>>(
    `/v1/recommendations?page=${page}&page_size=${PAGE_SIZE}`,
  );
}

export function fetchTrackedArtists(page = 1) {
  return apiFetch<PaginatedResponse<ArtistListItem>>(
    `/v1/artists?status=TRACKED&page=${page}&page_size=${PAGE_SIZE}`,
  );
}

export function fetchFollowingArtists(page = 1) {
  return apiFetch<PaginatedResponse<ArtistListItem>>(
    `/v1/artists?status=FOLLOWING&page=${page}&page_size=${PAGE_SIZE}`,
  );
}

export function patchArtistStatus(id: string, status: ArtistStatus) {
  return apiFetch<{ id: string; name: string; status: ArtistStatus }>(
    `/v1/artists/${id}/status`,
    { method: "PATCH", body: JSON.stringify({ status }) },
  );
}
