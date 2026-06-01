import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { FaceplatePanel } from "@/components/signal/FaceplatePanel";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchStatsBreakdown,
  fetchStatsCoverage,
  fetchStatsDiscoveries,
  fetchStatsFunnel,
  fetchStatsHealth,
  fetchStatsNovelty,
  fetchStatsScores,
  fetchStatsSources,
  fetchStatsVelocity,
} from "@/api/queries";

export const Route = createFileRoute("/stats")({
  component: StatsPage,
});

const CHART_HEIGHT = 220;

const TOOLTIP_STYLE = {
  background: "var(--color-panel-raised)",
  border: "1px solid var(--color-border)",
  borderRadius: 0,
  fontFamily: "monospace",
  fontSize: 10,
};

function MetaBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
      {children}
    </span>
  );
}

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

function SectionSkeleton({ height = CHART_HEIGHT }: { height?: number }) {
  return (
    <div className="p-4">
      <Skeleton style={{ height }} className="w-full" />
    </div>
  );
}

// ─── Service Health Strip ─────────────────────────────────────────────────────

function ServiceHealthStrip() {
  const { data, isError } = useQuery({
    queryKey: ["stats", "health"],
    queryFn: fetchStatsHealth,
  });

  if (isError) return null;
  if (!data || data.services.length === 0) return null;

  function formatRelative(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  return (
    <div className="faceplate flex items-center gap-6 px-4 py-2">
      {data.services.map((svc) => (
        <div key={svc.service} className="flex items-center gap-2">
          <div
            className={`w-1.5 h-1.5 rounded-full ${svc.stale ? "bg-signal-red" : "bg-signal-green"}`}
          />
          <span className="mono text-[10px] uppercase tracking-[0.14em] text-foreground">
            {svc.service}
          </span>
          <span className="mono text-[10px] text-muted-foreground tabular-nums">
            {formatRelative(svc.last_seen_at)}
          </span>
        </div>
      ))}
      <span className="mono text-[9px] text-muted-foreground ml-auto tracking-[0.12em]">
        STALE &gt; {data.stale_threshold_minutes}m
      </span>
    </div>
  );
}

// ─── Novelty Ratio ────────────────────────────────────────────────────────────

function NoveltyRatioSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "novelty"],
    queryFn: fetchStatsNovelty,
  });

  const chartData = data?.points.map((p, i) => ({
    label: `D-${data.points.length - 1 - i}`,
    ratio: p.ratio,
  }));

  return (
    <FaceplatePanel slug="04.A" label="NOVELTY RATIO" meta={<MetaBadge>30D</MetaBadge>}>
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="NOVELTY DATA UNAVAILABLE" refetch={refetch} />}
      {chartData && (
        <div className="px-2 pb-2" style={{ height: CHART_HEIGHT }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
                interval={4}
              />
              <YAxis
                domain={[0, 1]}
                tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
                width={28}
                tickCount={5}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                cursor={{ stroke: "var(--color-border)" }}
                formatter={(v: number) => [v.toFixed(3), "ratio"]}
              />
              <Line
                type="monotone"
                dataKey="ratio"
                stroke="var(--signal-orange)"
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3, fill: "var(--signal-orange)" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── New Artists Per Week ─────────────────────────────────────────────────────

function WeeklyDiscoveriesSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "discoveries"],
    queryFn: fetchStatsDiscoveries,
  });

  const chartData = data?.weeks.map((w, i) => ({
    label: `W${i + 1}`,
    count: w.new_artists,
  }));

  return (
    <FaceplatePanel slug="04.B" label="NEW ARTISTS PER WEEK" meta={<MetaBadge>12W</MetaBadge>}>
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="DISCOVERIES UNAVAILABLE" refetch={refetch} />}
      {chartData && (
        <div className="px-2 pb-2" style={{ height: CHART_HEIGHT }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} barCategoryGap="20%">
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
                width={28}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                cursor={{ fill: "var(--color-border)" }}
                formatter={(v: number) => [v, "artists"]}
              />
              <Bar dataKey="count" fill="var(--signal-orange)" radius={[1, 1, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── Most Active Sources ──────────────────────────────────────────────────────

const SOURCE_COLORS = [
  "var(--signal-orange)",
  "hsl(0 0% 60%)",
  "hsl(0 0% 45%)",
  "hsl(0 0% 32%)",
  "hsl(0 0% 22%)",
];

function ArtistSourcesSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "sources"],
    queryFn: fetchStatsSources,
  });

  const total = data?.sources.reduce((s, x) => s + x.count, 0) ?? 0;

  return (
    <FaceplatePanel slug="04.C" label="MOST ACTIVE SOURCES">
      {isLoading && <SectionSkeleton height={260} />}
      {isError && <SectionError label="SOURCE DATA UNAVAILABLE" refetch={refetch} />}
      {data && data.sources.length === 0 && (
        <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO SOURCE DATA
        </div>
      )}
      {data && data.sources.length > 0 && (
        <div className="flex items-center justify-center gap-12 px-8 py-4" style={{ height: 260 }}>
          <PieChart width={200} height={200}>
            <Pie
              data={data.sources}
              dataKey="count"
              nameKey="source"
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={95}
              strokeWidth={0}
            >
              {data.sources.map((_, i) => (
                <Cell key={i} fill={SOURCE_COLORS[i % SOURCE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [v, "artists"]} />
          </PieChart>
          <div className="flex flex-col gap-2.5 min-w-[160px]">
            {data.sources.map((s, i) => (
              <div key={s.source} className="flex items-center gap-2.5">
                <div
                  className="w-3 h-3 flex-shrink-0"
                  style={{ background: SOURCE_COLORS[i % SOURCE_COLORS.length] }}
                />
                <span className="mono text-[11px] uppercase tracking-[0.12em] text-foreground flex-1 truncate">
                  {s.source.replace(/^spotify.*/i, "SPOTIFY").toUpperCase()}
                </span>
                <span className="mono text-[11px] tabular-nums text-muted-foreground">
                  {total > 0 ? Math.round((s.count / total) * 100) : 0}%
                </span>
                <span className="mono text-[11px] tabular-nums text-foreground w-10 text-right">
                  {s.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── Score Distribution ───────────────────────────────────────────────────────

const SCORE_COLORS = [
  "hsl(0 60% 38%)",        // 0–20  dark red
  "hsl(0 0% 42%)",         // 20–40 gray
  "hsl(38 75% 52%)",       // 40–60 amber
  "hsl(142 45% 44%)",      // 60–80 green
  "var(--signal-orange)",  // 80–100 orange
];

function ScoreDistributionSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "scores"],
    queryFn: fetchStatsScores,
  });

  return (
    <FaceplatePanel
      slug="04.D"
      label="SCORE DISTRIBUTION"
      meta={data && data.total_scored > 0 ? <MetaBadge>N={data.total_scored}</MetaBadge> : undefined}
    >
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="SCORE DATA UNAVAILABLE" refetch={refetch} />}
      {data && data.total_scored === 0 && (
        <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO SCORED ARTISTS YET
        </div>
      )}
      {data && data.total_scored > 0 && (
        <div className="px-2 pb-2" style={{ height: CHART_HEIGHT }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.buckets} barCategoryGap="20%">
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
                width={28}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                cursor={{ fill: "var(--color-border)" }}
                formatter={(v: number) => [v, "artists"]}
              />
              <Bar dataKey="count" radius={[1, 1, 0, 0]}>
                {data.buckets.map((_, i) => (
                  <Cell key={i} fill={SCORE_COLORS[i % SCORE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── Pipeline Funnel ──────────────────────────────────────────────────────────

const STATUS_ORDER = ["TRACKED", "FOLLOWING", "PUBLISHED", "BLACKLISTED"];
const STATUS_COLORS: Record<string, string> = {
  TRACKED: "var(--signal-orange)",
  FOLLOWING: "hsl(142 45% 44%)",
  PUBLISHED: "hsl(210 60% 52%)",
  BLACKLISTED: "hsl(0 0% 35%)",
};

function PipelineFunnelSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "funnel"],
    queryFn: fetchStatsFunnel,
  });

  const sorted = data
    ? [...data.statuses].sort(
        (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)
      )
    : [];

  const maxTotal = sorted.length > 0 ? Math.max(...sorted.map((s) => s.total), 1) : 1;

  return (
    <FaceplatePanel slug="04.E" label="PIPELINE FUNNEL">
      {isLoading && <SectionSkeleton height={160} />}
      {isError && <SectionError label="FUNNEL DATA UNAVAILABLE" refetch={refetch} />}
      {data && sorted.length > 0 && (
        <div className="p-4 space-y-3">
          {sorted.map((s) => {
            const color = STATUS_COLORS[s.status] ?? "hsl(0 0% 40%)";
            const pct = (s.total / maxTotal) * 100;
            return (
              <div key={s.status} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                    {s.status}
                  </span>
                  <div className="flex items-center gap-3">
                    {s.high_priority > 0 && (
                      <span className="mono text-[9px] tracking-[0.1em] text-muted-foreground">
                        ★ {s.high_priority}
                      </span>
                    )}
                    <span className="mono text-[11px] tabular-nums text-foreground">
                      {s.total.toLocaleString()}
                    </span>
                  </div>
                </div>
                <div className="h-1 bg-border rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, background: color }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── Score Factor Breakdown ───────────────────────────────────────────────────

function ScoreBreakdownSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "breakdown"],
    queryFn: fetchStatsBreakdown,
  });

  const factors =
    data && data.avg_genre_novelty != null && data.avg_popularity_norm != null
      ? [
          { label: "GENRE NOVELTY", value: data.avg_genre_novelty, color: "var(--signal-orange)" },
          { label: "POPULARITY", value: data.avg_popularity_norm, color: "hsl(142 45% 44%)" },
        ]
      : null;

  return (
    <FaceplatePanel
      slug="04.F"
      label="SCORE FACTORS"
      meta={data && data.total > 0 ? <MetaBadge>N={data.total}</MetaBadge> : undefined}
    >
      {isLoading && <SectionSkeleton height={120} />}
      {isError && <SectionError label="BREAKDOWN UNAVAILABLE" refetch={refetch} />}
      {data && data.total === 0 && (
        <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          NO SCORED ARTISTS YET
        </div>
      )}
      {factors && (
        <div className="p-4 space-y-4">
          {factors.map((f) => (
            <div key={f.label} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  {f.label}
                </span>
                <span className="mono text-[13px] tabular-nums font-bold" style={{ color: f.color }}>
                  {f.value.toFixed(1)}
                </span>
              </div>
              <div className="h-2 bg-border rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.min(f.value, 100)}%`, background: f.color }}
                />
              </div>
            </div>
          ))}
          <p className="mono text-[9px] text-muted-foreground tracking-[0.1em] pt-1">
            AVERAGE COMPONENT SCORE (0–100) ACROSS {data?.total} SCORED ARTISTS
          </p>
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── Play Velocity ────────────────────────────────────────────────────────────

function PlayVelocitySection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "velocity"],
    queryFn: fetchStatsVelocity,
  });

  const chartData = data?.points.map((p, i) => ({
    label: i % 5 === 0 ? `D-${data.points.length - 1 - i}` : "",
    plays: p.plays,
  }));

  const totalPlays = data?.points.reduce((s, p) => s + p.plays, 0) ?? 0;

  return (
    <FaceplatePanel
      slug="04.G"
      label="PLAY VELOCITY"
      meta={<MetaBadge>30D</MetaBadge>}
    >
      {isLoading && <SectionSkeleton />}
      {isError && <SectionError label="VELOCITY DATA UNAVAILABLE" refetch={refetch} />}
      {chartData && (
        <div>
          <div className="px-2 pb-2" style={{ height: CHART_HEIGHT }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barCategoryGap="10%">
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
                  width={36}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  cursor={{ fill: "var(--color-border)" }}
                  formatter={(v: number) => [v.toLocaleString(), "plays"]}
                />
                <Bar dataKey="plays" fill="var(--signal-orange)" radius={[1, 1, 0, 0]} opacity={0.85} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground flex gap-4 px-4 pb-3">
            <span>{totalPlays.toLocaleString()} TOTAL PLAYS</span>
            <span className="ml-auto">{Math.round(totalPlays / 30)} AVG/DAY</span>
          </div>
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── Exploration Coverage ─────────────────────────────────────────────────────

function ExplorationCoverageSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stats", "coverage"],
    queryFn: fetchStatsCoverage,
  });

  return (
    <FaceplatePanel slug="04.H" label="EXPLORATION COVERAGE">
      {isLoading && <SectionSkeleton height={120} />}
      {isError && <SectionError label="COVERAGE DATA UNAVAILABLE" refetch={refetch} />}
      {data && (
        <div className="p-4 space-y-4">
          <div className="flex items-end gap-3">
            <span className="mono text-4xl font-bold tabular-nums text-foreground">
              {data.coverage_pct.toFixed(1)}
            </span>
            <span className="mono text-lg text-muted-foreground mb-1">%</span>
            <span className="mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2 ml-1">
              explored
            </span>
          </div>
          <div className="h-2 bg-border rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-signal-orange"
              style={{ width: `${data.coverage_pct}%` }}
            />
          </div>
          <div className="mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground flex justify-between">
            <span>{data.explored.toLocaleString()} EXPLORED</span>
            <span>{(data.total - data.explored).toLocaleString()} PENDING</span>
          </div>
          <p className="mono text-[9px] text-muted-foreground tracking-[0.1em]">
            FOLLOWING ARTISTS WITH SIMILAR-ARTIST EXPANSION COMPLETE
          </p>
        </div>
      )}
    </FaceplatePanel>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function StatsPage() {
  return (
    <div className="p-4 space-y-4">
      <ServiceHealthStrip />
      <div className="grid grid-cols-2 gap-4">
        <NoveltyRatioSection />
        <WeeklyDiscoveriesSection />
        <ArtistSourcesSection />
        <ScoreDistributionSection />
        <PipelineFunnelSection />
        <ScoreBreakdownSection />
        <PlayVelocitySection />
        <ExplorationCoverageSection />
      </div>
    </div>
  );
}
