import { cn } from "@/lib/utils";

function getPageRange(current: number, total: number): (number | "...")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const delta = 2;
  const left = current - delta;
  const right = current + delta;
  const pages: (number | "...")[] = [1];

  if (left > 2) pages.push("...");

  for (let p = Math.max(2, left); p <= Math.min(total - 1, right); p++) {
    pages.push(p);
  }

  if (right < total - 1) pages.push("...");

  pages.push(total);
  return pages;
}

export function Pagination({
  page,
  pages,
  onChange,
}: {
  page: number;
  pages: number;
  onChange: (p: number) => void;
}) {
  if (pages <= 1) return null;

  const nums = getPageRange(page, pages);

  return (
    <div className="mono flex items-center justify-between border-t border-border pt-4 text-[11px] tabular-nums tracking-[0.1em]">
      <div className="flex items-center gap-0.5">
        {page > 1 && (
          <button
            onClick={() => onChange(page - 1)}
            className="px-2 py-1 text-muted-foreground hover:text-foreground"
          >
            &lsaquo; PREV
          </button>
        )}
        {nums.map((p, i) =>
          p === "..." ? (
            <span key={`e${i}`} className="px-1.5 py-1 text-muted-foreground select-none">
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p as number)}
              className={cn(
                "px-1.5 py-1 transition-colors",
                p === page
                  ? "text-signal-red underline decoration-2 underline-offset-[3px]"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {p}
            </button>
          ),
        )}
      </div>
      <button
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
        className="px-2 py-1 text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
      >
        NEXT &rsaquo;
      </button>
    </div>
  );
}
