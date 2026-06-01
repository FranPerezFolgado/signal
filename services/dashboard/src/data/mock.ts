export type Source = "spotify" | "lastfm" | "bandcamp" | "rss";

export type EvidenceTrack = {
  id: string;
  title: string;
  source: Source;
  playedAt: string;
};

export type ScoreBreakdown = {
  novelty: number;
  genre_fit: number;
  graph: number;
  velocity: number;
};

export type Artist = {
  id: string;
  name: string;
  score: number;
  breakdown: ScoreBreakdown;
  genres: string[];
  sources: Source[];
  evidence: EvidenceTrack[];
  high_priority?: boolean;
  added_days_ago?: number;
  recent_tracks?: number;
  last_seen?: string;
};

const GENRES = [
  "ambient",
  "shoegaze",
  "post-punk",
  "drum & bass",
  "hyperpop",
  "footwork",
  "dub techno",
  "modular",
  "jazz fusion",
  "kosmische",
  "noise",
  "uk garage",
  "vapor",
  "deconstructed club",
  "post-rock",
  "industrial",
];

const SOURCES: Source[] = ["spotify", "lastfm", "bandcamp", "rss"];

const ARTIST_NAMES = [
  "Akira Kosemura", "Loraine James", "Hiroshi Yoshimura", "Nala Sinephro",
  "Galya Bisengalieva", "Cucina Povera", "Pavel Milyakov", "Astrid Sonne",
  "Caterina Barbieri", "Beatrice Dillon", "Kali Malone", "Klein",
  "Toma Kami", "Upsammy", "Lyra Pramuk", "Iceboy Violet",
  "Ehua", "Object Blue", "Florentino", "Aya",
  "Bambii", "Crystallmess", "DJ Manny", "Coby Sey",
  "Sofia Kourtesis", "Tirzah", "Felisha Ledesma", "Yu Su",
];

const TRACK_TITLES = [
  "Liminal Drift", "Phase Cascade", "Soft Granite", "Null Field",
  "Velvet Aperture", "Iridium Hum", "Magnetic North", "Static Bloom",
  "Cobalt Pulse", "Halocline", "Ferrite Loop", "Quiet Reactor",
  "Slip Stream", "Inner Drone", "Hex Lattice", "Carrier Wave",
];

const rand = (seed: number) => {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
};

function pick<T>(arr: T[], r: () => number): T {
  return arr[Math.floor(r() * arr.length)];
}

function buildArtists(count: number, offset = 0, seedBase = 1): Artist[] {
  const r = rand(seedBase);
  return Array.from({ length: count }, (_, i) => {
    const name = ARTIST_NAMES[(offset + i) % ARTIST_NAMES.length];
    const novelty = +(0.4 + r() * 0.6).toFixed(2);
    const genre_fit = +(0.3 + r() * 0.7).toFixed(2);
    const graph = +(0.2 + r() * 0.8).toFixed(2);
    const velocity = +(0.1 + r() * 0.9).toFixed(2);
    const score = Math.round(
      (novelty * 0.4 + genre_fit * 0.25 + graph * 0.2 + velocity * 0.15) * 100,
    );
    const genres = Array.from({ length: 1 + Math.floor(r() * 3) }, () => pick(GENRES, r));
    const sources = Array.from({ length: 1 + Math.floor(r() * 2) }, () => pick(SOURCES, r));
    const evidence: EvidenceTrack[] = Array.from(
      { length: 2 + Math.floor(r() * 3) },
      (_, j) => ({
        id: `${name}-t${j}`,
        title: pick(TRACK_TITLES, r),
        source: pick(SOURCES, r),
        playedAt: `${Math.floor(r() * 23)}:${String(Math.floor(r() * 60)).padStart(2, "0")}`,
      }),
    );
    return {
      id: `${name}-${offset + i}`,
      name,
      score,
      breakdown: { novelty, genre_fit, graph, velocity },
      genres: Array.from(new Set(genres)),
      sources: Array.from(new Set(sources)),
      evidence,
      high_priority: score >= 78,
      added_days_ago: Math.floor(r() * 60),
      recent_tracks: Math.floor(r() * 12),
      last_seen: `${Math.floor(r() * 48)}h`,
    };
  }).sort((a, b) => b.score - a.score);
}

export const MOCK_QUEUE: Artist[] = buildArtists(22, 0, 11);
export const MOCK_FOLLOWING: Artist[] = buildArtists(14, 7, 91);

export const ALL_GENRES = GENRES;
export const ALL_SOURCES = SOURCES;

// Exploration
export const DETECTED_GENRES: { name: string; count: number; delta: number }[] = [
  { name: "deconstructed club", count: 42, delta: 12 },
  { name: "ambient", count: 38, delta: 5 },
  { name: "modular", count: 31, delta: 9 },
  { name: "hyperpop", count: 27, delta: -3 },
  { name: "footwork", count: 24, delta: 7 },
  { name: "dub techno", count: 22, delta: 2 },
  { name: "post-punk", count: 19, delta: 1 },
  { name: "kosmische", count: 17, delta: 4 },
  { name: "noise", count: 14, delta: -1 },
  { name: "shoegaze", count: 13, delta: 6 },
  { name: "uk garage", count: 12, delta: 3 },
  { name: "industrial", count: 10, delta: 2 },
  { name: "vapor", count: 9, delta: -2 },
  { name: "jazz fusion", count: 8, delta: 1 },
];

export const GRAPH_DISCOVERIES: { artist: string; via: string; depth: number; score: number }[] = [
  { artist: "Klein", via: "Loraine James", depth: 1, score: 82 },
  { artist: "Object Blue", via: "Aya", depth: 2, score: 74 },
  { artist: "Astrid Sonne", via: "Caterina Barbieri", depth: 1, score: 79 },
  { artist: "Ehua", via: "Crystallmess", depth: 2, score: 68 },
  { artist: "Toma Kami", via: "Florentino", depth: 1, score: 71 },
  { artist: "Upsammy", via: "Beatrice Dillon", depth: 2, score: 66 },
  { artist: "Coby Sey", via: "Tirzah", depth: 1, score: 77 },
  { artist: "Yu Su", via: "Sofia Kourtesis", depth: 2, score: 64 },
];

// Stats
export const NOVELTY_RATIO = Array.from({ length: 30 }, (_, i) => {
  const r = rand(i + 3)();
  return {
    day: `D-${29 - i}`,
    ratio: +(0.3 + Math.sin(i / 4) * 0.15 + r * 0.1).toFixed(2),
  };
});

export const ARTISTS_PER_WEEK = Array.from({ length: 12 }, (_, i) => ({
  week: `W${i + 1}`,
  count: 4 + Math.floor(rand(i + 50)() * 18),
}));

export const SOURCE_SHARE = [
  { name: "spotify", value: 142 },
  { name: "lastfm", value: 88 },
  { name: "bandcamp", value: 67 },
  { name: "rss", value: 31 },
];

export const SCORE_DISTRIBUTION = [
  { bucket: "0-20", count: 4 },
  { bucket: "20-40", count: 11 },
  { bucket: "40-60", count: 28 },
  { bucket: "60-80", count: 47 },
  { bucket: "80-100", count: 19 },
];
