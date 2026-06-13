"use client";

import { WidgetData } from "@/lib/types";

interface Props {
  data: NonNullable<WidgetData["schedule"]>;
}

export default function ScheduleWidget({ data }: Props) {
  const blocks = data.blocks || [];
  const goals = data.daily_goals || [];
  const focus = data.weekly_focus || [];

  const priorityColor = (p: string) => {
    switch (p) {
      case "high": return "border-l-urgent bg-urgent/5";
      case "medium": return "border-l-accent bg-accent/5";
      case "low": return "border-l-success bg-success/5";
      default: return "border-l-secondary bg-surface";
    }
  };

  const priorityBadge = (p: string) => {
    switch (p) {
      case "high": return "bg-urgent/20 text-urgent";
      case "medium": return "bg-accent/20 text-accent";
      case "low": return "bg-success/20 text-success";
      default: return "bg-secondary/20 text-secondary";
    }
  };

  return (
    <div className="mt-3 space-y-3 max-w-full">
      {/* Header */}
      <div className="flex items-center gap-2 text-xs text-secondary">
        <span className="inline-flex items-center gap-1 bg-accent/10 text-accent px-2 py-0.5 rounded-full font-medium">
          📋 {data.schedule_type === "weekly" ? "Weekly" : "Daily"} Schedule
        </span>
        {data.date && (
          <span>
            {new Date(data.date).toLocaleDateString("en-IN", {
              weekday: "short",
              day: "numeric",
              month: "short",
            })}
          </span>
        )}
      </div>

      {/* Schedule blocks */}
      {blocks.length > 0 && (
        <div className="space-y-1.5">
          {blocks.map((block, i) => (
            <div
              key={i}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg border-l-3 border border-border ${priorityColor(block.priority)}`}
            >
              <span className="text-[11px] text-secondary font-mono shrink-0 w-24">
                {block.time}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-foreground truncate">
                  {block.activity}
                </p>
                {block.subject && (
                  <p className="text-[10px] text-secondary">{block.subject}</p>
                )}
              </div>
              <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${priorityBadge(block.priority)}`}>
                {block.priority}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Daily goals */}
      {goals.length > 0 && (
        <div className="pt-2 border-t border-border/50">
          <p className="text-[10px] font-medium text-secondary uppercase tracking-wide mb-1">
            Today&apos;s Goals
          </p>
          <ul className="space-y-1">
            {goals.map((goal, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                <span className="text-accent mt-0.5">○</span>
                <span>{goal}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Weekly focus */}
      {focus.length > 0 && (
        <div className="pt-2 border-t border-border/50">
          <p className="text-[10px] font-medium text-secondary uppercase tracking-wide mb-1">
            Focus Areas
          </p>
          <div className="flex flex-wrap gap-1.5">
            {focus.map((item, i) => (
              <span
                key={i}
                className="text-[10px] px-2 py-0.5 rounded-full bg-surface border border-border text-foreground"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
