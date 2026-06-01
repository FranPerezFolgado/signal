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

export interface RecommendationItem {
  id: string;
  name: string;
  status: ArtistStatus;
  high_priority: boolean;
  genres: string[];
  score: number;
  breakdown: ScoreBreakdown | null;
  evidence_tracks: string[];
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
