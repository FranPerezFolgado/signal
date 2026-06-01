import { Disc3, Music2, Radio, Rss } from "lucide-react";

const SOURCE_MAP: Record<string, { icon: typeof Music2; label: string }> = {
  spotify: { icon: Music2, label: "SPT" },
  SPOTIFY: { icon: Music2, label: "SPT" },
  SPOTIFY_RELATED: { icon: Music2, label: "SPT_REL" },
  lastfm: { icon: Radio, label: "LFM" },
  LASTFM: { icon: Radio, label: "LFM" },
  LASTFM_SIMILAR: { icon: Radio, label: "LFM_SIM" },
  bandcamp: { icon: Disc3, label: "BCP" },
  rss: { icon: Rss, label: "RSS" },
};

const DEFAULT_ENTRY = { icon: Music2, label: "UNK" };

export function SourceIcon({ source, withLabel = false }: { source: string; withLabel?: boolean }) {
  const { icon: Icon, label } = SOURCE_MAP[source] ?? DEFAULT_ENTRY;
  return (
    <span className="mono inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.15em] text-zinc-400">
      <Icon className="h-3 w-3" />
      {withLabel && <span>{label}</span>}
    </span>
  );
}
