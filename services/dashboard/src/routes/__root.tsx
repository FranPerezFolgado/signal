import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
} from "@tanstack/react-router";
import { AppShell } from "@/components/signal/AppShell";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-4">
      <div className="faceplate max-w-md p-8 text-center">
        <h1 className="mono text-5xl font-bold text-signal-orange">404</h1>
        <h2 className="mt-4 text-base font-semibold uppercase tracking-[0.2em]">
          Signal lost
        </h2>
        <p className="mono mt-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          ROUTE NOT FOUND
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="mono inline-flex items-center border border-signal-orange bg-signal-orange px-4 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-black hover:bg-signal-orange/90"
          >
            RETURN TO QUEUE
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-4">
      <div className="faceplate max-w-md p-8 text-center">
        <h1 className="text-base font-semibold uppercase tracking-[0.2em] text-signal-red">
          SYSTEM FAULT
        </h1>
        <p className="mono mt-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          Module failed to load.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="mono border border-signal-orange bg-signal-orange px-4 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-black"
          >
            RETRY
          </button>
          <a
            href="/"
            className="mono border border-border bg-panel px-4 py-2 text-[11px] font-bold uppercase tracking-[0.12em]"
          >
            HOME
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
