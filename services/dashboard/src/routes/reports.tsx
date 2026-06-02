import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { FaceplatePanel } from "@/components/signal/FaceplatePanel";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  fetchReportsHeadline,
  fetchReportsTopArtists,
  fetchReportsPlaysTrend,
  fetchReportsGenres,
  fetchReportsDiscoveryTimeline,
  fetchReportsListeningRatio,
  fetchReportsStreak,
  fetchReportsFunnel,
} from "@/api/queries";

export const Route = createFileRoute("/reports")({
  component: ReportsPage,
});

// ─── Period selector ──────────────────────────────────────────────────────────

type Period = "all" | "30d" | "90d" | "ytd";

const PERIODS: { id: Period; label: string }[] = [
  { id: "all", label: "ALL TIME" },
  { id: "30d", label: "LAST 30D" },
  { id: "90d", label: "LAST 90D" },
  { id: "ytd", label: "THIS YEAR" },
];

function usePeriodDates(period: Period): { fromDate: string | null; toDate: string | null } {
  const today = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const fmt = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const toDate = fmt(today);

  if (period === "all") return { fromDate: null, toDate: null };

  if (period === "30d") {
    const from = new Date(today);
    from.setDate(from.getDate() - 30);
    return { fromDate: fmt(from), toDate };
  }
  if (period === "90d") {
    const from = new Date(today);
    from.setDate(from.getDate() - 90);
    return { fromDate: fmt(from), toDate };
  }
  // ytd
  return { fromDate: `${today.getFullYear()}-01-01`, toDate };
}

function PeriodSelector({
  value,
  onChange,
}: {
  value: Period;
  onChange: (p: Period) => void;
}) {
  return (
    <div className="flex gap-0">
      {PERIODS.map((p) => (
        <button
          key={p.id}
          onClick={() => onChange(p.id)}
          className={cn(
            "mono border border-border px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] transition-colors -ml-px first:ml-0",
            value === p.id
              ? "bg-signal-orange text-black border-signal-orange z-10"
              : "text-muted-foreground hover:text-foreground hover:bg-panel-raised",
          )}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

const CHART_HEIGHT = 180;

const TOOLTIP_STYLE = {
  background: "var(--color-panel-raised)",
  border: "1px solid var(--color-border)",
  borderRadius: 0,
  fontFamily: "monospace",
  fontSize: 10,
};

function SectionSkeleton({ height = CHART_HEIGHT }: { height?: number }) {
  return (
    <div className="p-4">
      <Skeleton style={{ height }} className="w-full" />
    </div>
  );
}

function SectionError({ label, refetch }: { label: string; refetch: () => void }) {
  return (
    <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-signal-red">
      {label} —{" "}
      <button onClick={refetch} className="underline text-muted-foreground hover:text-foreground">
        RETRY
      </button>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="mono p-6 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
      {label}
    </div>
  );
}

// ─── Headline panel ───────────────────────────────────────────────────────────

function HeadlinePanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "headline", fromDate, toDate],
    queryFn: () => fetchReportsHeadline(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={72} />;
  if (isError) return <SectionError label="HEADLINE UNAVAILABLE" refetch={refetch} />;

  return (
    <div className="flex gap-8 p-4">
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          TOTAL PLAYS
        </div>
        <div className="mt-1 font-mono text-3xl font-bold tabular-nums text-foreground">
          {(data?.total_plays ?? 0).toLocaleString()}
        </div>
      </div>
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          UNIQUE ARTISTS
        </div>
        <div className="mt-1 font-mono text-3xl font-bold tabular-nums text-foreground">
          {(data?.unique_artists ?? 0).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

// ─── Top artists panel ────────────────────────────────────────────────────────

function TopArtistsPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "top-artists", fromDate, toDate],
    queryFn: () => fetchReportsTopArtists(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton />;
  if (isError) return <SectionError label="TOP ARTISTS UNAVAILABLE" refetch={refetch} />;
  if (!data || data.artists.length === 0) return <Empty label="NO PLAYS IN PERIOD" />;

  return (
    <div className="divide-y divide-border">
      {data.artists.map((a) => (
        <div key={a.rank} className="flex items-center gap-3 px-4 py-2">
          <span className="mono w-5 text-right text-[9px] tabular-nums text-muted-foreground">
            {a.rank}
          </span>
          <div className="flex-1 min-w-0">
            <div className="mono truncate text-[11px] font-bold uppercase tracking-[0.12em] text-foreground">
              {a.name}
            </div>
            <div className="mt-0.5 h-1 w-full rounded-none bg-panel-raised">
              <div
                className="h-full bg-signal-orange"
                style={{ width: `${Math.round(a.weight * 100)}%` }}
              />
            </div>
          </div>
          <span className="mono text-[10px] tabular-nums text-muted-foreground">
            {a.plays.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Plays trend panel ────────────────────────────────────────────────────────

function PlaysTrendPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "plays-trend", fromDate, toDate],
    queryFn: () => fetchReportsPlaysTrend(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton />;
  if (isError) return <SectionError label="PLAYS DATA UNAVAILABLE" refetch={refetch} />;
  if (!data || data.days.length === 0) return <Empty label="NO PLAYS IN PERIOD" />;

  const chartData = data.days.map((d) => ({ date: d.date.slice(5), plays: d.plays }));

  return (
    <div className="px-2 pb-2" style={{ height: CHART_HEIGHT }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="playsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-signal-orange)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--color-signal-orange)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            width={28}
          />
          <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: "var(--color-border)" }} />
          <Area
            type="monotone"
            dataKey="plays"
            stroke="var(--color-signal-orange)"
            strokeWidth={1.5}
            fill="url(#playsGrad)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Genre landscape panel ────────────────────────────────────────────────────

function GenresPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "genres", fromDate, toDate],
    queryFn: () => fetchReportsGenres(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton />;
  if (isError) return <SectionError label="GENRE DATA UNAVAILABLE" refetch={refetch} />;
  if (!data || data.genres.length === 0) return <Empty label="NO PLAYS IN PERIOD" />;

  return (
    <div className="divide-y divide-border">
      {data.genres.slice(0, 12).map((g) => (
        <div key={g.genre} className="flex items-center gap-3 px-4 py-2">
          <div className="flex-1 min-w-0">
            <div className="mono truncate text-[10px] uppercase tracking-[0.1em] text-foreground">
              {g.genre}
            </div>
            <div className="mt-0.5 h-1 w-full rounded-none bg-panel-raised">
              <div
                className="h-full bg-zinc-400"
                style={{ width: `${Math.round(g.weight * 100)}%` }}
              />
            </div>
          </div>
          <span className="mono text-[10px] tabular-nums text-muted-foreground">
            {g.plays.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Discovery timeline panel ─────────────────────────────────────────────────

function DiscoveryTimelinePanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "discovery-timeline", fromDate, toDate],
    queryFn: () => fetchReportsDiscoveryTimeline(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton />;
  if (isError) return <SectionError label="TIMELINE UNAVAILABLE" refetch={refetch} />;
  if (!data || data.months.length === 0) return <Empty label="NO DISCOVERIES IN PERIOD" />;

  const chartData = data.months.map((m) => ({ month: m.month.slice(0, 7), count: m.count }));

  return (
    <div className="px-2 pb-2" style={{ height: CHART_HEIGHT }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="month"
            tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            width={28}
          />
          <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--color-panel-raised)" }} />
          <Bar dataKey="count" fill="var(--color-signal-orange)" radius={0} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Old / new ratio panel ────────────────────────────────────────────────────

function ListeningRatioPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "listening-ratio", fromDate, toDate],
    queryFn: () => fetchReportsListeningRatio(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={120} />;
  if (isError) return <SectionError label="RATIO UNAVAILABLE" refetch={refetch} />;
  if (!data) return null;

  const segments = [
    { label: "FAMILIAR", pct: data.familiar_pct, plays: data.familiar_plays, color: "bg-signal-orange" },
    { label: "NEW", pct: data.new_pct, plays: data.new_plays, color: "bg-zinc-400" },
    { label: "UNKNOWN", pct: 100 - data.familiar_pct - data.new_pct, plays: data.unknown_plays, color: "bg-panel-raised" },
  ];

  return (
    <div className="p-4 space-y-3">
      <div className="flex h-3 w-full overflow-hidden gap-px">
        {segments.map((s) =>
          s.pct > 0 ? (
            <div
              key={s.label}
              className={s.color}
              style={{ width: `${s.pct}%` }}
            />
          ) : null,
        )}
      </div>
      <div className="flex gap-6">
        {segments.map((s) => (
          <div key={s.label}>
            <div className="mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
              {s.label}
            </div>
            <div className="mono text-[13px] font-bold tabular-nums text-foreground">
              {s.pct.toFixed(1)}%
            </div>
            <div className="mono text-[9px] tabular-nums text-muted-foreground">
              {s.plays.toLocaleString()} plays
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Streak panel ─────────────────────────────────────────────────────────────

function StreakPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "streak", fromDate, toDate],
    queryFn: () => fetchReportsStreak(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={80} />;
  if (isError) return <SectionError label="STREAK UNAVAILABLE" refetch={refetch} />;

  return (
    <div className="flex gap-8 p-4">
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          CURRENT STREAK
        </div>
        <div className="mt-1 font-mono text-3xl font-bold tabular-nums text-foreground">
          {data?.current ?? 0}
          <span className="mono ml-1 text-[11px] font-normal text-muted-foreground">DAYS</span>
        </div>
      </div>
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          LONGEST STREAK
        </div>
        <div className="mt-1 font-mono text-3xl font-bold tabular-nums text-foreground">
          {data?.longest ?? 0}
          <span className="mono ml-1 text-[11px] font-normal text-muted-foreground">DAYS</span>
        </div>
      </div>
    </div>
  );
}

// ─── Curation funnel panel ────────────────────────────────────────────────────

const FUNNEL_STATUS_ORDER = ["TRACKED", "FOLLOWING", "PUBLISHED", "BLACKLISTED"];
const FUNNEL_STATUS_COLOR: Record<string, string> = {
  TRACKED: "bg-zinc-500",
  FOLLOWING: "bg-zinc-400",
  PUBLISHED: "bg-signal-green",
  BLACKLISTED: "bg-signal-red",
};

function CurationFunnelPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "funnel", fromDate, toDate],
    queryFn: () => fetchReportsFunnel(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={100} />;
  if (isError) return <SectionError label="FUNNEL UNAVAILABLE" refetch={refetch} />;
  if (!data) return null;

  const ordered = FUNNEL_STATUS_ORDER.map((s) => ({
    status: s,
    count: data.entries.find((e) => e.status === s)?.count ?? 0,
  }));
  const max = Math.max(...ordered.map((o) => o.count), 1);

  return (
    <div className="p-4">
      {data.period_filtered && (
        <div className="mono mb-3 text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
          STATUS CHANGES IN PERIOD
        </div>
      )}
      <div className="space-y-2">
        {ordered.map((o) => (
          <div key={o.status} className="flex items-center gap-3">
            <span className="mono w-24 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              {o.status}
            </span>
            <div className="flex-1 h-4 bg-panel-raised">
              <div
                className={cn("h-full", FUNNEL_STATUS_COLOR[o.status] ?? "bg-zinc-500")}
                style={{ width: `${(o.count / max) * 100}%` }}
              />
            </div>
            <span className="mono w-8 text-right text-[10px] tabular-nums text-foreground">
              {o.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function ReportsPage() {
  const [period, setPeriod] = useState<Period>("30d");
  const { fromDate, toDate } = usePeriodDates(period);

  return (
    <div className="flex flex-col gap-0 min-h-0 overflow-y-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            § 05 · REPORTS
          </div>
          <div className="mt-1 font-mono text-xl font-bold tracking-tight text-foreground">
            LISTENING ANALYTICS
          </div>
        </div>
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>

      {/* Hero — headline */}
      <FaceplatePanel slug="05.A" label="HEADLINE" className="faceplate">
        <HeadlinePanel fromDate={fromDate} toDate={toDate} />
      </FaceplatePanel>

      {/* 2-column grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FaceplatePanel
          slug="05.B"
          label="TOP ARTISTS"
          meta={<span className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">TOP 20</span>}
          bodyClassName="p-0"
        >
          <TopArtistsPanel fromDate={fromDate} toDate={toDate} />
        </FaceplatePanel>

        <FaceplatePanel slug="05.C" label="PLAYS TREND">
          <PlaysTrendPanel fromDate={fromDate} toDate={toDate} />
        </FaceplatePanel>

        <FaceplatePanel
          slug="05.D"
          label="GENRE LANDSCAPE"
          bodyClassName="p-0"
        >
          <GenresPanel fromDate={fromDate} toDate={toDate} />
        </FaceplatePanel>

        <FaceplatePanel slug="05.E" label="DISCOVERY TIMELINE">
          <DiscoveryTimelinePanel fromDate={fromDate} toDate={toDate} />
        </FaceplatePanel>

        <FaceplatePanel
          slug="05.F"
          label="OLD / NEW RATIO"
          info="Familiar = artists you first heard before the period start. New = first heard during the period. Unknown = no artist record found."
        >
          <ListeningRatioPanel fromDate={fromDate} toDate={toDate} />
        </FaceplatePanel>

        <FaceplatePanel
          slug="05.G"
          label="LISTENING STREAK"
          info="Consecutive days with at least one play. Current streak counts from today backwards."
        >
          <StreakPanel fromDate={fromDate} toDate={toDate} />
        </FaceplatePanel>
      </div>

      {/* Full-width funnel */}
      <FaceplatePanel
        slug="05.H"
        label="CURATION FUNNEL"
        info="Artist counts at each pipeline stage. When a period is selected, shows status changes that occurred within the period (requires status_changed_at tracking). Falls back to current-state counts if no audit data exists."
      >
        <CurationFunnelPanel fromDate={fromDate} toDate={toDate} />
      </FaceplatePanel>
    </div>
  );
}
