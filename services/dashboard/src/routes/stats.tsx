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
  fetchStatsDiscoveries,
  fetchStatsNovelty,
  fetchStatsScores,
  fetchStatsSources,
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

// --- Novelty Ratio ---

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

// --- New Artists Per Week ---

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

// --- Most Active Sources ---

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
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(v: number) => [v, "artists"]}
            />
          </PieChart>
          <div className="flex flex-col gap-2.5 min-w-[160px]">
            {data.sources.map((s, i) => (
              <div key={s.source} className="flex items-center gap-2.5">
                <div
                  className="w-3 h-3 flex-shrink-0"
                  style={{ background: SOURCE_COLORS[i % SOURCE_COLORS.length] }}
                />
                <span className="mono text-[11px] uppercase tracking-[0.12em] text-foreground flex-1 truncate">
                  {s.source.replace(/^spotify.*/, "SPOTIFY").toUpperCase()}
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

// --- Score Distribution ---

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

// --- Page ---

function StatsPage() {
  return (
    <div className="p-4 grid grid-cols-2 gap-4">
      <NoveltyRatioSection />
      <WeeklyDiscoveriesSection />
      <ArtistSourcesSection />
      <ScoreDistributionSection />
    </div>
  );
}
