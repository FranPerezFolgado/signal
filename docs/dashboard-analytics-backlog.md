# Dashboard Analytics Backlog

Future stats and reports panels not yet implemented. Ordered roughly by value.

## Stats tab

Stats panels are system/pipeline metrics — no period filter, always reflect current state.

### S1 — Blacklist rate

**What:** Ratio of BLACKLISTED artists vs (BLACKLISTED + FOLLOWING + PUBLISHED) over time, as a gauge or trend line.  
**Why:** Measures scorer signal quality. High blacklist rate means recommendations are noisy; low rate may mean the threshold is too permissive.  
**Data:** `artists` table, `status` column + `updated_at`.  
**API:** New endpoint `GET /v1/stats/blacklist-rate` returning a ratio and optionally a weekly trend series.  
**Query hint:** `SELECT COUNT(*) FILTER (WHERE status='BLACKLISTED') / NULLIF(COUNT(*),0) FROM artists WHERE status != 'TRACKED'`

---

### S2 — Median time-to-follow

**What:** Median and p90 number of days between `first_seen_at` and the artist being moved to FOLLOWING.  
**Why:** Measures how long good artists sit in the queue. A rising median means the queue is getting backed up.  
**Data:** Need to record a `followed_at` timestamp, or approximate using the `updated_at` of status transitions. Currently no explicit transition log exists.  
**Note:** Would benefit from an `artist_status_log` table (artist_id, old_status, new_status, changed_at). Worth adding as a migration.  
**API:** `GET /v1/stats/time-to-follow` → `{ median_days, p90_days, sample_size }`

---

### S3 — Active pipeline genre distribution

**What:** Genre breakdown filtered to TRACKED and FOLLOWING artists only (not all artists).  
**Why:** Shows what's actively in the pipeline right now, distinct from all-time genre history.  
**Data:** `artists` table filtered by `status IN ('TRACKED','FOLLOWING')`, `genres` column (jsonb array).  
**API:** Extend existing `GET /v1/stats/genres` with an optional `?status=TRACKED,FOLLOWING` query param, or add a dedicated endpoint.

---

### S4 — Stale recommendations

**What:** Count (and optionally list) of artists that have been TRACKED for more than N days without any status change.  
**Why:** Actionable queue health indicator — tells you the queue is piling up with undecided artists.  
**Data:** `artists` table: `status='TRACKED'` AND `updated_at < now() - interval 'N days'`.  
**API:** `GET /v1/stats/stale` → `{ count, threshold_days, oldest_seen_at }`. The threshold should be configurable (default 14d).

---

### S5 — Score decay / stagnation

**What:** Distribution of recommendation `updated_at` ages — how many scored artists haven't been re-scored in >7d, >30d, etc.  
**Why:** Stale scores mean the scorer isn't keeping up, or artists are sitting un-explored.  
**Data:** `artist_recommendations.updated_at`.  
**API:** `GET /v1/stats/score-freshness` → `{ buckets: [{label, max_age_days, count}] }`

---

## Reports tab

Reports panels are personal listening analytics — all support the period selector (7d / 30d / 90d / ytd / all time).

### R1 — New artist discovery rate (weekly trend)

**What:** Line chart of new artists discovered per week within the selected period. Different from the existing discovery timeline (monthly) — this is weekly granularity and is a rate, not cumulative.  
**Why:** Shows acceleration/deceleration in discovery activity. A plateau means the ingester is slowing down or your listening has narrowed.  
**Data:** `artists.first_seen_at` grouped by ISO week.  
**API:** Extend or parallel to existing `GET /v1/reports/discovery-timeline` with `?granularity=week`.

---

### R2 — Discovery highlight ("Artist of the period")

**What:** A single highlight card showing the artist you played most that you first discovered within the current period.  
**Why:** "Discovery of the month/year" — a narrative anchor like Last.fm annual reports.  
**Data:** JOIN `listening_history` plays with `artists.first_seen_at` filtered to the period, ranked by play count.  
**API:** `GET /v1/reports/discovery-highlight` → `{ name, plays, first_seen_at, genres, spotify_id }`  
**UI:** Standalone hero card above the top-artists list, shown only when data is available (not for "all time").

---

### R3 — Genre drift

**What:** Side-by-side comparison of top 5 genres this period vs the previous equivalent period (e.g. last 30d vs the 30d before that). Show delta as +/- indicators.  
**Why:** The most interesting stat for understanding whether your listening is broadening or narrowing.  
**Data:** Two date ranges computed from the selected period. Same genre-plays query run twice.  
**API:** `GET /v1/reports/genre-drift` → `{ current: GenreEntry[], previous: GenreEntry[] }` with period params.  
**Note:** Needs two period params or a server-side "previous period" computation. Simplest: pass both `from_date`/`to_date` and a `compare=true` flag.

---

### R4 — Listening calendar heatmap

**What:** GitHub-style calendar grid (52 weeks × 7 days) coloured by play count per day.  
**Why:** Best visualisation for listening consistency and patterns — immediately shows gaps, binges, and streaks.  
**Data:** `listening_history` grouped by date, play count per day.  
**API:** `GET /v1/reports/calendar` → `{ days: [{date, plays}] }` (full year for the heatmap, period filter optional).  
**UI:** Full-width panel. Use a custom SVG/div grid — Recharts doesn't have a heatmap. Each cell is a small square coloured on a 5-bucket scale (0 / 1-3 / 4-9 / 10-19 / 20+).

---

### R5 — Artist loyalty

**What:** List of artists you've been playing consistently for >6 months, ranked by total plays within the period.  
**Why:** Counterpart to the discovery-focused panels — highlights long-term favourites vs new finds.  
**Data:** `artists.first_seen_at < now() - interval '6 months'` JOIN `listening_history` plays within period.  
**API:** `GET /v1/reports/loyal-artists` → same shape as `top-artists` but filtered to veteran artists.  
**UI:** Can reuse the TopArtistsPanel component with a different label.

---

### R6 — Discovery source effectiveness

**What:** For artists that reached PUBLISHED status, break down by their discovery `source` (LASTFM_SIMILAR, SPOTIFY_RELATED, MANUAL, etc.).  
**Why:** Tells you which pipeline branch is actually producing published artists, not just candidates.  
**Data:** `artists` table: `status='PUBLISHED'`, `source` column, filtered by period if `first_seen_at` is in range.  
**API:** `GET /v1/reports/source-effectiveness` → `{ sources: [{source, total, published, publish_rate}] }`  
**UI:** Horizontal bar or donut chart. Could sit alongside the existing curation funnel.

---

## Implementation notes

- R4 (heatmap) is the highest visual impact, requires a custom renderer.
- S2 (time-to-follow) needs a schema migration for accurate data; skip until the status log table is added.
- R3 (genre drift) and R6 (source effectiveness) share infrastructure with existing reports — lowest backend effort.
- S1 (blacklist rate) and S4 (stale recs) are single-query additions, very low effort.
- All new endpoints should follow the existing pattern: router in `routers/`, query in `repositories/stats_repository.py` or `reports_repository.py`, models in `models.py`, TypeScript types in `api/types.ts`.
