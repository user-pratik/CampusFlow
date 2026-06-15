"use client";

import { useState, useEffect } from "react";
import { useTheme } from "../ThemeProvider";
import { useWindowManager } from "@/lib/windowManager";

interface TopBarProps {
  agentCount: number;
  notificationCount: number;
  onNotificationClick: () => void;
  onSyncClick: () => void;
  syncStatus: "idle" | "syncing" | "done" | "error";
  onLaunchEmail?: () => void;
  onLaunchWhatsApp?: () => void;
  onLaunchMarks?: () => void;
}

export default function TopBar({ agentCount, notificationCount, onNotificationClick, onSyncClick, syncStatus, onLaunchEmail, onLaunchWhatsApp, onLaunchMarks }: TopBarProps) {
  const { theme, toggle } = useTheme();
  const { windows } = useWindowManager();
  const [clock, setClock] = useState("");
  const [dateStr, setDateStr] = useState("");

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(
        now.toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
      setDateStr(
        now.toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
        })
      );
    };
    tick();
    const interval = setInterval(tick, 30000);
    return () => clearInterval(interval);
  }, []);

  const openWindowCount = windows.filter((w) => w.state === "open").length;

  return (
    <header className="h-8 bg-zinc-950 flex items-center justify-between px-4 shrink-0 select-none z-50 relative">
      {/* Left: Activities */}
      <div className="flex items-center gap-3">
        <span className="text-[13px] font-medium text-white/90 hover:bg-white/10 px-2 py-0.5 rounded cursor-default transition-colors">
          Activities
        </span>
      </div>

      {/* Center: Date & Time (absolute centered) */}
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-1.5">
        <span className="text-[13px] text-white/90 font-medium">
          {dateStr} {clock}
        </span>
      </div>

      {/* Right: System tray icons */}
      <div className="flex items-center gap-1">
        {/* Sync indicator (subtle) */}
        <button
          onClick={onSyncClick}
          disabled={syncStatus === "syncing"}
          className="p-1.5 rounded hover:bg-white/10 transition-colors"
          title="Sync VTOP data"
        >
          <svg className={`w-3.5 h-3.5 text-white/70 ${syncStatus === "syncing" ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>

        {/* Wifi / Network icon */}
        <div className="p-1.5 rounded hover:bg-white/10 transition-colors cursor-default">
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.858 15.355-5.858 21.213 0" />
          </svg>
        </div>

        {/* Volume icon */}
        <div className="p-1.5 rounded hover:bg-white/10 transition-colors cursor-default">
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
          </svg>
        </div>

        {/* Notification bell */}
        <button
          onClick={onNotificationClick}
          className="relative p-1.5 rounded hover:bg-white/10 transition-colors"
          aria-label="Notifications"
        >
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          {notificationCount > 0 && (
            <span className="absolute top-0 right-0 w-2 h-2 bg-blue-400 rounded-full" />
          )}
        </button>

        {/* Power / user icon */}
        <button
          onClick={toggle}
          className="p-1.5 rounded hover:bg-white/10 transition-colors"
          aria-label="Toggle theme"
        >
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728M12 2v4" />
          </svg>
        </button>
      </div>
    </header>
  );
}
