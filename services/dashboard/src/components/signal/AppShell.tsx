import { Outlet } from "@tanstack/react-router";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
  return (
    <TooltipProvider delayDuration={120}>
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1 p-4 md:p-6">
            <Outlet />
          </main>
        </div>
      </div>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast:
              "!rounded-none !border !border-border !bg-panel !text-foreground !font-mono !text-xs !uppercase !tracking-[0.12em]",
            title: "!text-signal-orange",
            description: "!text-zinc-400",
          },
        }}
      />
    </TooltipProvider>
  );
}
