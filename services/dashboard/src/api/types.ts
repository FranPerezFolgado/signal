export type ArtistStatus = "TRACKED" | "FOLLOWING" | "PUBLISHED" | "BLACKLISTED";

export interface ScoreBreakdown {
  genre_novelty: number;
  popularity_norm: number;
}

export interface ArtistListItem {
  id: string;
  name: string;
  status: ArtistStatus;
  high_priority: boolean;
  scrobble_count: number;
  genres: string[];
  spotify_id: string | null;
  source: string | null;
  origin_artist_id: string | null;
  origin_artist_name: string | null;
}

export interface EvidenceTrack {
  text: string;
  track_id: string | null;
}

export interface RecommendationItem {
  id: string;
  name: string;
  status: ArtistStatus;
  high_priority: boolean;
  genres: string[];
  score: number;
  breakdown: ScoreBreakdown | null;
  evidence_tracks: EvidenceTrack[];
  spotify_id: string | null;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// --- Stats types ---

export interface ArtistStatusCounts {
  tracked: number;
  following: number;
  published: number;
  blacklisted: number;
  total: number;
}

export interface ServiceCheckpoint {
  service: string;
  last_seen_at: string;
  stale: boolean;
}

export interface ServiceHealthResponse {
  services: ServiceCheckpoint[];
  stale_threshold_minutes: number;
}

export interface GenreCount {
  genre: string;
  artist_count: number;
}

export interface GenreStatsResponse {
  genres: GenreCount[];
}

export interface ScoreBucket {
  label: string;
  min_score: number;
  max_score: number;
  count: number;
}

export interface ScoreDistributionResponse {
  total_scored: number;
  min_score: number | null;
  max_score: number | null;
  mean_score: number | null;
  buckets: ScoreBucket[];
}

export interface WeeklyCount {
  week_start: string;
  new_artists: number;
}

export interface WeeklyDiscoveriesResponse {
  weeks: WeeklyCount[];
}

export interface NoveltyPoint {
  day: string;
  ratio: number;
}

export interface NoveltyRatioResponse {
  points: NoveltyPoint[];
}

export interface SourceCount {
  source: string;
  count: number;
}

export interface ArtistSourcesResponse {
  sources: SourceCount[];
}

export interface PlayVelocityPoint {
  day: string;
  plays: number;
}

export interface PlayVelocityResponse {
  points: PlayVelocityPoint[];
}

export interface ScoreBreakdownAverages {
  avg_genre_novelty: number | null;
  avg_popularity_norm: number | null;
  total: number;
}

export interface ExplorationCoverageResponse {
  total: number;
  explored: number;
  coverage_pct: number;
}

export interface StatusBucket {
  status: string;
  total: number;
  high_priority: number;
}

export interface PipelineFunnelResponse {
  statuses: StatusBucket[];
}

export interface PipelineServiceStat {
  service: string;
  group: string;
  topic: string;
  status: "ACTIVE" | "PROCESSING" | "STALLED" | "IDLE";
  lag: number;
  processed: number;
  consumers: number;
}

export interface PipelineStatsResponse {
  services: PipelineServiceStat[];
}

// --- Reports types ---

export interface HeadlineResponse {
  total_plays: number;
  unique_artists: number;
}

export interface TopArtistEntry {
  rank: number;
  name: string;
  plays: number;
  weight: number;
}

export interface TopArtistsResponse {
  artists: TopArtistEntry[];
}

export interface DailyPlayPoint {
  date: string;
  plays: number;
}

export interface PlaysTrendResponse {
  days: DailyPlayPoint[];
}

export interface GenreEntry {
  genre: string;
  plays: number;
  weight: number;
}

export interface GenreLandscapeResponse {
  genres: GenreEntry[];
}

export interface DiscoveryMonthPoint {
  month: string;
  count: number;
}

export interface DiscoveryTimelineResponse {
  months: DiscoveryMonthPoint[];
}

export interface ListeningRatioResponse {
  familiar_plays: number;
  new_plays: number;
  unknown_plays: number;
  familiar_pct: number;
  new_pct: number;
}

export interface StreakResponse {
  current: number;
  longest: number;
}

export interface FunnelEntry {
  status: string;
  count: number;
}

export interface ReportsFunnelResponse {
  entries: FunnelEntry[];
  period_filtered: boolean;
}

export interface HourlyPlayPoint {
  hour: number;
  plays: number;
}

export interface ListeningClockResponse {
  hours: HourlyPlayPoint[];
}

export interface FingerprintResponse {
  consistency: number;
  variety: number;
  discovery: number;
  night_owl: number;
  depth: number;
}

export interface GenreStreamPoint {
  week_start: string;
  plays: Record<string, number>;
}

export interface GenreStreamResponse {
  top_genres: string[];
  points: GenreStreamPoint[];
}

// --- Stats backlog types ---

export interface BlacklistRateResponse {
  blacklisted: number;
  total_meaningful: number;
  rate: number;
}

export interface StaleRecsResponse {
  count: number;
  threshold_days: number;
  oldest_status_changed_at: string | null;
}

export interface ScoreFreshnessBucket {
  label: string;
  max_age_days: number | null;
  count: number;
}

export interface ScoreFreshnessResponse {
  buckets: ScoreFreshnessBucket[];
}

// --- Reports backlog types ---

export interface WeeklyDiscoveryPoint {
  week_start: string;
  count: number;
}

export interface WeeklyDiscoveryRateResponse {
  weeks: WeeklyDiscoveryPoint[];
}

export interface DiscoveryHighlightResponse {
  available: boolean;
  name: string | null;
  plays: number | null;
  first_seen_at: string | null;
  genres: string[];
  spotify_id: string | null;
}

export interface GenreDriftResponse {
  current: GenreEntry[];
  previous: GenreEntry[];
  period_days: number | null;
}

export interface CalendarDay {
  date: string;
  plays: number;
}

export interface CalendarResponse {
  days: CalendarDay[];
  from_date: string;
  to_date: string;
}

export interface SourceEffectivenessEntry {
  source: string;
  total: number;
  published: number;
  publish_rate: number;
}
