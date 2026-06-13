"use client";

import { useEffect, useState } from "react";
import { fetchNotices, fetchTasks, type Notice, type Task } from "@/lib/api";

type FeedItem =
  | { kind: "task"; data: Task }
  | { kind: "notice"; data: Notice };

function categoryColor(category: string): string {
  switch (category) {
    case "Urgent":
      return "text-urgent";
    case "Event":
      return "text-blue-600";
    case "Academic":
      return "text-emerald-700";
    default:
      return "text-secondary";
  }
}

function relativeDeadline(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  const hours = Math.round(diff / (1000 * 60 * 60));
  if (hours < 0) return "Overdue";
  if (hours < 1) return "Due within the hour";
  if (hours < 24) return `${hours}h remaining`;
  const days = Math.round(hours / 24);
  return `${days}d remaining`;
}

export default function CampusFeed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchTasks(), fetchNotices()])
      .then(([tasks, notices]) => {
        const feed: FeedItem[] = [
          ...tasks
            .filter((t) => t.status === "pending")
            .map((t) => ({ kind: "task" as const, data: t })),
          ...notices
            .filter((n) => !n.is_processed)
            .map((n) => ({ kind: "notice" as const, data: n })),
        ];
        setItems(feed);
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <section className="max-w-2xl mx-auto px-6 py-8">
        <p className="text-secondary text-sm">Loading feed…</p>
      </section>
    );
  }

  if (items.length === 0) {
    return (
      <section className="max-w-2xl mx-auto px-6 py-8">
        <p className="text-secondary text-sm">
          No pending tasks or unprocessed notices. Your slate is clean.
        </p>
      </section>
    );
  }

  return (
    <section className="max-w-2xl mx-auto px-6 pb-16">
      <p className="text-secondary text-xs uppercase tracking-widest mb-4">
        Feed
      </p>

      <ul className="divide-y divide-border">
        {items.map((item) => {
          if (item.kind === "task") {
            const t = item.data;
            return (
              <li key={`task-${t.id}`} className="py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {t.title}
                    </p>
                    <p className="text-xs text-secondary mt-0.5">
                      {relativeDeadline(t.deadline)}
                    </p>
                  </div>
                  <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 bg-surface text-secondary">
                    Task
                  </span>
                </div>
              </li>
            );
          }

          const n = item.data;
          return (
            <li key={`notice-${n.id}`} className="py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {n.parsed_title}
                  </p>
                  <p className="text-xs text-secondary mt-0.5 truncate">
                    {n.source_group}
                  </p>
                </div>
                <span
                  className={`shrink-0 text-[10px] font-semibold uppercase tracking-wider ${categoryColor(n.category)}`}
                >
                  {n.category}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
