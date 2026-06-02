import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  fetchReportsListeningClock,
  fetchReportsFingerprint,
  fetchReportsGenreStream,
  fetchReportsWeeklyDiscoveryRate,
  fetchReportsDiscoveryHighlight,
  fetchReportsGenreDrift,
  fetchReportsCalendar,
  fetchReportsLoyalArtists,
  fetchReportsSourceEffectiveness,
} from "@/api/queries";

export const Route = createFileRoute("/reports")({
  component: ReportsPage,
});

// ─── Period selector ──────────────────────────────────────────────────────────

type Period = "all" | "7d" | "30d" | "90d" | "ytd";

const PERIODS: { id: Period; label: string }[] = [
  { id: "all", label: "ALL TIME" },
  { id: "7d", label: "LAST 7D" },
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

  if (period === "7d") {
    const from = new Date(today);
    from.setDate(from.getDate() - 7);
    return { fromDate: fmt(from), toDate };
  }
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

// ─── Borderless section wrapper ───────────────────────────────────────────────

function ReportSection({
  label,
  meta,
  info,
  children,
}: {
  label: string;
  meta?: React.ReactNode;
  info?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between border-b border-border pb-2 mb-0">
        <div className="flex items-center gap-2">
          <span className="mono text-[10px] font-bold uppercase tracking-[0.2em] text-foreground">
            {label}
          </span>
          {info && (
            <UITooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="flex h-[14px] w-[14px] items-center justify-center rounded-full border border-muted-foreground/40 text-muted-foreground/60 hover:border-muted-foreground hover:text-muted-foreground mono text-[9px] leading-none transition-colors"
                >
                  ?
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[260px] whitespace-normal leading-relaxed">
                {info}
              </TooltipContent>
            </UITooltip>
          )}
        </div>
        {meta && (
          <span className="mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {meta}
          </span>
        )}
      </div>
      {children}
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
  return <Skeleton style={{ height }} className="w-full mt-3" />;
}

function SectionError({ label, refetch }: { label: string; refetch: () => void }) {
  return (
    <div className="mono pt-4 text-center text-[11px] uppercase tracking-[0.18em] text-signal-red">
      {label} —{" "}
      <button onClick={refetch} className="underline text-muted-foreground hover:text-foreground">
        RETRY
      </button>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="mono pt-4 text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
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

  if (isLoading) return <SectionSkeleton height={56} />;
  if (isError) return <SectionError label="HEADLINE UNAVAILABLE" refetch={refetch} />;

  return (
    <div className="flex gap-10 pt-4">
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          TOTAL PLAYS
        </div>
        <div className="mt-0.5 font-mono text-3xl font-bold tabular-nums text-foreground">
          {(data?.total_plays ?? 0).toLocaleString()}
        </div>
      </div>
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          UNIQUE ARTISTS
        </div>
        <div className="mt-0.5 font-mono text-3xl font-bold tabular-nums text-foreground">
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
        <div key={a.rank} className="flex items-center gap-3 py-2">
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
      {data.genres.slice(0, 15).map((g) => (
        <div key={g.genre} className="flex items-center gap-3 py-2">
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
    <div className="pt-3" style={{ height: CHART_HEIGHT }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
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
    <div className="pt-3" style={{ height: CHART_HEIGHT }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
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
          <Bar dataKey="count" fill="var(--color-signal-orange)" radius={0} maxBarSize={32} />
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

  if (isLoading) return <SectionSkeleton height={88} />;
  if (isError) return <SectionError label="RATIO UNAVAILABLE" refetch={refetch} />;
  if (!data) return null;

  const segments = [
    { label: "FAMILIAR", pct: data.familiar_pct, plays: data.familiar_plays, color: "bg-signal-orange" },
    { label: "NEW", pct: data.new_pct, plays: data.new_plays, color: "bg-zinc-400" },
    { label: "UNKNOWN", pct: 100 - data.familiar_pct - data.new_pct, plays: data.unknown_plays, color: "bg-panel-raised" },
  ];

  return (
    <div className="pt-4 space-y-3">
      <div className="flex h-2 w-full overflow-hidden gap-px">
        {segments.map((s) =>
          s.pct > 0 ? (
            <div key={s.label} className={s.color} style={{ width: `${s.pct}%` }} />
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

  if (isLoading) return <SectionSkeleton height={56} />;
  if (isError) return <SectionError label="STREAK UNAVAILABLE" refetch={refetch} />;

  return (
    <div className="flex gap-8 pt-4">
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          CURRENT STREAK
        </div>
        <div className="mt-0.5 font-mono text-3xl font-bold tabular-nums text-foreground">
          {data?.current ?? 0}
          <span className="mono ml-1 text-[11px] font-normal text-muted-foreground">DAYS</span>
        </div>
      </div>
      <div>
        <div className="mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
          LONGEST STREAK
        </div>
        <div className="mt-0.5 font-mono text-3xl font-bold tabular-nums text-foreground">
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

  if (isLoading) return <SectionSkeleton height={88} />;
  if (isError) return <SectionError label="FUNNEL UNAVAILABLE" refetch={refetch} />;
  if (!data) return null;

  const ordered = FUNNEL_STATUS_ORDER.map((s) => ({
    status: s,
    count: data.entries.find((e) => e.status === s)?.count ?? 0,
  }));
  const max = Math.max(...ordered.map((o) => o.count), 1);

  return (
    <div className="pt-4">
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

// ─── Listening clock panel ────────────────────────────────────────────────────

function ListeningClockPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "listening-clock", fromDate, toDate],
    queryFn: () => fetchReportsListeningClock(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={260} />;
  if (isError) return <SectionError label="CLOCK UNAVAILABLE" refetch={refetch} />;
  if (!data) return null;

  const cx = 130;
  const cy = 130;
  const innerR = 22;
  const maxOuterR = 104;
  const maxPlays = Math.max(...data.hours.map((h) => h.plays), 1);

  const hourMap: Record<number, number> = {};
  data.hours.forEach((h) => { hourMap[h.hour] = h.plays; });

  const sectors = Array.from({ length: 24 }, (_, i) => {
    const plays = hourMap[i] ?? 0;
    const outerR = plays > 0
      ? innerR + (plays / maxPlays) * (maxOuterR - innerR)
      : innerR + 2;
    const θ1 = (i / 24) * 2 * Math.PI - Math.PI / 2;
    const θ2 = ((i + 1) / 24) * 2 * Math.PI - Math.PI / 2;
    const x1i = cx + innerR * Math.cos(θ1);
    const y1i = cy + innerR * Math.sin(θ1);
    const x2i = cx + innerR * Math.cos(θ2);
    const y2i = cy + innerR * Math.sin(θ2);
    const x1o = cx + outerR * Math.cos(θ1);
    const y1o = cy + outerR * Math.sin(θ1);
    const x2o = cx + outerR * Math.cos(θ2);
    const y2o = cy + outerR * Math.sin(θ2);
    const d = [
      `M ${x1i.toFixed(2)} ${y1i.toFixed(2)}`,
      `L ${x1o.toFixed(2)} ${y1o.toFixed(2)}`,
      `A ${outerR.toFixed(2)} ${outerR.toFixed(2)} 0 0 1 ${x2o.toFixed(2)} ${y2o.toFixed(2)}`,
      `L ${x2i.toFixed(2)} ${y2i.toFixed(2)}`,
      `A ${innerR} ${innerR} 0 0 0 ${x1i.toFixed(2)} ${y1i.toFixed(2)}`,
      "Z",
    ].join(" ");
    return { hour: i, plays, d };
  });

  const labelHours: [number, string][] = [[0, "12A"], [6, "6A"], [12, "12P"], [18, "6P"]];
  const labelR = maxOuterR + 14;

  return (
    <div className="pt-3 flex justify-center">
      <svg width={260} height={260} viewBox="0 0 260 260">
        <circle cx={cx} cy={cy} r={maxOuterR} fill="none" stroke="var(--color-border)" strokeWidth={0.5} />
        <circle cx={cx} cy={cy} r={innerR} fill="var(--color-panel-raised)" />
        {sectors.map(({ hour, plays, d }) => (
          <path
            key={hour}
            d={d}
            fill="var(--color-signal-orange)"
            fillOpacity={plays > 0 ? 0.8 : 0.08}
            stroke="var(--color-background)"
            strokeWidth={0.5}
          >
            <title>{`${hour}:00 — ${plays} plays`}</title>
          </path>
        ))}
        {labelHours.map(([h, label]) => {
          const θ = (h / 24) * 2 * Math.PI - Math.PI / 2;
          return (
            <text
              key={h}
              x={(cx + labelR * Math.cos(θ)).toFixed(1)}
              y={(cy + labelR * Math.sin(θ)).toFixed(1)}
              textAnchor="middle"
              dominantBaseline="central"
              fill="var(--color-muted-foreground)"
              fontSize={9}
              fontFamily="monospace"
            >
              {label}
            </text>
          );
        })}
        <text x={cx} y={cy - 4} textAnchor="middle" fill="var(--color-muted-foreground)" fontSize={8} fontFamily="monospace">PLAYS</text>
        <text x={cx} y={cy + 6} textAnchor="middle" fill="var(--color-muted-foreground)" fontSize={7} fontFamily="monospace">BY HOUR</text>
      </svg>
    </div>
  );
}

// ─── Listening fingerprint panel ──────────────────────────────────────────────

function FingerprintPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "fingerprint", fromDate, toDate],
    queryFn: () => fetchReportsFingerprint(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={260} />;
  if (isError) return <SectionError label="FINGERPRINT UNAVAILABLE" refetch={refetch} />;
  if (!data) return null;

  const radarData = [
    { metric: "CONSISTENCY", value: Math.round(data.consistency * 100) },
    { metric: "VARIETY", value: Math.round(data.variety * 100) },
    { metric: "DISCOVERY", value: Math.round(data.discovery * 100) },
    { metric: "NIGHT OWL", value: Math.round(data.night_owl * 100) },
    { metric: "DEPTH", value: Math.round(data.depth * 100) },
  ];

  return (
    <div className="pt-3" style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={radarData}>
          <PolarGrid stroke="var(--color-border)" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 9, fontFamily: "monospace" }}
          />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="fingerprint"
            dataKey="value"
            stroke="var(--color-signal-orange)"
            fill="var(--color-signal-orange)"
            fillOpacity={0.25}
            strokeWidth={1.5}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v: number) => [`${v}%`, undefined]}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Genre streamgraph panel ──────────────────────────────────────────────────

const STREAM_COLORS = [
  "#f97316",
  "#ef4444",
  "#8b5cf6",
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ec4899",
  "#6366f1",
];

function GenreStreamPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "genre-stream", fromDate, toDate],
    queryFn: () => fetchReportsGenreStream(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={220} />;
  if (isError) return <SectionError label="STREAM UNAVAILABLE" refetch={refetch} />;
  if (!data || data.points.length === 0) return <Empty label="NO PLAYS IN PERIOD" />;

  const chartData = data.points.map((p) => ({
    week: p.week_start.slice(5),
    ...p.plays,
  }));

  return (
    <div className="pt-3" style={{ height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          stackOffset="wiggle"
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <XAxis
            dataKey="week"
            tick={{ fontSize: 9, fontFamily: "monospace", fill: "var(--color-muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis hide />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          {data.top_genres.map((genre, i) => (
            <Area
              key={genre}
              type="monotone"
              dataKey={genre}
              stackId="1"
              stroke={STREAM_COLORS[i % STREAM_COLORS.length]}
              fill={STREAM_COLORS[i % STREAM_COLORS.length]}
              fillOpacity={0.75}
              strokeWidth={0}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Weekly discovery rate panel ─────────────────────────────────────────────

function WeeklyDiscoveryRatePanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "weekly-discovery-rate", fromDate, toDate],
    queryFn: () => fetchReportsWeeklyDiscoveryRate(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton />;
  if (isError) return <SectionError label="DISCOVERY RATE UNAVAILABLE" refetch={refetch} />;
  if (!data || data.weeks.length === 0) return <Empty label="NO DISCOVERY DATA" />;

  const chartData = data.weeks.map((w) => ({
    week: w.week_start.slice(5, 10),
    count: w.count,
  }));

  return (
    <div className="pt-3" style={{ height: CHART_HEIGHT }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="week"
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
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ fill: "var(--color-panel-raised)" }}
            formatter={(v: number) => [v, "new artists"]}
          />
          <Bar dataKey="count" fill="var(--color-signal-orange)" radius={[1, 1, 0, 0]} maxBarSize={32} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Discovery highlight panel ────────────────────────────────────────────────

function DiscoveryHighlightPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["reports", "discovery-highlight", fromDate, toDate],
    queryFn: () => fetchReportsDiscoveryHighlight(fromDate, toDate),
    staleTime: 30_000,
    enabled: fromDate !== null,
  });

  if (!fromDate || isLoading || isError || !data?.available) return null;

  return (
    <div className="border border-signal-orange/30 bg-signal-orange/5 p-4 space-y-1">
      <div className="mono text-[9px] uppercase tracking-[0.22em] text-signal-orange">
        DISCOVERY OF THE PERIOD
      </div>
      <div className="font-mono text-lg font-bold tracking-tight text-foreground">
        {data.name}
      </div>
      {data.first_seen_at && (
        <div className="mono text-[9px] text-muted-foreground">
          FIRST SEEN {new Date(data.first_seen_at).toISOString().slice(0, 10)}
        </div>
      )}
      <div className="flex items-center gap-4 pt-1">
        {data.plays !== null && (
          <span className="mono text-[11px] text-foreground">
            {data.plays.toLocaleString()} PLAYS
          </span>
        )}
        {data.genres.length > 0 && (
          <span className="mono text-[10px] text-muted-foreground truncate">
            {data.genres.slice(0, 3).join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Genre drift panel ────────────────────────────────────────────────────────

function GenreDriftPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "genre-drift", fromDate, toDate],
    queryFn: () => fetchReportsGenreDrift(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={140} />;
  if (isError) return <SectionError label="GENRE DRIFT UNAVAILABLE" refetch={refetch} />;
  if (!fromDate) return <Empty label="SELECT A PERIOD TO COMPARE GENRE DRIFT" />;
  if (!data) return null;

  const col = (entries: typeof data.current, label: string) => {
    const max = Math.max(...entries.map((g) => g.plays), 1);
    return (
      <div className="flex-1 min-w-0">
        <div className="mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground mb-2">
          {label}
        </div>
        {entries.slice(0, 5).length === 0 ? (
          <div className="mono text-[10px] text-muted-foreground">—</div>
        ) : (
          entries.slice(0, 5).map((g, i) => (
            <div key={g.genre} className="flex items-center gap-2 py-1">
              <span className="mono w-3 text-[9px] tabular-nums text-muted-foreground">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <div className="mono truncate text-[10px] text-foreground">{g.genre}</div>
                <div className="mt-0.5 h-0.5 bg-panel-raised">
                  <div
                    className="h-full bg-signal-orange"
                    style={{ width: `${(g.plays / max) * 100}%` }}
                  />
                </div>
              </div>
              <span className="mono text-[9px] tabular-nums text-muted-foreground shrink-0">
                {g.plays.toLocaleString()}
              </span>
            </div>
          ))
        )}
      </div>
    );
  };

  return (
    <div className="pt-3 flex gap-6">
      {col(data.current, "CURRENT PERIOD")}
      <div className="w-px bg-border shrink-0" />
      {col(data.previous, `PREVIOUS PERIOD${data.period_days ? ` (–${data.period_days}D)` : ""}`)}
    </div>
  );
}

// ─── Calendar heatmap panel ───────────────────────────────────────────────────

const CAL_COLORS = [
  "var(--color-panel-raised)",
  "rgba(249,115,22,0.2)",
  "rgba(249,115,22,0.45)",
  "rgba(249,115,22,0.7)",
  "rgb(249,115,22)",
];

function calColor(plays: number, maxPlays: number): string {
  if (plays === 0) return CAL_COLORS[0];
  const r = plays / maxPlays;
  if (r < 0.15) return CAL_COLORS[1];
  if (r < 0.35) return CAL_COLORS[2];
  if (r < 0.65) return CAL_COLORS[3];
  return CAL_COLORS[4];
}

function CalendarHeatmapPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "calendar", fromDate, toDate],
    queryFn: () => fetchReportsCalendar(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={110} />;
  if (isError) return <SectionError label="CALENDAR UNAVAILABLE" refetch={refetch} />;
  if (!data || data.days.length === 0) return <Empty label="NO PLAY DATA" />;

  const playMap: Record<string, number> = {};
  data.days.forEach((d) => { playMap[d.date] = d.plays; });
  const maxPlays = Math.max(...Object.values(playMap), 1);

  const start = new Date(data.from_date + "T00:00:00");
  const end = new Date(data.to_date + "T00:00:00");

  // Align start to Monday (getDay: 0=Sun,1=Mon…6=Sat → shift to Mon=0)
  const dow0 = (start.getDay() + 6) % 7;
  const firstCell = new Date(start);
  firstCell.setDate(firstCell.getDate() - dow0);

  const weeks: { date: string; plays: number; inRange: boolean }[][] = [];
  const cur = new Date(firstCell);
  while (cur <= end || weeks.length === 0 || weeks[weeks.length - 1].length < 7) {
    const week: { date: string; plays: number; inRange: boolean }[] = [];
    for (let d = 0; d < 7; d++) {
      const dateStr = cur.toISOString().slice(0, 10);
      week.push({ date: dateStr, plays: playMap[dateStr] ?? 0, inRange: cur >= start && cur <= end });
      cur.setDate(cur.getDate() + 1);
    }
    weeks.push(week);
    if (cur > end && weeks[weeks.length - 1].every((c) => !c.inRange)) {
      weeks.pop();
      break;
    }
  }

  const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];

  return (
    <div className="pt-3 overflow-x-auto">
      <div className="flex gap-px" style={{ minWidth: `${weeks.length * 12 + 18}px` }}>
        <div className="flex flex-col gap-px mr-1 pt-px shrink-0">
          {DAY_LABELS.map((l, i) => (
            <div
              key={i}
              className="mono text-[8px] text-muted-foreground flex items-center justify-center"
              style={{ width: 10, height: 10 }}
            >
              {i % 2 === 0 ? l : ""}
            </div>
          ))}
        </div>
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-px">
            {week.map((day) => (
              <div
                key={day.date}
                style={{
                  width: 10,
                  height: 10,
                  background: day.inRange ? calColor(day.plays, maxPlays) : "transparent",
                  flexShrink: 0,
                }}
                title={day.inRange ? `${day.date}: ${day.plays} plays` : undefined}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Loyal artists panel ──────────────────────────────────────────────────────

function LoyalArtistsPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "loyal-artists", fromDate, toDate],
    queryFn: () => fetchReportsLoyalArtists(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton />;
  if (isError) return <SectionError label="LOYAL ARTISTS UNAVAILABLE" refetch={refetch} />;
  if (!data || data.artists.length === 0) return <Empty label="NO LOYAL ARTISTS IN PERIOD" />;

  return (
    <div className="divide-y divide-border">
      {data.artists.map((a) => (
        <div key={a.rank} className="flex items-center gap-3 py-2">
          <span className="mono w-5 text-right text-[9px] tabular-nums text-muted-foreground">
            {a.rank}
          </span>
          <div className="flex-1 min-w-0">
            <div className="mono truncate text-[11px] font-bold uppercase tracking-[0.12em] text-foreground">
              {a.name}
            </div>
            <div className="mt-0.5 h-1 w-full rounded-none bg-panel-raised">
              <div
                className="h-full bg-zinc-400"
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

// ─── Source effectiveness panel ───────────────────────────────────────────────

function SourceEffectivenessPanel({
  fromDate,
  toDate,
}: {
  fromDate: string | null;
  toDate: string | null;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "source-effectiveness", fromDate, toDate],
    queryFn: () => fetchReportsSourceEffectiveness(fromDate, toDate),
    staleTime: 30_000,
  });

  if (isLoading) return <SectionSkeleton height={140} />;
  if (isError) return <SectionError label="SOURCE DATA UNAVAILABLE" refetch={refetch} />;
  if (!data || data.sources.length === 0) return <Empty label="NO SOURCE DATA" />;

  const maxTotal = Math.max(...data.sources.map((s) => s.total), 1);

  return (
    <div className="pt-3 space-y-0 divide-y divide-border">
      {data.sources.map((s) => (
        <div key={s.source} className="py-2 space-y-1">
          <div className="flex items-center justify-between">
            <span className="mono text-[10px] uppercase tracking-[0.12em] text-foreground">
              {s.source}
            </span>
            <span
              className="mono text-[10px] tabular-nums"
              style={{ color: s.publish_rate >= 0.1 ? "var(--color-signal-orange)" : "var(--color-muted-foreground)" }}
            >
              {(s.publish_rate * 100).toFixed(0)}% published
            </span>
          </div>
          <div className="relative h-2 bg-panel-raised overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 bg-zinc-600"
              style={{ width: `${(s.total / maxTotal) * 100}%` }}
            />
            <div
              className="absolute inset-y-0 left-0 bg-signal-orange"
              style={{ width: `${(s.published / maxTotal) * 100}%` }}
            />
          </div>
          <div className="mono text-[9px] text-muted-foreground flex gap-3">
            <span>{s.total} total</span>
            <span>{s.published} published</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function ReportsPage() {
  const [period, setPeriod] = useState<Period>("30d");
  const { fromDate, toDate } = usePeriodDates(period);

  return (
    <div className="space-y-8">
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

      {/* Headline */}
      <ReportSection label="HEADLINE">
        <HeadlinePanel fromDate={fromDate} toDate={toDate} />
      </ReportSection>

      {/* Discovery Highlight — only shown when a period is selected */}
      <DiscoveryHighlightPanel fromDate={fromDate} toDate={toDate} />

      {/* Lists: Top Artists + Genre Landscape — natural heights side-by-side */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:items-start">
        <ReportSection label="TOP ARTISTS" meta="TOP 20">
          <TopArtistsPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>

        <ReportSection label="GENRE LANDSCAPE">
          <GenresPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>
      </div>

      {/* Plays trend — full width area chart */}
      <ReportSection label="PLAYS TREND">
        <PlaysTrendPanel fromDate={fromDate} toDate={toDate} />
      </ReportSection>

      {/* Discovery Timeline + Ratio */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:items-start">
        <ReportSection label="DISCOVERY TIMELINE">
          <DiscoveryTimelinePanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>

        <ReportSection
          label="OLD / NEW RATIO"
          info="Familiar = artists you first heard before the period start. New = first heard during the period. Unknown = no artist record found."
        >
          <ListeningRatioPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>
      </div>

      {/* Weekly Discovery Rate */}
      <ReportSection
        label="WEEKLY DISCOVERY RATE"
        info="Number of new artists first seen each week. Spikes indicate active exploration periods."
      >
        <WeeklyDiscoveryRatePanel fromDate={fromDate} toDate={toDate} />
      </ReportSection>

      {/* Streak + Funnel */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:items-start">
        <ReportSection
          label="LISTENING STREAK"
          info="Consecutive days with at least one play. Current streak counts from today backwards."
        >
          <StreakPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>

        <ReportSection
          label="CURATION FUNNEL"
          info="Artist counts at each pipeline stage. When a period is selected, shows status changes that occurred within the period."
        >
          <CurationFunnelPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>
      </div>

      {/* Listening Clock + Fingerprint */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:items-start">
        <ReportSection
          label="LISTENING CLOCK"
          info="Play distribution across 24 hours of the day (UTC). Each wedge height represents relative play count for that hour."
        >
          <ListeningClockPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>

        <ReportSection
          label="LISTENING FINGERPRINT"
          info="Consistency: listening days / period span. Variety: spread across artists. Discovery: new artists in period. Night Owl: plays 20:00–04:00. Depth: artists replayed more than once."
        >
          <FingerprintPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>
      </div>

      {/* Genre Streamgraph */}
      <ReportSection
        label="GENRE STREAM"
        info="Weekly play volume for your top 8 genres, shown as a streamgraph. Area height = relative plays per week."
      >
        <GenreStreamPanel fromDate={fromDate} toDate={toDate} />
      </ReportSection>

      {/* Calendar Heatmap */}
      <ReportSection
        label="PLAY CALENDAR"
        info="Daily play count over the selected period. Colour intensity scales with plays per day — darker orange = more plays."
      >
        <CalendarHeatmapPanel fromDate={fromDate} toDate={toDate} />
      </ReportSection>

      {/* Genre Drift */}
      <ReportSection
        label="GENRE DRIFT"
        info="Top 5 genres this period vs the equivalent previous period. Shows how your listening tastes are shifting."
      >
        <GenreDriftPanel fromDate={fromDate} toDate={toDate} />
      </ReportSection>

      {/* Loyal Artists + Source Effectiveness */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:items-start">
        <ReportSection
          label="LOYAL ARTISTS"
          meta="6+ MONTHS"
          info="Artists you've been listening to for at least 6 months, ranked by plays in the selected period. These are your long-term staples."
        >
          <LoyalArtistsPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>

        <ReportSection
          label="SOURCE EFFECTIVENESS"
          info="For each discovery source, how many artists were found and how many were published. Orange bar = published; grey bar = total."
        >
          <SourceEffectivenessPanel fromDate={fromDate} toDate={toDate} />
        </ReportSection>
      </div>
    </div>
  );
}
