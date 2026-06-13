"use client";

import { useState } from "react";
import { TaskItem } from "@/lib/types";

interface Props {
  tasks: TaskItem[];
}

export default function TaskListWidget({ tasks }: Props) {
  const [checkedTasks, setCheckedTasks] = useState<Set<number>>(new Set());

  const toggleTask = (index: number) => {
    setCheckedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const priorityDot = (p?: string) => {
    switch (p) {
      case "high": return "bg-urgent";
      case "medium": return "bg-accent";
      case "low": return "bg-success";
      default: return "bg-secondary";
    }
  };

  const completedCount = checkedTasks.size;
  const totalCount = tasks.length;
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="mt-3 space-y-2 max-w-full">
      {/* Header with progress */}
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1 text-xs bg-accent/10 text-accent px-2 py-0.5 rounded-full font-medium">
          ✅ Tasks
        </span>
        <span className="text-[10px] text-secondary">
          {completedCount}/{totalCount} done
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-border rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-300"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Task list */}
      <div className="space-y-1">
        {tasks.map((task, i) => {
          const isChecked = checkedTasks.has(i);
          return (
            <button
              key={i}
              onClick={() => toggleTask(i)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg border border-border text-left transition-all ${
                isChecked ? "bg-success/5 opacity-60" : "bg-surface hover:bg-surface/80"
              }`}
            >
              {/* Checkbox */}
              <span
                className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                  isChecked
                    ? "bg-success border-success text-white"
                    : "border-secondary"
                }`}
              >
                {isChecked && (
                  <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </span>

              {/* Priority dot */}
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${priorityDot(task.priority)}`} />

              {/* Task content */}
              <div className="flex-1 min-w-0">
                <p className={`text-xs font-medium truncate ${isChecked ? "line-through text-secondary" : "text-foreground"}`}>
                  {task.title}
                </p>
                {task.deadline && (
                  <p className="text-[10px] text-secondary">{task.deadline}</p>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
