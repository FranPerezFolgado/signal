import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { FaceplatePanel } from "@/components/signal/FaceplatePanel";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchStatsSummary,
  fetchStatsHealth,
  fetchStatsGenres,
  fetchStatsScores,
  fetchStatsDiscoveries,
} from "@/api/queries";

export const Route = createFileRoute("/stats")({
  component: StatsPage,
});

function SectionError({ label, refetch }: { label: string; refetch: () => void }) {
  return (
    <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-signal-red">
      {label} — API UNREACHABLE{" "}
      <button
        onClick={refetch}
        className="underline text-muted-foreground hover:text-foreground ml-2"
      >
        RETRY
      </button>
    </div>
  );
}

function SectionSkeleton() {
  return (
    <div className="space-y-2 p-4">
      <Skeleton className="h-6 w-full" />
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-6 w-1/2" />
    </div>
  );
}

// --- Pipeline Summary ---

function PipelineSummarySection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "summary"],
    queryFn: fetchStatsSummary,
  });

  return (
    <FaceplatePanel slug="04.A" label="PIPELINE">
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="PIPELINE DATA UNAVAILABLE" refetch={refetch} />}
      {data && (
        <div className="grid grid-cols-2 gap-3 p-2">
          {(
            [
              { key: "tracked", label: "TRACKED" },
              { key: "following", label: "FOLLOWING" },
              { key: "published", label: "PUBLISHED" },
              { key: "blacklisted", label: "BLACKLISTED" },
            ] as const
          ).map(({ key, label }) => (
            <div
              key={key}
              className="faceplate flex flex-col items-center justify-center p-3 gap-1"
            >
              <span className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                {label}
              </span>
              <span className="mono text-2xl font-bold tabular-nums">
                {data[key]}
              </span>
            </div>
          ))}
        </div>
      )}
      {data && data.total === 0 && (
        <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO ARTISTS IN PIPELINE
        </div>
      )}
    </FaceplatePanel>
  );
}

// --- Service Health ---

function ServiceHealthSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "health"],
    queryFn: fetchStatsHealth,
  });

  function formatRelative(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  return (
    <FaceplatePanel slug="04.B" label="HEALTH" meta={data ? `STALE > ${data.stale_threshold_minutes}m` : undefined}>
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="HEALTH DATA UNAVAILABLE" refetch={refetch} />}
      {data && data.services.length === 0 && (
        <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO CHECKPOINT DATA
        </div>
      )}
      {data && data.services.length > 0 && (
        <div className="divide-y divide-border">
          {data.services.map((svc) => (
            <div
              key={svc.service}
              className={`flex items-center justify-between px-3 py-2 mono text-[11px] uppercase tracking-[0.12em] ${
                svc.stale ? "text-signal-red" : "text-signal-green"
              }`}
            >
              <span>{svc.service}</span>
              <span className="tabular-nums text-muted-foreground">
                {formatRelative(svc.last_seen_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </FaceplatePanel>
  );
}

// --- Genre Distribution ---

function GenreDistributionSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "genres"],
    queryFn: fetchStatsGenres,
  });

  const maxCount = data ? Math.max(...data.genres.map((g) => g.artist_count), 1) : 1;

  return (
    <FaceplatePanel slug="04.C" label="GENRES">
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="GENRE DATA UNAVAILABLE" refetch={refetch} />}
      {data && data.genres.length === 0 && (
        <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO GENRE DATA AVAILABLE
        </div>
      )}
      {data && data.genres.length > 0 && (
        <div className="divide-y divide-border">
          {data.genres.map((g) => (
            <div key={g.genre} className="flex items-center gap-3 px-3 py-1.5">
              <span className="mono text-[11px] uppercase tracking-[0.12em] text-foreground w-36 truncate flex-shrink-0">
                {g.genre}
              </span>
              <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-signal-orange rounded-full"
                  style={{ width: `${(g.artist_count / maxCount) * 100}%` }}
                />
              </div>
              <span className="mono text-[11px] tabular-nums text-muted-foreground w-8 text-right flex-shrink-0">
                {g.artist_count}
              </span>
            </div>
          ))}
        </div>
      )}
    </FaceplatePanel>
  );
}

// --- Score Distribution ---

function ScoreDistributionSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "scores"],
    queryFn: fetchStatsScores,
  });

  const maxBucketCount = data ? Math.max(...data.buckets.map((b) => b.count), 1) : 1;

  return (
    <FaceplatePanel slug="04.D" label="SCORES">
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="SCORE DATA UNAVAILABLE" refetch={refetch} />}
      {data && data.total_scored === 0 && (
        <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO SCORED ARTISTS YET
        </div>
      )}
      {data && data.total_scored > 0 && (
        <div className="p-3 space-y-3">
          <div className="divide-y divide-border">
            {data.buckets.map((b) => (
              <div key={b.label} className="flex items-center gap-3 py-1.5">
                <span className="mono text-[10px] text-muted-foreground w-20 flex-shrink-0">
                  {b.label}
                </span>
                <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-signal-orange rounded-full"
                    style={{ width: `${(b.count / maxBucketCount) * 100}%` }}
                  />
                </div>
                <span className="mono text-[11px] tabular-nums text-muted-foreground w-6 text-right flex-shrink-0">
                  {b.count}
                </span>
              </div>
            ))}
          </div>
          <div className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground flex gap-4 pt-1">
            <span>MIN {data.min_score?.toFixed(2)}</span>
            <span>MAX {data.max_score?.toFixed(2)}</span>
            <span>MEAN {data.mean_score?.toFixed(2)}</span>
            <span className="ml-auto">{data.total_scored} SCORED</span>
          </div>
        </div>
      )}
    </FaceplatePanel>
  );
}

// --- Weekly Discoveries ---

function WeeklyDiscoveriesSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "discoveries"],
    queryFn: fetchStatsDiscoveries,
  });

  const chartData = data?.weeks.map((w) => ({
    label: new Date(w.week_start + "T00:00:00Z").toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    }),
    count: w.new_artists,
  }));

  return (
    <FaceplatePanel slug="04.E" label="DISCOVERIES / WEEK">
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="DISCOVERIES UNAVAILABLE" refetch={refetch} />}
      {chartData && (
        <div className="p-3 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} barCategoryGap="30%">
              <XAxis
                dataKey="label"
                tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
                width={24}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-panel-raised)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 0,
                  fontFamily: "monospace",
                  fontSize: 10,
                }}
                cursor={{ fill: "var(--color-border)" }}
              />
              <Bar dataKey="count" fill="var(--signal-orange)" name="Artists" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </FaceplatePanel>
  );
}

// --- Page ---

function StatsPage() {
  return (
    <div className="space-y-4 p-4">
      <div className="grid grid-cols-2 gap-4">
        <PipelineSummarySection />
        <ServiceHealthSection />
      </div>
      <GenreDistributionSection />
      <ScoreDistributionSection />
      <WeeklyDiscoveriesSection />
    </div>
  );
}
