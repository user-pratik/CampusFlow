"use client";

import { useWindowManager } from "@/lib/windowManager";
import FloatingWindow from "./FloatingWindow";
import Dock from "./Dock";
import CommandPalette from "./CommandPalette";

export default function Desktop({ onToggleAppGrid }: { onToggleAppGrid?: () => void }) {
  const { windows } = useWindowManager();

  return (
    <main className="relative flex-1 overflow-hidden bg-transparent">
      {/* Desktop wallpaper / gradient */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute inset-0 bg-linear-to-br from-accent/5 via-transparent to-success/5" />
        {/* Subtle grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "radial-gradient(circle, var(--foreground) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />
      </div>

      {/* Empty state */}
      {windows.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center space-y-3 opacity-50">
            <p className="text-4xl">🎓</p>
            <p className="text-sm text-secondary">
              Your agent desktop is ready
            </p>
            <p className="text-xs text-secondary">
              Use the command palette below or wait for agents to surface activity
            </p>
          </div>
        </div>
      )}

      {/* Floating windows */}
      {windows.map((win) => (
        <FloatingWindow key={win.id} window={win} />
      ))}

      {/* Bottom dock (minimized windows) */}
      <Dock onToggleAppGrid={onToggleAppGrid} />

      {/* Command palette / chat input */}
      <CommandPalette />
    </main>
  );
}
