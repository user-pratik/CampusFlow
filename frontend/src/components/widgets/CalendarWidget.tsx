"use client";

import { CalendarEvent } from "@/lib/types";

interface Props {
  events: CalendarEvent[];
}

export default function CalendarWidget({ events }: Props) {
  const typeIcon = (type: string) => {
    switch (type) {
      case "exam": return "📝";
      case "deadline": return "⏰";
      case "meeting": return "👥";
      default: return "📌";
    }
  };

  const typeColor = (type: string) => {
    switch (type) {
      case "exam": return "border-l-urgent";
      case "deadline": return "border-l-accent";
      case "meeting": return "border-l-success";
      default: return "border-l-secondary";
    }
  };

  const daysUntil = (date: string) => {
    const diff = new Date(date).getTime() - Date.now();
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    if (days < 0) return "Passed";
    if (days === 0) return "Today";
    if (days === 1) return "Tomorrow";
    return `${days}d`;
  };

  const daysUntilColor = (date: string) => {
    const diff = new Date(date).getTime() - Date.now();
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    if (days <= 1) return "bg-urgent/20 text-urgent";
    if (days <= 3) return "bg-accent/20 text-accent";
    return "bg-success/20 text-success";
  };

  return (
    <div className="mt-3 space-y-2 max-w-full">
      {/* Header */}
      <div className="flex items-center gap-2 text-xs text-secondary">
        <span className="inline-flex items-center gap-1 bg-accent/10 text-accent px-2 py-0.5 rounded-full font-medium">
          📅 Calendar
        </span>
        <span>{events.length} events</span>
      </div>

      {/* Events */}
      <div className="space-y-1.5">
        {events.slice(0, 8).map((event, i) => (
          <div
            key={i}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-surface border-l-3 ${typeColor(event.type)}`}
          >
            <span className="text-sm shrink-0">{typeIcon(event.type)}</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground truncate">
                {event.course_code && (
                  <span className="text-accent">[{event.course_code}] </span>
                )}
                {event.title}
              </p>
              <p className="text-[10px] text-secondary">
                {new Date(event.date).toLocaleDateString("en-IN", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}
                {" · "}
                {event.start_time}
                {event.location && ` · ${event.location}`}
              </p>
            </div>
            <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded shrink-0 ${daysUntilColor(event.date)}`}>
              {daysUntil(event.date)}
            </span>
          </div>
        ))}
      </div>

      {events.length > 8 && (
        <p className="text-[10px] text-secondary text-center">
          +{events.length - 8} more events
        </p>
      )}
    </div>
  );
}
