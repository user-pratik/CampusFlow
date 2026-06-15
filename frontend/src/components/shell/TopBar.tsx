"use client";

import { useState, useEffect } from "react";
import { useTheme } from "../ThemeProvider";
import { useWindowManager } from "@/lib/windowManager";
import { useTimetableAgent } from "./TimetableAgentWindow";
import { useAttendanceRiskAgent } from "./AttendanceRiskAgentWindow";
import { useGPAAgent } from "./GPAAgentWindow";

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
  const { spawn: spawnTimetable } = useTimetableAgent();
  const { checkAndSpawn: spawnAttendance } = useAttendanceRiskAgent();
  const { spawn: spawnGPA } = useGPAAgent();
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
      {/* Left: Brand */}
      <div className="flex items-center gap-3">
        <span className="text-[13px] font-bold text-white/90 hover:bg-white/10 px-2 py-0.5 rounded cursor-default transition-colors">
          CampusFlow
        </span>
      </div>

      {/* Center: Date & Time (absolute centered) */}
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-1.5">
        <span className="text-[13px] text-white/90 font-medium">
          {dateStr} {clock}
        </span>
      </div>

      {/* Right: Academic tools + Notification + Sync */}
      <div className="flex items-center gap-1">
        {/* Attendance */}
        <button
          onClick={spawnAttendance}
          className="p-1.5 rounded hover:bg-white/10 transition-colors"
          title="Attendance Tracker"
        >
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>

        {/* Today's Schedule */}
        <button
          onClick={() => spawnTimetable("today")}
          className="p-1.5 rounded hover:bg-white/10 transition-colors"
          title="Today's Schedule"
        >
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
          </svg>
        </button>

        {/* GPA Estimator */}
        <button
          onClick={spawnGPA}
          className="p-1.5 rounded hover:bg-white/10 transition-colors"
          title="GPA Estimator"
        >
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 00-.491 6.347A48.62 48.62 0 0112 20.904a48.62 48.62 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.636 50.636 0 00-2.658-.813A59.906 59.906 0 0112 3.493a59.903 59.903 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5" />
          </svg>
        </button>

        {/* Sync indicator */}
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

        {/* Notification bell with blinking alert LED */}
        <button
          onClick={onNotificationClick}
          className="relative p-1.5 rounded hover:bg-white/10 transition-colors"
          aria-label="Notifications"
        >
          <svg className="w-3.5 h-3.5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span className="absolute top-0 right-0 flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
        </button>

        {/* Theme toggle (power icon position) */}
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
