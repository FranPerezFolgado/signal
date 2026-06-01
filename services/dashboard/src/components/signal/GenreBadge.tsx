export function GenreBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="mono inline-flex items-center border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-zinc-300">
      {children}
    </span>
  );
}
