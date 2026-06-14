"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";
import { useAttendanceRiskAgent } from "./AttendanceRiskAgentWindow";
import { useTimetableAgent } from "./TimetableAgentWindow";
import { useGPAAgent } from "./GPAAgentWindow";
import { usePlacementAgent } from "./PlacementAgentWindow";

// ─── Types ───────────────────────────────────────────────────────────────────

interface NotificationItem {
  id: number;
  title: string;
  message: string;
  source_agent: string;
  priority: string;
  is_read: boolean;
  link: string | null;
  created_at: string;
}

interface NotificationsResponse {
  notifications: NotificationItem[];
  unread_count: number;
  total: number;
}

// ─── Agent icon mapping ──────────────────────────────────────────────────────

const AGENT_ICONS: Record<string, string> = {
  "Attendance Agent": "📊",
  "Academic Agent": "📊",
  "Deadline Agent": "⏰",
  "Notice Agent": "📢",
  "Schedule Agent": "📅",
  "Timetable Agent": "🕐",
  "Digest Agent": "📰",
  "Connector Agent": "🔗",
  "Action Agent": "⚡",
  "GPA Agent": "🎯",
  "System": "🖥️",
};

const PRIORITY_COLORS: Record<string, string> = {
  urgent: "border-l-urgent",
  high: "border-l-urgent/60",
  normal: "border-l-accent/40",
  low: "border-l-border",
};

function getAgentIcon(agent: string): string {
  return AGENT_ICONS[agent] || "🔔";
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);

  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ─── Window Content ──────────────────────────────────────────────────────────

function NotificationCenterContent({
  onNavigate,
}: {
  onNavigate: (link: string) => void;
}) {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await fetch("/api/notifications?unread_only=true", { cache: "no-store" });
      if (res.ok) {
        const data: NotificationsResponse = await res.json();
        setNotifications(data.notifications);
        setError(null);
      }
    } catch {
      setError("Unable to reach backend");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchNotifications();
    // Poll every 60s
    pollRef.current = setInterval(fetchNotifications, 60000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchNotifications]);

  const markRead = async (id: number, link: string | null) => {
    // Optimistically mark as read in UI
    setNotifications((prev) => prev.filter((n) => n.id !== id));

    // Fire API call
    try {
      await fetch(`/api/notifications/${id}/read`, { method: "POST" });
    } catch {
      // silent — already removed from UI
    }

    // Navigate if link is set
    if (link) {
      onNavigate(link);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-secondary py-4">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span>Loading notifications...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-xs text-secondary py-4 text-center">
        <p>⚠️ {error}</p>
      </div>
    );
  }

  if (notifications.length === 0) {
    return (
      <div className="text-center py-6">
        <p className="text-2xl mb-2">✨</p>
        <p className="text-sm text-foreground font-medium">All caught up!</p>
        <p className="text-xs text-secondary mt-1">No unread notifications.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between px-1 pb-2 border-b border-border mb-2">
        <span className="text-[10px] text-secondary font-medium uppercase tracking-wide">
          Unread ({notifications.length})
        </span>
        <span className="text-[10px] text-secondary">Auto-refreshes every 60s</span>
      </div>

      {notifications.map((n) => (
        <button
          key={n.id}
          onClick={() => markRead(n.id, n.link)}
          className={`w-full text-left flex items-start gap-2.5 p-2.5 rounded-md border-l-2 hover:bg-surface transition-colors cursor-pointer ${
            PRIORITY_COLORS[n.priority] || PRIORITY_COLORS.normal
          }`}
        >
          <span className="text-sm shrink-0 mt-0.5">{getAgentIcon(n.source_agent)}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-foreground truncate">{n.title}</p>
              <span className="text-[9px] text-secondary shrink-0">
                {timeAgo(n.created_at)}
              </span>
            </div>
            <p className="text-[11px] text-secondary mt-0.5 line-clamp-2">{n.message}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[9px] text-secondary">{n.source_agent}</span>
              {n.link && (
                <span className="text-[9px] text-accent">→ Open</span>
              )}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Hook providing:
 * - `unreadCount` — live unread count (polled every 60s)
 * - `openNotificationCenter()` — spawns the notification center floating window
 */
export function useNotificationCenter() {
  const { spawnWindow } = useWindowManager();
  const { spawn: spawnAttendance } = useAttendanceRiskAgent();
  const { spawn: spawnTimetable } = useTimetableAgent();
  const { spawn: spawnGPA } = useGPAAgent();
  const { spawn: spawnPlacements } = usePlacementAgent();
  const [unreadCount, setUnreadCount] = useState(0);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const fetchCount = useCallback(async () => {
    try {
      const res = await fetch("/api/notifications?unread_only=true", { cache: "no-store" });
      if (res.ok) {
        const data: NotificationsResponse = await res.json();
        setUnreadCount(data.unread_count);
      }
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchCount();
    pollRef.current = setInterval(fetchCount, 60000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchCount]);

  const handleNavigate = useCallback(
    (link: string) => {
      // Route link to the appropriate agent window
      const lower = link.toLowerCase();
      if (lower.includes("placement")) {
        spawnPlacements();
      } else if (lower.includes("attendance") || lower.includes("risk")) {
        spawnAttendance();
      } else if (lower.includes("timetable") || lower.includes("schedule")) {
        spawnTimetable("today");
      } else if (lower.includes("gpa") || lower.includes("cgpa") || lower.includes("grade")) {
        spawnGPA();
      }
      // Refresh count after marking read
      setTimeout(fetchCount, 500);
    },
    [spawnAttendance, spawnTimetable, spawnGPA, spawnPlacements, fetchCount]
  );

  const openNotificationCenter = useCallback(() => {
    spawnWindow(
      "System",
      "Notification Center",
      <NotificationCenterContent onNavigate={handleNavigate} />,
      {
        agentIcon: "🔔",
        size: { width: 360, height: 380 },
        position: { x: 600, y: 40 },
      }
    );
    // Refresh count when opening
    fetchCount();
  }, [spawnWindow, handleNavigate, fetchCount]);

  return { unreadCount, openNotificationCenter };
}
