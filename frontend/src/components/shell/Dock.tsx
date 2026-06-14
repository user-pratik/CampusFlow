"use client";

import { useWindowManager } from "@/lib/windowManager";

export default function Dock() {
  const { windows, restoreWindow, closeWindow, activeWindowId } = useWindowManager();

  const minimizedWindows = windows.filter((w) => w.state === "minimized");

  if (minimizedWindows.length === 0) return null;

  return (
    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 mb-3 z-9999">
      <div className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-panel-bg/90 backdrop-blur-md border border-border shadow-lg">
        {minimizedWindows.map((win) => (
          <button
            key={win.id}
            onClick={() => restoreWindow(win.id)}
            onContextMenu={(e) => {
              e.preventDefault();
              closeWindow(win.id);
            }}
            className={`group relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-all hover:bg-surface-hover ${
              activeWindowId === win.id ? "bg-accent-light" : ""
            }`}
            title={`${win.title} — ${win.agentName}\nRight-click to close`}
          >
            <span className="text-sm">{win.agentIcon}</span>
            <span className="text-secondary group-hover:text-foreground truncate max-w-[100px]">
              {win.title}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
