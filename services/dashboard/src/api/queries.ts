import { apiFetch } from "./client";
import type {
  ArtistListItem,
  ArtistSourcesResponse,
  ArtistStatus,
  ArtistStatusCounts,
  GenreStatsResponse,
  NoveltyRatioResponse,
  PaginatedResponse,
  RecommendationItem,
  ScoreDistributionResponse,
  ServiceHealthResponse,
  WeeklyDiscoveriesResponse,
} from "./types";

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

export function fetchStatsSummary() {
  return apiFetch<ArtistStatusCounts>("/v1/stats/summary");
}

export function fetchStatsHealth() {
  return apiFetch<ServiceHealthResponse>("/v1/stats/health");
}

export function fetchStatsGenres() {
  return apiFetch<GenreStatsResponse>("/v1/stats/genres");
}

export function fetchStatsScores() {
  return apiFetch<ScoreDistributionResponse>("/v1/stats/scores");
}

export function fetchStatsDiscoveries() {
  return apiFetch<WeeklyDiscoveriesResponse>("/v1/stats/discoveries");
}

export function fetchStatsNovelty() {
  return apiFetch<NoveltyRatioResponse>("/v1/stats/novelty");
}

export function fetchStatsSources() {
  return apiFetch<ArtistSourcesResponse>("/v1/stats/sources");
}
