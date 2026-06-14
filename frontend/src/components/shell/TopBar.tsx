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

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(
        now.toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
    };
    tick();
    const interval = setInterval(tick, 30000);
    return () => clearInterval(interval);
  }, []);

  const openWindowCount = windows.filter((w) => w.state === "open").length;

  return (
    <header className="h-10 bg-panel-bg border-b border-border flex items-center justify-between px-4 shrink-0 select-none z-50">
      {/* Left: Logo + Agent status */}
      <div className="flex items-center gap-4">
        <span className="font-display text-sm font-semibold text-foreground tracking-tight">
          CampusFlow
        </span>
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-secondary">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          <span>{agentCount} agent{agentCount !== 1 ? "s" : ""} active</span>
        </div>
        {openWindowCount > 0 && (
          <span className="text-xs text-secondary hidden md:inline">
            · {openWindowCount} window{openWindowCount !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Right: Launchers + Sync + Clock + Notification + Theme */}
      <div className="flex items-center gap-3">
        {/* Quick launcher buttons */}
        <div className="hidden md:flex items-center gap-1">
          {onLaunchEmail && (
            <button
              onClick={onLaunchEmail}
              className="px-2 py-1 rounded text-[11px] bg-surface hover:bg-surface-hover text-secondary hover:text-foreground transition-colors"
              title="Open Email Intelligence"
            >
              📧 Email
            </button>
          )}
          {onLaunchWhatsApp && (
            <button
              onClick={onLaunchWhatsApp}
              className="px-2 py-1 rounded text-[11px] bg-surface hover:bg-surface-hover text-secondary hover:text-foreground transition-colors"
              title="Open WhatsApp Messages"
            >
              💬 WhatsApp
            </button>
          )}
          {onLaunchMarks && (
            <button
              onClick={onLaunchMarks}
              className="px-2 py-1 rounded text-[11px] bg-surface hover:bg-surface-hover text-secondary hover:text-foreground transition-colors"
              title="Open GPA Projection"
            >
              📊 Marks
            </button>
          )}
        </div>

        {/* VTOP Sync button */}
        <button
          onClick={onSyncClick}
          disabled={syncStatus === "syncing"}
          className={`hidden sm:flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium transition-colors ${
            syncStatus === "syncing"
              ? "bg-accent/20 text-accent cursor-wait"
              : syncStatus === "done"
              ? "bg-success/10 text-success"
              : syncStatus === "error"
              ? "bg-urgent/10 text-urgent"
              : "bg-surface hover:bg-surface-hover text-secondary hover:text-foreground"
          }`}
          title="Sync VTOP data (attendance, marks, timetable)"
        >
          <span className={syncStatus === "syncing" ? "animate-spin" : ""}>
            {syncStatus === "syncing" ? "↻" : syncStatus === "done" ? "✓" : syncStatus === "error" ? "✗" : "🔄"}
          </span>
          <span>
            {syncStatus === "syncing" ? "Syncing..." : syncStatus === "done" ? "Synced" : syncStatus === "error" ? "Failed" : "Sync"}
          </span>
        </button>

        <span className="text-xs text-secondary font-mono">{clock}</span>

        <button
          onClick={onNotificationClick}
          className="relative p-1 rounded hover:bg-surface transition-colors"
          aria-label="Notifications"
        >
          <svg
            className="w-4 h-4 text-secondary"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
          {notificationCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-urgent text-white text-[9px] font-bold rounded-full flex items-center justify-center">
              {notificationCount > 9 ? "9+" : notificationCount}
            </span>
          )}
        </button>

        <button
          onClick={toggle}
          className="p-1 rounded hover:bg-surface transition-colors text-secondary"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>
      </div>
    </header>
  );
}
