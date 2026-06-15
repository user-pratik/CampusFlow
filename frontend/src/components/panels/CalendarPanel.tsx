"use client";

import { useEffect, useState } from "react";

interface CalendarEvent {
  title: string;
  start: string;
  end: string;
  location: string;
  description: string;
  link: string;
}

interface Props {
  data: Record<string, unknown>;
}

export default function CalendarPanel({ data }: Props) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchEvents() {
      try {
        const res = await fetch("/api/gmail/calendar-events", { cache: "no-store" });
        if (res.ok) {
          const d = await res.json();
          setEvents(d.events || []);
        }
      } catch {
        // silent
      }
      setLoading(false);
    }
    fetchEvents();
  }, []);

  const daysUntil = (dateStr: string) => {
    const date = new Date(dateStr);
    const diff = date.getTime() - Date.now();
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    if (days < 0) return "Passed";
    if (days === 0) return "Today";
    if (days === 1) return "Tomorrow";
    return `In ${days} days`;
  };

  const daysColor = (dateStr: string) => {
    const date = new Date(dateStr);
    const diff = date.getTime() - Date.now();
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    if (days <= 1) return "bg-red-900/50 text-red-300";
    if (days <= 3) return "bg-orange-900/50 text-orange-300";
    return "bg-emerald-900/50 text-emerald-300";
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-400 py-4">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Loading calendar events...
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="text-center py-4">
        <p className="text-sm text-slate-400">No upcoming events</p>
        <p className="text-xs text-slate-500 mt-1">
          Ask CampusFlow to add events via chat
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400 mb-2">
        {events.length} upcoming event{events.length !== 1 ? "s" : ""}
      </p>

      {events.map((event, i) => (
        <div
          key={i}
          className="p-3 rounded-lg border border-slate-800 bg-slate-900"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-100 truncate">
                📅 {event.title}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {new Date(event.start).toLocaleDateString("en-IN", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}
                {" · "}
                {new Date(event.start).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
              {event.location && (
                <p className="text-xs text-slate-500 mt-0.5">
                  📍 {event.location}
                </p>
              )}
            </div>
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 ${daysColor(event.start)}`}>
              {daysUntil(event.start)}
            </span>
          </div>
          {event.link && (
            <a
              href={event.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-emerald-400 hover:underline mt-1.5 inline-block"
            >
              Open in Google Calendar →
            </a>
          )}
        </div>
      ))}
    </div>
  );
}
