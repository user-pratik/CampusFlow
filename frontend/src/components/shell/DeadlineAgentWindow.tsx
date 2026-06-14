"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";
import WindowChat from "./WindowChat";

// ─── Types ───────────────────────────────────────────────────────────────────

interface DeadlineItem {
  id: number;
  title: string;
  due_datetime: string;
  category: string;
  source: string;
  status: string;
  days_until: number;
}

interface WeekGroup {
  label: string;
  week_start: string;
  deadlines: DeadlineItem[];
}

interface TimelineResponse {
  weeks: WeekGroup[];
  total: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  exam: "bg-urgent/10 text-urgent",
  fee: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
  placement: "bg-accent-light text-accent",
  academic: "bg-surface-hover text-secondary",
  event: "bg-success/10 text-success",
};

const CATEGORY_ICONS: Record<string, string> = {
  exam: "📝",
  fee: "💰",
  placement: "💼",
  academic: "📚",
  event: "📅",
};

function daysLabel(days: number): string {
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days < 0) return "Overdue";
  return `${days}d`;
}

function daysUrgencyClass(days: number): string {
  if (days <= 1) return "bg-urgent/10 text-urgent";
  if (days <= 3) return "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400";
  return "bg-surface-hover text-secondary";
}

// ─── Window Content ──────────────────────────────────────────────────────────

function DeadlineWindowContent() {
  const [weeks, setWeeks] = useState<WeekGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTimeline = useCallback(async () => {
    try {
      const res = await fetch("/api/deadlines/timeline", { cache: "no-store" });
      if (res.ok) {
        const data: TimelineResponse = await res.json();
        setWeeks(data.weeks);
        setTotal(data.total);
        setError(null);
      } else {
        setError("Failed to load deadlines");
      }
    } catch {
      setError("Unable to reach backend");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetch("/api/deadlines/sync", { method: "POST" });
      // Refetch after sync
      await fetchTimeline();
    } catch {
      // silent
    }
    setSyncing(false);
  };

  const handleMarkDone = async (id: number) => {
    // Optimistic update
    setWeeks((prev) =>
      prev.map((week) => ({
        ...week,
        deadlines: week.deadlines.filter((d) => d.id !== id),
      })).filter((week) => week.deadlines.length > 0)
    );
    setTotal((prev) => prev - 1);

    try {
      await fetch(`/api/deadlines/${id}?status=completed`, { method: "PATCH" });
    } catch {
      // Revert on error by refetching
      fetchTimeline();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-secondary py-4">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span>Deadline Agent loading timeline...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-3">
        <div className="text-xs text-urgent py-2">
          <p>⚠️ {error}</p>
          <p className="text-secondary mt-1">Make sure the backend is running.</p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-xs px-3 py-1.5 bg-accent text-white rounded-md hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          {syncing ? "Syncing..." : "Sync Now"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-secondary">
          {total} upcoming deadline{total !== 1 ? "s" : ""}
        </span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[10px] px-2 py-1 bg-accent/10 text-accent rounded-md hover:bg-accent/20 transition-colors disabled:opacity-40"
        >
          <span className={syncing ? "animate-spin" : ""}>↻</span>
          {syncing ? "Syncing" : "Sync"}
        </button>
      </div>

      {/* Empty state */}
      {weeks.length === 0 && (
        <div className="text-center py-4">
          <p className="text-2xl mb-2">✅</p>
          <p className="text-sm text-foreground font-medium">No upcoming deadlines!</p>
          <p className="text-xs text-secondary mt-1">
            Hit Sync to pull from Gmail and calendar.
          </p>
        </div>
      )}

      {/* Weeks */}
      {weeks.map((week) => (
        <div key={week.week_start} className="space-y-1.5">
          <p className="text-[10px] text-secondary font-medium uppercase tracking-wide px-1">
            {week.label}
          </p>
          {week.deadlines.map((d) => (
            <div
              key={d.id}
              className="flex items-start gap-2 p-2 rounded-md bg-surface border border-border group"
            >
              {/* Checkbox */}
              <button
                onClick={() => handleMarkDone(d.id)}
                className="mt-0.5 w-4 h-4 rounded border border-border flex items-center justify-center shrink-0 hover:border-accent hover:bg-accent/10 transition-colors group-hover:border-secondary"
                title="Mark as done"
              >
                <svg
                  className="w-2.5 h-2.5 text-transparent group-hover:text-secondary transition-colors"
                  viewBox="0 0 12 12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path d="M2 6l3 3 5-5" />
                </svg>
              </button>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-xs shrink-0">
                      {CATEGORY_ICONS[d.category] || "📌"}
                    </span>
                    <span className="text-xs font-medium text-foreground truncate">
                      {d.title}
                    </span>
                  </div>
                  <span
                    className={`text-[9px] px-1.5 py-0.5 rounded shrink-0 font-medium ${daysUrgencyClass(d.days_until)}`}
                  >
                    {daysLabel(d.days_until)}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1 text-[10px] text-secondary">
                  <span
                    className={`px-1 py-0.5 rounded ${CATEGORY_COLORS[d.category] || "bg-surface-hover text-secondary"}`}
                  >
                    {d.category}
                  </span>
                  <span>
                    {new Date(d.due_datetime).toLocaleDateString("en-IN", {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                  <span className="text-secondary/60">· {d.source}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}

      {/* In-window conversational follow-up */}
      <WindowChat
        agentType="deadlines"
        contextData={{ weeks, total }}
      />
    </div>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Hook to spawn the Deadline Agent floating window.
 *
 * Usage:
 * - `spawn()` — open the Upcoming Deadlines window
 */
export function useDeadlineAgent() {
  const { spawnWindow } = useWindowManager();

  const spawn = useCallback(() => {
    spawnWindow(
      "Deadline Agent",
      "Upcoming Deadlines",
      <DeadlineWindowContent />,
      {
        agentIcon: "⏰",
        size: { width: 380, height: 440 },
        position: { x: 70, y: 70 },
      }
    );
  }, [spawnWindow]);

  return { spawn };
}
