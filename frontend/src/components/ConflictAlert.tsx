"use client";

import { useEffect, useState } from "react";
import { fetchTasks, type Task } from "@/lib/api";

export default function ConflictAlert() {
  const [conflicts, setConflicts] = useState<Task[]>([]);

  useEffect(() => {
    fetchTasks()
      .then((tasks) => setConflicts(tasks.filter((t) => t.is_conflict)))
      .catch(() => setConflicts([]));
  }, []);

  if (conflicts.length === 0) return null;

  return (
    <div className="w-full bg-[#FEF08A] border-b border-[#111827]/10">
      <div className="max-w-2xl mx-auto px-6 py-4">
        {conflicts.map((task) => (
          <p
            key={task.id}
            className="text-[#111827] text-sm font-medium tracking-tight"
          >
            <span className="mr-2">⚠️</span>
            Schedule conflict detected.{" "}
            <span className="font-semibold">{task.title}</span> overlaps with an
            existing deadline.
          </p>
        ))}
      </div>
    </div>
  );
}
