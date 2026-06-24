import * as React from "react";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
} from "d3-force";

import type { GraphData, GraphNodeAttributes } from "@/api/types";
import { ArtistGraphPanel } from "./ArtistGraphPanel";

const NIGHT = "#0d0f1a";

const STATUS_COLOR: Record<string, string> = {
  FOLLOWING: "#f97316",
  TRACKED: "#22c55e",
  PUBLISHED: "#3b82f6",
  BLACKLISTED: "#6b7280",
};
const GENRE_COLOR = "#a855f7";
const UNKNOWN_COLOR = "#6b7280";

const LEGEND_ITEMS = [
  { color: STATUS_COLOR.FOLLOWING, label: "FOLLOWING" },
  { color: STATUS_COLOR.TRACKED, label: "TRACKED" },
  { color: STATUS_COLOR.PUBLISHED, label: "PUBLISHED" },
  { color: STATUS_COLOR.BLACKLISTED, label: "BLACKLISTED" },
  { color: GENRE_COLOR, label: "GENRE" },
];

type SimNode = SimulationNodeDatum & {
  id: string;
  nodeType: "artist" | "genre";
  label: string;
  color: string;
  r: number;
  attrs: GraphNodeAttributes;
};

type SimLink = {
  source: string | SimNode;
  target: string | SimNode;
  directed: boolean;
};

function nodeRadius(a: GraphNodeAttributes): number {
  if (a.nodeType === "genre") return Math.min(14, 4 + (a.artist_count ?? 1) * 0.8);
  if (a.score != null) return Math.max(3, Math.min(12, a.score * 12));
  if (a.scrobble_count != null && a.scrobble_count > 0)
    return Math.max(2, Math.min(8, Math.log(a.scrobble_count) * 1.5));
  return 3;
}

function glowId(a: GraphNodeAttributes): string {
  if (a.nodeType === "genre") return "glow-genre";
  switch (a.status) {
    case "FOLLOWING": return "glow-following";
    case "TRACKED": return "glow-tracked";
    case "PUBLISHED": return "glow-published";
    default: return "glow-dim";
  }
}

interface ConstellationProps {
  data: GraphData;
  width: number;
  height: number;
  onPickArtist: (attrs: GraphNodeAttributes | null) => void;
}

function Constellation({ data, width, height, onPickArtist }: ConstellationProps) {
  const [, tick] = React.useState(0);
  const svgRef = React.useRef<SVGSVGElement>(null);
  const simNodes = React.useRef<SimNode[]>([]);
  const simLinks = React.useRef<SimLink[]>([]);
  const [view, setView] = React.useState({ x: 0, y: 0, k: 1 });
  const bgDrag = React.useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const nodeDrag = React.useRef<{ node: SimNode; sim: ReturnType<typeof forceSimulation> } | null>(null);

  React.useEffect(() => {
    simNodes.current = data.nodes.map((n) => ({
      id: n.key,
      nodeType: n.attributes.nodeType,
      label: n.attributes.label,
      color: n.attributes.nodeType === "genre"
        ? GENRE_COLOR
        : (STATUS_COLOR[n.attributes.status ?? ""] ?? UNKNOWN_COLOR),
      r: nodeRadius(n.attributes),
      attrs: n.attributes,
    }));

    simLinks.current = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      directed: e.attributes.edgeType === "similar",
    }));

    const sim = forceSimulation(simNodes.current)
      .force(
        "link",
        forceLink<SimNode, SimLink>(simLinks.current)
          .id((d) => d.id)
          .distance(80)
          .strength(0.5),
      )
      .force("charge", forceManyBody().strength(-80))
      .force("center", forceCenter(width / 2, height / 2))
      .force("collide", forceCollide<SimNode>().radius((d) => d.r + 6))
      .alpha(1)
      .alphaDecay(0.025);

    sim.on("tick", () => tick((x) => x + 1));
    (svgRef.current as any).__sim = sim;
    return () => void sim.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, width, height]);

  const onWheel = React.useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const rect = svgRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    setView((v) => {
      const k = Math.min(5, Math.max(0.2, v.k * factor));
      const ratio = k / v.k;
      return { k, x: mx - (mx - v.x) * ratio, y: my - (my - v.y) * ratio };
    });
  }, []);

  const onBgMouseDown = (e: React.MouseEvent) => {
    bgDrag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (nodeDrag.current) {
      const rect = svgRef.current!.getBoundingClientRect();
      const x = (e.clientX - rect.left - view.x) / view.k;
      const y = (e.clientY - rect.top - view.y) / view.k;
      nodeDrag.current.node.fx = x;
      nodeDrag.current.node.fy = y;
      nodeDrag.current.sim.alpha(0.3).restart();
      return;
    }
    if (!bgDrag.current) return;
    setView((v) => ({
      ...v,
      x: bgDrag.current!.vx + (e.clientX - bgDrag.current!.x),
      y: bgDrag.current!.vy + (e.clientY - bgDrag.current!.y),
    }));
  };

  const onMouseUp = () => {
    bgDrag.current = null;
    if (nodeDrag.current) {
      nodeDrag.current.node.fx = null;
      nodeDrag.current.node.fy = null;
      nodeDrag.current = null;
    }
  };

  const startNodeDrag = (n: SimNode) => (e: React.MouseEvent) => {
    e.stopPropagation();
    const sim = (svgRef.current as any).__sim;
    if (sim) nodeDrag.current = { node: n, sim };
  };

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      style={{ display: "block", cursor: bgDrag.current ? "grabbing" : "grab" }}
      onWheel={onWheel}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      <defs>
        <radialGradient id="glow-following">
          <stop offset="0%" stopColor="#f97316" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#f97316" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="glow-tracked">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="glow-published">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="glow-genre">
          <stop offset="0%" stopColor="#a855f7" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#a855f7" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="glow-dim">
          <stop offset="0%" stopColor="#6b7280" stopOpacity="0.7" />
          <stop offset="100%" stopColor="#6b7280" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Background pan surface */}
      <rect
        x={0}
        y={0}
        width={width}
        height={height}
        fill="transparent"
        onMouseDown={onBgMouseDown}
        onClick={() => onPickArtist(null)}
      />

      <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
        {/* Edges */}
        {simLinks.current.map((l, i) => {
          const s = l.source as SimNode;
          const t = l.target as SimNode;
          if (s.x == null || t.x == null) return null;
          return (
            <line
              key={i}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke={l.directed ? "#f97316" : "#ffffff"}
              strokeOpacity={l.directed ? 0.4 : 0.12}
              strokeWidth={(l.directed ? 1 : 0.6) / view.k}
            />
          );
        })}

        {/* Nodes */}
        {simNodes.current.map((n) => {
          if (n.x == null || n.y == null) return null;
          const isGenre = n.nodeType === "genre";
          return (
            <g
              key={n.id}
              onMouseDown={startNodeDrag(n)}
              onClick={(e) => {
                e.stopPropagation();
                if (!isGenre) onPickArtist(n.attrs);
              }}
              style={{ cursor: isGenre ? "grab" : "pointer" }}
            >
              {/* Glow halo */}
              <circle
                cx={n.x}
                cy={n.y}
                r={n.r * 2.8}
                fill={`url(#${glowId(n.attrs)})`}
                opacity={isGenre ? 0.5 : 0.35}
              />
              {/* Node body */}
              <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} />
              {/* Genre label — always visible */}
              {isGenre && (
                <text
                  x={n.x}
                  y={n.y + n.r + 12}
                  textAnchor="middle"
                  fontFamily="monospace"
                  fontSize={10}
                  letterSpacing="0.08em"
                  fill="#ffffff"
                  opacity={0.8}
                  style={{ pointerEvents: "none" }}
                >
                  {n.label.toUpperCase()}
                </text>
              )}
              {/* Artist label — only when zoomed in */}
              {!isGenre && view.k > 1.5 && (
                <text
                  x={n.x}
                  y={n.y - n.r - 5}
                  textAnchor="middle"
                  fontFamily="monospace"
                  fontSize={9}
                  fill="#ffffff"
                  opacity={0.55}
                  style={{ pointerEvents: "none" }}
                >
                  {n.label}
                </text>
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
}

interface GenreGraphProps {
  data: GraphData;
}

export function GenreGraph({ data }: GenreGraphProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [size, setSize] = React.useState({ w: 800, h: 600 });
  const [selected, setSelected] = React.useState<GraphNodeAttributes | null>(null);

  React.useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((es) =>
      setSize({ w: es[0].contentRect.width, h: 600 }),
    );
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const handlePickArtist = React.useCallback((attrs: GraphNodeAttributes | null) => {
    setSelected(attrs?.nodeType === "artist" ? attrs : null);
  }, []);

  return (
    <div className="flex flex-col gap-3">
      <div
        ref={containerRef}
        className="relative w-full overflow-hidden border border-border"
        style={{ height: "600px", background: NIGHT }}
      >
        <Constellation
          data={data}
          width={size.w}
          height={size.h}
          onPickArtist={handlePickArtist}
        />
        <ArtistGraphPanel artist={selected} onClose={() => setSelected(null)} />
      </div>

      <div className="flex flex-wrap gap-4">
        {LEGEND_ITEMS.map(({ color, label }) => (
          <div
            key={label}
            className="mono flex items-center gap-1.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground"
          >
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
