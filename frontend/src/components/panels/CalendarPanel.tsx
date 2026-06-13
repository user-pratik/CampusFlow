"use client";

import mockData from "@/lib/mockData.json";

interface Props {
  data: Record<string, unknown>;
}

export default function CalendarPanel({ data }: Props) {
  const events = mockData.calendar;

  const typeIcon = (type: string) => {
    switch (type) {
      case "exam": return "📝";
      case "deadline": return "⏰";
      case "meeting": return "📌";
      default: return "📅";
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
    return `In ${days} days`;
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-secondary">
        {events.length} upcoming events
      </p>

      {events.map((event) => (
        <div
          key={event.id}
          className={`p-3 rounded-lg border border-border bg-surface border-l-4 ${typeColor(event.type)}`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">
                {typeIcon(event.type)} {event.title}
              </p>
              <p className="text-xs text-secondary mt-1">
                {new Date(event.date).toLocaleDateString("en-IN", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}{" "}
                at {event.time}
              </p>
              <p className="text-xs text-secondary mt-0.5">
                📍 {event.location}
              </p>
            </div>
            <span className="text-[10px] font-medium text-accent shrink-0 bg-accent-light px-2 py-1 rounded">
              {daysUntil(event.date)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
