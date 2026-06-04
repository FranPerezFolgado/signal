import { apiFetch } from "./client";
import type {
  ArtistListItem,
  ArtistSourcesResponse,
  ArtistStatus,
  ArtistStatusCounts,
  BlacklistRateResponse,
  CalendarResponse,
  DiscoveryHighlightResponse,
  DiscoveryTimelineResponse,
  ExplorationCoverageResponse,
  FingerprintResponse,
  GenreDriftResponse,
  GenreLandscapeResponse,
  GenreStatsResponse,
  LoyalArtistsResponse,
  GenreStreamResponse,
  HeadlineResponse,
  ListeningClockResponse,
  ListeningRatioResponse,
  NoveltyRatioResponse,
  PaginatedResponse,
  PipelineFunnelResponse,
  PipelineStatsResponse,
  PlayVelocityResponse,
  PlaysTrendResponse,
  RecommendationItem,
  ReportsFunnelResponse,
  ScoreBreakdownAverages,
  ScoreDistributionResponse,
  ScoreFreshnessResponse,
  ServiceHealthResponse,
  SourceEffectivenessEntry,
  StaleRecsResponse,
  StreakResponse,
  TopArtistsResponse,
  WeeklyDiscoveriesResponse,
  WeeklyDiscoveryRateResponse,
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

export function fetchFollowingArtists(
  page = 1,
  genre: string | null = null,
  sortBy: "first_seen_at" | "scrobble_count" | "first_play_at" = "first_seen_at",
  order: "asc" | "desc" = "desc",
) {
  const p = new URLSearchParams({
    status: "FOLLOWING",
    page: String(page),
    page_size: String(PAGE_SIZE),
    sort_by: sortBy,
    order,
  });
  if (genre) p.set("genre", genre);
  return apiFetch<PaginatedResponse<ArtistListItem>>(`/v1/artists?${p.toString()}`);
}

export function patchArtistStatus(id: string, status: ArtistStatus) {
  return apiFetch<{ id: string; name: string; status: ArtistStatus }>(`/v1/artists/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function patchArtistSpotify(id: string, spotifyId: string) {
  return apiFetch<{ id: string; name: string }>(`/v1/artists/${id}/spotify`, {
    method: "PATCH",
    body: JSON.stringify({ spotify_id: spotifyId }),
  });
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

export function fetchStatsVelocity() {
  return apiFetch<PlayVelocityResponse>("/v1/stats/velocity");
}

export function fetchStatsBreakdown() {
  return apiFetch<ScoreBreakdownAverages>("/v1/stats/breakdown");
}

export function fetchStatsCoverage() {
  return apiFetch<ExplorationCoverageResponse>("/v1/stats/coverage");
}

export function fetchStatsFunnel() {
  return apiFetch<PipelineFunnelResponse>("/v1/stats/funnel");
}

export function fetchStatsPipeline() {
  return apiFetch<PipelineStatsResponse>("/v1/stats/pipeline");
}

// ─── Reports queries ──────────────────────────────────────────────────────────

function periodParams(fromDate: string | null, toDate: string | null) {
  const p = new URLSearchParams();
  if (fromDate) p.set("from_date", fromDate);
  if (toDate) p.set("to_date", toDate);
  const qs = p.toString();
  return qs ? `?${qs}` : "";
}

export function fetchReportsHeadline(fromDate: string | null, toDate: string | null) {
  return apiFetch<HeadlineResponse>(`/v1/reports/headline${periodParams(fromDate, toDate)}`);
}

export function fetchReportsTopArtists(fromDate: string | null, toDate: string | null) {
  return apiFetch<TopArtistsResponse>(`/v1/reports/top-artists${periodParams(fromDate, toDate)}`);
}

export function fetchReportsPlaysTrend(fromDate: string | null, toDate: string | null) {
  return apiFetch<PlaysTrendResponse>(`/v1/reports/plays-trend${periodParams(fromDate, toDate)}`);
}

export function fetchReportsGenres(fromDate: string | null, toDate: string | null) {
  return apiFetch<GenreLandscapeResponse>(`/v1/reports/genres${periodParams(fromDate, toDate)}`);
}

export function fetchReportsDiscoveryTimeline(fromDate: string | null, toDate: string | null) {
  return apiFetch<DiscoveryTimelineResponse>(
    `/v1/reports/discovery-timeline${periodParams(fromDate, toDate)}`,
  );
}

export function fetchReportsListeningRatio(fromDate: string | null, toDate: string | null) {
  return apiFetch<ListeningRatioResponse>(
    `/v1/reports/listening-ratio${periodParams(fromDate, toDate)}`,
  );
}

export function fetchReportsStreak(fromDate: string | null, toDate: string | null) {
  return apiFetch<StreakResponse>(`/v1/reports/streak${periodParams(fromDate, toDate)}`);
}

export function fetchReportsFunnel(fromDate: string | null, toDate: string | null) {
  return apiFetch<ReportsFunnelResponse>(`/v1/reports/funnel${periodParams(fromDate, toDate)}`);
}

export function fetchReportsListeningClock(fromDate: string | null, toDate: string | null) {
  return apiFetch<ListeningClockResponse>(
    `/v1/reports/listening-clock${periodParams(fromDate, toDate)}`,
  );
}

export function fetchReportsFingerprint(fromDate: string | null, toDate: string | null) {
  return apiFetch<FingerprintResponse>(`/v1/reports/fingerprint${periodParams(fromDate, toDate)}`);
}

export function fetchReportsGenreStream(fromDate: string | null, toDate: string | null) {
  return apiFetch<GenreStreamResponse>(`/v1/reports/genre-stream${periodParams(fromDate, toDate)}`);
}

export function fetchReportsWeeklyDiscoveryRate(fromDate: string | null, toDate: string | null) {
  return apiFetch<WeeklyDiscoveryRateResponse>(
    `/v1/reports/weekly-discovery-rate${periodParams(fromDate, toDate)}`,
  );
}

export function fetchReportsDiscoveryHighlight(fromDate: string | null, toDate: string | null) {
  return apiFetch<DiscoveryHighlightResponse>(
    `/v1/reports/discovery-highlight${periodParams(fromDate, toDate)}`,
  );
}

export function fetchReportsGenreDrift(fromDate: string | null, toDate: string | null) {
  return apiFetch<GenreDriftResponse>(`/v1/reports/genre-drift${periodParams(fromDate, toDate)}`);
}

export function fetchReportsCalendar(fromDate: string | null, toDate: string | null) {
  return apiFetch<CalendarResponse>(`/v1/reports/calendar${periodParams(fromDate, toDate)}`);
}

export function fetchReportsLoyalArtists(fromDate: string | null, toDate: string | null) {
  return apiFetch<LoyalArtistsResponse>(
    `/v1/reports/loyal-artists${periodParams(fromDate, toDate)}`,
  );
}

export function fetchReportsSourceEffectiveness(fromDate: string | null, toDate: string | null) {
  return apiFetch<{ sources: SourceEffectivenessEntry[] }>(
    `/v1/reports/source-effectiveness${periodParams(fromDate, toDate)}`,
  );
}

// --- Stats backlog queries ---

export function fetchStatsBlacklistRate() {
  return apiFetch<BlacklistRateResponse>("/v1/stats/blacklist-rate");
}

export function fetchStatsActiveGenres() {
  return apiFetch<GenreStatsResponse>("/v1/stats/active-genres");
}

export function fetchStatsStaleRecs(thresholdDays = 14) {
  return apiFetch<StaleRecsResponse>(`/v1/stats/stale?threshold_days=${thresholdDays}`);
}

export function fetchStatsScoreFreshness() {
  return apiFetch<ScoreFreshnessResponse>("/v1/stats/score-freshness");
}
