
# Signal v2 — Refined Brutalist Industrial

A redesign of the existing Signal dashboard. Keeps all current functionality, views, mock data, routing, and state. Only the visual language and component shells change.

## Direction

Refined brutalist — hard edges, exposed grid, no decoration. Less "cassette futurism prop", more "industrial control surface for a serious operator". Closer to Vitsoe / Massimo Vignelli / Swiss signage with hazard-orange punctuation.

## Design System

**Palette — Concrete & Hazard (dark)**

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#1a1a1a` | Canvas |
| `--panel` | `#222222` | Panels / faceplates |
| `--panel-raised` | `#2a2a2a` | Hover / active rows |
| `--border` | `#3d3d3d` | All hairlines |
| `--border-strong` | `#5a5a5a` | Headers, dividers between zones |
| `--muted` | `#9a9a9a` | Secondary text, labels |
| `--foreground` | `#e6e6e6` | Primary text |
| `--hazard` | `#ff5b00` | Primary action, priority, active nav |
| `--hazard-ink` | `#0a0a0a` | Text on hazard fills |
| `--warn` | `#c1272d` | Destructive (Blacklist) |
| `--data` | `#e6e6e6` | Numeric data (no more CRT green glow) |

Retire: CRT green glow, scanlines, frosted blur. Numbers are plain off-white on dark — data, not decoration.

**Typography**
- Display / headings / numbers: **Space Mono** (700 for headings, 400 for data)
- Body / nav / labels: **Rubik** (500 for labels, 400 for body)
- All-caps labels stay all-caps; tracking tightened from `0.2em` → `0.12em`

**Geometry**
- `rounded-none` everywhere, no exceptions (badges included)
- 1px borders, single weight. Use 2px only on the outer page frame and active state underlines.
- No shadows. No gradients. No blur.
- Spacing on an 8px grid; sections separated by visible 1px rules, not gaps.

**Brutalist primitives**
- `[ LABEL ]` bracket buttons → replaced with solid hazard fills for primary, hollow `border` rectangles for secondary. Brackets removed; the shape carries the affordance.
- Section headers use a numbered slug: `§ 01 — QUEUE` in Space Mono, with a 1px rule continuing across the panel.
- Genre badges become uppercase tag rectangles with a single border, no fill.
- Hazard left-stripe (4px solid `--hazard`) marks priority artists — same idea, sharper edge.

## Layout

```text
┌──────────────────────────────────────────────────────────────┐
│  SIGNAL / / / / / / / / / / / / / / / / / / / / / / / /  ◼  │  ← page frame (2px)
├──────┬───────────────────────────────────────────────────────┤
│ 01   │ § 01 — QUEUE        24 PENDING   SYS:OK   23:14 UTC   │
│ QUE  ├───────────────────────────────────────────────────────┤
│ 02   │  ┌─ filter rail (sticky, 1px rule) ─────────────────┐ │
│ FOL  │  │ SEARCH ▮▮▮▮  GENRE ▾  SOURCE ▾                 │ │
│ 03   │  └───────────────────────────────────────────────────┘ │
│ EXP  │  ┌─ artist row ─────────────────────────────────────┐ │
│ 04   │  │ ▌ AKIRA KOSEMURA            092   [ FOLLOW ] [×]│ │
│ STA  │  │   AMBIENT · NEO-CLASSICAL · SPOTIFY · LASTFM   │ │
│      │  │   ─ evidence ──────────────────────────────────  │ │
│      │  │   › track title                        2h ago    │ │
│ ──── │  └──────────────────────────────────────────────────┘ │
│ v0.2 │                                                       │
└──────┴───────────────────────────────────────────────────────┘
```

Changes from v1:
- Sidebar: narrower (180px), numbered slugs `01 / QUEUE` stacked vertically (two lines), active = hazard fill block + black text (not just orange text).
- Top bar: no blur. Solid `--panel` with 1px bottom rule. Status pill becomes plain text `SYS:OK`.
- Cards become **rows**, not cards — no rounded plates floating in space. Each artist is a full-width band separated by 1px rules. Hover = `--panel-raised`.
- Score: large Space Mono number, right-aligned, no glow, no padding `000`. Hover still reveals breakdown in a hard-edged tooltip.
- Stats: 2×2 grid becomes a 4-row stacked table-of-charts with thin rules between, each chart prefixed by `§ 0X — TITLE`. Charts use hazard orange as the single accent; secondary series in `--muted` grey, not green.
- Exploration: tag cloud becomes a left-aligned wrapping list of `TAG · 12` strings, not size-varying. Lineage list keeps the `via → seed` mono form.

## Interactions
- Same actions, same toasts, same routing. Only visual treatment changes.
- Button press = 1px inset border (no translate).
- Toast: hard-edge panel, hazard accent on title, no rounded corners.

## Technical

Files touched:
- `src/styles.css` — replace palette tokens, fonts, utility classes (`.faceplate`, `.frosted`, `.crt-glow` removed; add `.row`, `.rule`, `.slug`).
- `index.html` (or font loader) — swap Google Fonts to **Space Mono + Rubik**.
- `src/components/signal/ArtistCard.tsx` → restructure as row, drop CRT green score styling, brackets.
- `src/components/signal/ScoreReadout.tsx` → plain numeric, no glow, no zero-padding.
- `src/components/signal/GenreBadge.tsx` → hollow rectangle tag.
- `src/components/signal/Sidebar.tsx` → numbered slugs, hazard fill active state.
- `src/components/signal/TopBar.tsx` → de-frost, solid panel + rule.
- `src/components/signal/FaceplatePanel.tsx` → rename intent (keep file): hard panel with numbered `§` header.
- `src/routes/stats.tsx` → switch 2×2 grid to stacked rule-separated sections; recolor charts to hazard + muted.
- `src/routes/exploration.tsx` → flatten tag cloud to inline list.

Untouched:
- `src/store/signal.tsx`, `src/data/mock.ts`, routing, server files, all `src/components/ui/*` shadcn primitives.

## Out of scope
- Light/paper variant
- Animation pass (no Motion/GSAP work in this round)
- New views, new data, new functionality
