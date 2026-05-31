# ADR-019: Signal Dashboard Tech Stack

- **Status**: Accepted
- **Date**: 2026-05-31

## Context

The Signal pipeline surfaces artist recommendations through a FastAPI + Swagger UI interface, which requires manual JSON editing to follow or blacklist artists. A proper curation UI was needed to replace this workflow. A reference implementation (`cyber-signal-desk-main`) already existed with the desired dark brutalist design and all required components, but it was built on TanStack Start with a Cloudflare Workers/SSR runtime that cannot run outside the Lovable platform. The dashboard is a local dev tool used by a single operator — not a customer-facing service — so operational simplicity and fast iteration matter more than SSR, SEO, or production hardening.

## Decision

Build `services/dashboard` as a plain Vite SPA by converting the reference project: replace TanStack Start and the Cloudflare Workers runtime with standard `@vitejs/plugin-react` + `TanStackRouterVite` (file-based routing, client-side only), use TanStack Query v5 for data fetching with optimistic updates, serve via Bun dev server, and run under the `tools` Docker Compose profile alongside `kafka-ui`.

## Alternatives considered

**Keep Swagger UI** — *Rejected*
Swagger UI supports `GET` and `PATCH` but has no concept of triage flow (optimistic removal, toast feedback, genre filtering). It cannot display the `VIA → origin` attribution or the QUEUE/DISCOVERY split that reflects the actual two-population TRACKED topology.

**Next.js** — *Rejected*
Would require starting from scratch rather than adapting the existing reference components (ArtistCard, Sidebar, TopBar, ScoreReadout, GenreBadge, SourceIcon). The reference already uses TanStack Router and Tailwind CSS v4, so rewriting for Next.js routing conventions would discard more than it adds for a single-operator tool.

**Keep TanStack Start (SSR)** — *Rejected*
TanStack Start in the reference is configured for Cloudflare Workers via `@lovable.dev/vite-tanstack-config`, which wraps the Vite build for that deployment target and cannot be used locally. Removing the Cloudflare runtime while preserving SSR would require significant server entry-point work for no benefit — the dashboard has one user and no SEO requirements.

**React 19 + TanStack Router SPA + TanStack Query v5 + Tailwind CSS v4 + shadcn/ui + Bun** — *Accepted*

## Consequences

✅ Reference project components (ArtistCard, Sidebar, TopBar, AppShell, ScoreReadout, GenreBadge, SourceIcon) are reused with minimal changes — adapting rather than rebuilding.
✅ TanStack Query v5 provides optimistic cache updates (artist removed immediately on action, reverted on API failure) with a single `useStatusMutation` hook shared across all pages.
✅ File-based routing with `TanStackRouterVite` auto-generates `routeTree.gen.ts` — adding a new page is a single file drop.
✅ Bun dev server starts in ~300ms and supports `--host 0.0.0.0` for Docker; the `tools` profile keeps it out of the default `make up` stack.
❌ Dev-server-only deployment — not production-hardened; no auth, no HTTPS, no rate limiting. Acceptable for a single-operator local tool, but must not be exposed beyond `127.0.0.1`.
❌ TanStack Router's `routeTree.gen.ts` is auto-generated and must be kept in sync manually when the dev server isn't running (was patched by hand during the migration). Running `bun run dev` regenerates it automatically.
❌ Tailwind CSS v4 uses `@import "tailwindcss"` and `@source` directives — the v3 `tailwind.config.js` pattern no longer works. Any contributor unfamiliar with v4 will hit this on first setup.

## When to reconsider

If the dashboard needs to be shared with collaborators over a network (multi-user access, authentication, HTTPS), extract it to a production Vite build served by a reverse proxy and add auth middleware to the FastAPI. At that point SSR or a lightweight server would also become relevant.
