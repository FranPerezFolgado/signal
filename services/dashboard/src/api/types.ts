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
