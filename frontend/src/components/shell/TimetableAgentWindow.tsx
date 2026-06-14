"use client";

import { useEffect, useRef } from "react";
import { useWindowManager } from "@/lib/windowManager";
import WindowChat from "./WindowChat";

interface TimetableSlot {
  id: number;
  course_code: string;
  course_name: string;
  start_time: string;
  end_time: string;
  slot_type: string;
  venue: string;
}

interface FreeSlot {
  start_time: string;
  end_time: string;
  duration_minutes: number;
}

interface FreeSlotsResponse {
  day: string;
  free_slots: FreeSlot[];
  total_free_minutes: number;
}

type TimetableResponse = Record<string, TimetableSlot[]>;

/** Merged timeline entry for display (class or free slot) */
interface TimelineEntry {
  type: "class" | "free";
  start_time: string;
  end_time: string;
  // class fields
  course_code?: string;
  course_name?: string;
  slot_type?: string;
  venue?: string;
  // free fields
  duration_minutes?: number;
}

function buildTimeline(classes: TimetableSlot[], freeSlots: FreeSlot[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [];

  for (const cls of classes) {
    entries.push({
      type: "class",
      start_time: cls.start_time,
      end_time: cls.end_time,
      course_code: cls.course_code,
      course_name: cls.course_name,
      slot_type: cls.slot_type,
      venue: cls.venue,
    });
  }

  for (const free of freeSlots) {
    entries.push({
      type: "free",
      start_time: free.start_time,
      end_time: free.end_time,
      duration_minutes: free.duration_minutes,
    });
  }

  // Sort by start_time
  entries.sort((a, b) => a.start_time.localeCompare(b.start_time));
  return entries;
}

function TimetableWindowContent({ day }: { day: string }) {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [totalFree, setTotalFree] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [timetableRes, freeSlotsRes] = await Promise.all([
          fetch("/api/timetable", { cache: "no-store" }),
          fetch(`/api/timetable/free-slots?day=${day}`, { cache: "no-store" }),
        ]);

        if (!timetableRes.ok || !freeSlotsRes.ok) {
          setError("Could not fetch timetable data");
          setLoading(false);
          return;
        }

        const timetableData: TimetableResponse = await timetableRes.json();
        const freeSlotsData: FreeSlotsResponse = await freeSlotsRes.json();

        const todayClasses = timetableData[freeSlotsData.day] || [];
        const entries = buildTimeline(todayClasses, freeSlotsData.free_slots);

        setTimeline(entries);
        setTotalFree(freeSlotsData.total_free_minutes);
        setLoading(false);
      } catch {
        setError("Unable to reach backend");
        setLoading(false);
      }
    }

    fetchData();
  }, [day]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-secondary py-4">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span>Timetable Agent loading schedule...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-xs text-urgent py-2">
        <p>⚠️ {error}</p>
        <p className="text-secondary mt-1">Make sure the backend is running.</p>
      </div>
    );
  }

  if (timeline.length === 0) {
    return (
      <div className="text-center py-4">
        <p className="text-2xl mb-2">🎉</p>
        <p className="text-sm text-foreground font-medium">No classes today!</p>
        <p className="text-xs text-secondary mt-1">You have the full day free (8am–6pm).</p>
      </div>
    );
  }

  const classCount = timeline.filter((e) => e.type === "class").length;
  const freeHours = Math.floor(totalFree / 60);
  const freeMinutes = totalFree % 60;

  return (
    <div className="space-y-1.5">
      {/* Summary bar */}
      <div className="flex items-center justify-between px-1 pb-2 border-b border-border mb-2">
        <span className="text-[10px] text-secondary">
          {classCount} class{classCount !== 1 ? "es" : ""}
        </span>
        <span className="text-[10px] text-success font-medium">
          {freeHours > 0 ? `${freeHours}h ` : ""}{freeMinutes > 0 ? `${freeMinutes}m` : ""} free
        </span>
      </div>

      {/* Timeline */}
      {timeline.map((entry, i) => (
        <div key={i}>
          {entry.type === "class" ? (
            <div className="flex items-start gap-2 p-2 rounded-md bg-surface border border-border">
              <div className="w-1 h-full min-h-[32px] rounded-full bg-accent shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-foreground truncate">
                    {entry.course_code}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${
                    entry.slot_type === "lab"
                      ? "bg-accent-light text-accent"
                      : "bg-surface-hover text-secondary"
                  }`}>
                    {entry.slot_type === "lab" ? "LAB" : "TH"}
                  </span>
                </div>
                <p className="text-[11px] text-secondary truncate">{entry.course_name}</p>
                <div className="flex items-center gap-2 mt-1 text-[10px] text-secondary">
                  <span>{entry.start_time}–{entry.end_time}</span>
                  {entry.venue && <span>· {entry.venue}</span>}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-success/5 border border-success/20">
              <span className="text-xs">☕</span>
              <span className="text-[11px] text-success font-medium">
                Free: {entry.start_time}–{entry.end_time}
              </span>
              <span className="text-[10px] text-secondary ml-auto">
                {entry.duration_minutes}min
              </span>
            </div>
          )}
        </div>
      ))}

      {/* In-window conversational follow-up */}
      <WindowChat
        agentType="timetable"
        contextData={{ timeline, totalFree, classCount }}
      />
    </div>
  );
}

// Need useState import at top level for the content component
import { useState } from "react";

/**
 * Spawns the Timetable Agent floating window.
 * Call this hook inside a component that has access to WindowManagerProvider.
 *
 * Returns a trigger function that can be called to spawn/re-spawn the window.
 */
export function useTimetableAgent() {
  const { spawnWindow } = useWindowManager();
  const spawnedRef = useRef(false);

  const spawn = (day: string = "today") => {
    const dayLabel = day === "today"
      ? new Date().toLocaleDateString("en-US", { weekday: "long" })
      : day;

    spawnWindow(
      "Schedule Agent",
      `Today's Schedule — ${dayLabel}`,
      <TimetableWindowContent day={day} />,
      {
        agentIcon: "📅",
        size: { width: 360, height: 420 },
        position: { x: 50, y: 50 },
      }
    );
  };

  /** Auto-spawn on first call (for app load) */
  const autoSpawn = () => {
    if (spawnedRef.current) return;
    spawnedRef.current = true;
    spawn("today");
  };

  return { spawn, autoSpawn };
}
