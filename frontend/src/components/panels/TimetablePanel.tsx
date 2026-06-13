"use client";

import { useState } from "react";
import mockData from "@/lib/mockData.json";

interface Props {
  data: Record<string, unknown>;
}

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

export default function TimetablePanel({ data }: Props) {
  const today = new Date().toLocaleDateString("en-US", { weekday: "long" });
  const [selectedDay, setSelectedDay] = useState(
    DAYS.includes(today) ? today : "Monday"
  );

  const timetable = mockData.timetable as Record<
    string,
    { time: string; course: string; room: string; type: string }[]
  >;

  const classes = timetable[selectedDay] || [];

  return (
    <div className="space-y-4">
      {/* Day selector */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {DAYS.map((day) => (
          <button
            key={day}
            onClick={() => setSelectedDay(day)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors shrink-0 ${
              selectedDay === day
                ? "bg-accent text-white"
                : "bg-surface text-secondary hover:text-foreground"
            }`}
          >
            {day.slice(0, 3)}
          </button>
        ))}
      </div>

      {/* Classes */}
      <div className="space-y-2">
        {classes.length === 0 ? (
          <p className="text-sm text-secondary text-center py-8">
            No classes on {selectedDay} 🎉
          </p>
        ) : (
          classes.map((cls, i) => (
            <div
              key={i}
              className="p-3 rounded-lg border border-border bg-surface"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-foreground">
                  {cls.course}
                </p>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    cls.type === "Lab"
                      ? "bg-accent-light text-accent"
                      : "bg-surface-hover text-secondary"
                  }`}
                >
                  {cls.type}
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-3 text-xs text-secondary">
                <span>🕐 {cls.time}</span>
                <span>📍 {cls.room}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
