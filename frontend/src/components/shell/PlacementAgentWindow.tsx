"use client";

import { useCallback, useEffect, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";
import WindowChat from "./WindowChat";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChecklistItem {
  task: string;
  completed: boolean;
  round_type: string;
}

interface PlacementDriveData {
  id: number;
  company_name: string;
  role: string | null;
  drive_date: string | null;
  rounds: string[];
  status: string;
  applied: boolean;
  package: string | null;
  eligibility_status: string;
  eligible_degree: string | null;
  min_cgpa: number | null;
  checklist: {
    items: ChecklistItem[];
    total: number;
    completed: number;
  };
}

interface PlacementsResponse {
  drives: PlacementDriveData[];
  total: number;
  upcoming: number;
  eligible_count: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function eligibilityBadge(status: string): { label: string; cls: string } {
  switch (status) {
    case "Eligible":
      return { label: "✅ Eligible", cls: "bg-success/10 text-success border-success/20" };
    case "Likely Not Eligible":
      return { label: "❌ Not Eligible", cls: "bg-urgent/10 text-urgent border-urgent/20" };
    default:
      return { label: "❓ Unclear", cls: "bg-surface-hover text-secondary border-border" };
  }
}

function countdown(dateStr: string | null): string {
  if (!dateStr) return "Date TBD";
  const diff = Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  if (diff < 0) return "Passed";
  if (diff === 0) return "Today!";
  if (diff === 1) return "Tomorrow";
  return `in ${diff} days`;
}

function countdownUrgency(dateStr: string | null): string {
  if (!dateStr) return "text-secondary";
  const diff = Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  if (diff <= 1) return "text-urgent font-semibold";
  if (diff <= 3) return "text-yellow-600 dark:text-yellow-400 font-medium";
  return "text-secondary";
}

// ─── Drive Card ──────────────────────────────────────────────────────────────

function DriveCard({ drive, onRefresh }: { drive: PlacementDriveData; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [toggling, setToggling] = useState(false);

  const badge = eligibilityBadge(drive.eligibility_status);

  const handleAppliedToggle = async () => {
    setToggling(true);
    try {
      await fetch(`/api/placements/${drive.id}/applied`, { method: "POST" });
      onRefresh();
    } catch { /* silent */ }
    setToggling(false);
  };

  const handleChecklistToggle = async (index: number) => {
    try {
      await fetch(`/api/placements/${drive.id}/checklist?item_index=${index}`, { method: "PATCH" });
      onRefresh();
    } catch { /* silent */ }
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="p-2.5 bg-surface">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm">💼</span>
            <span className="text-xs font-semibold text-foreground truncate">
              {drive.company_name}
            </span>
          </div>
          <span className={`text-[10px] ${countdownUrgency(drive.drive_date)}`}>
            {countdown(drive.drive_date)}
          </span>
        </div>

        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          {drive.role && (
            <span className="text-[10px] text-secondary">{drive.role}</span>
          )}
          {drive.package && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-light text-accent">
              {drive.package}
            </span>
          )}
          <span className={`text-[10px] px-1.5 py-0.5 rounded border ${badge.cls}`}>
            {badge.label}
          </span>
        </div>

        {/* Rounds */}
        <div className="flex gap-1 mt-1.5 flex-wrap">
          {drive.rounds.map((r) => (
            <span key={r} className="text-[9px] px-1.5 py-0.5 rounded bg-surface-hover text-secondary">
              {r}
            </span>
          ))}
        </div>

        {/* Action row */}
        <div className="flex items-center justify-between mt-2">
          <button
            onClick={handleAppliedToggle}
            disabled={toggling}
            className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${
              drive.applied
                ? "bg-success/10 text-success border-success/20"
                : "bg-surface-hover text-secondary border-border hover:border-accent"
            }`}
          >
            {drive.applied ? "✓ Applied" : "Mark Applied"}
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[10px] text-accent hover:underline"
          >
            {expanded ? "Hide prep" : `Prep (${drive.checklist.completed}/${drive.checklist.total})`}
          </button>
        </div>
      </div>

      {/* Expandable checklist */}
      {expanded && (
        <div className="p-2 border-t border-border space-y-1 max-h-40 overflow-y-auto">
          {drive.checklist.items.map((item, i) => (
            <button
              key={i}
              onClick={() => handleChecklistToggle(i)}
              className="w-full flex items-start gap-2 text-left p-1 rounded hover:bg-surface-hover transition-colors"
            >
              <span className={`mt-0.5 w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 ${
                item.completed
                  ? "bg-success/20 border-success text-success"
                  : "border-border"
              }`}>
                {item.completed && (
                  <svg className="w-2 h-2" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <path d="M2 6l3 3 5-5" />
                  </svg>
                )}
              </span>
              <span className={`text-[10px] ${item.completed ? "line-through text-secondary" : "text-foreground"}`}>
                {item.task}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Window Content ──────────────────────────────────────────────────────────

function PlacementWindowContent() {
  const [drives, setDrives] = useState<PlacementDriveData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const fetchDrives = useCallback(async () => {
    try {
      const res = await fetch("/api/placements", { cache: "no-store" });
      if (res.ok) {
        const data: PlacementsResponse = await res.json();
        setDrives(data.drives);
        setError(null);
      } else {
        setError("Failed to load placements");
      }
    } catch {
      setError("Unable to reach backend");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDrives();
  }, [fetchDrives]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetch("/api/placements/sync", { method: "POST" });
      await fetchDrives();
    } catch { /* silent */ }
    setSyncing(false);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-secondary py-4">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span>Placement Agent scanning drives...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-3">
        <p className="text-xs text-urgent">⚠️ {error}</p>
        <button
          onClick={handleSync}
          className="text-xs px-3 py-1.5 bg-accent text-white rounded-md"
        >
          Sync Now
        </button>
      </div>
    );
  }

  const upcoming = drives.filter((d) => d.status === "upcoming" || d.status === "applied");

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-secondary">
          {upcoming.length} active drive{upcoming.length !== 1 ? "s" : ""}
        </span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[10px] px-2 py-1 bg-accent/10 text-accent rounded-md hover:bg-accent/20 transition-colors disabled:opacity-40"
        >
          <span className={syncing ? "animate-spin" : ""}>↻</span>
          {syncing ? "Syncing" : "Sync"}
        </button>
      </div>

      {/* Empty state */}
      {drives.length === 0 && (
        <div className="text-center py-4">
          <p className="text-2xl mb-2">💼</p>
          <p className="text-sm text-foreground font-medium">No placement drives yet</p>
          <p className="text-xs text-secondary mt-1">
            Hit Sync to scan your inbox for placement emails.
          </p>
        </div>
      )}

      {/* Drive cards */}
      {upcoming.map((drive) => (
        <DriveCard key={drive.id} drive={drive} onRefresh={fetchDrives} />
      ))}

      {/* Completed/past drives (collapsed) */}
      {drives.filter((d) => d.status === "completed" || d.status === "missed").length > 0 && (
        <details className="text-[10px] text-secondary">
          <summary className="cursor-pointer hover:text-foreground">
            Past drives ({drives.filter((d) => d.status !== "upcoming" && d.status !== "applied").length})
          </summary>
          <div className="mt-2 space-y-2">
            {drives
              .filter((d) => d.status === "completed" || d.status === "missed")
              .map((drive) => (
                <DriveCard key={drive.id} drive={drive} onRefresh={fetchDrives} />
              ))}
          </div>
        </details>
      )}

      {/* In-window conversational follow-up */}
      <WindowChat
        agentType="placements"
        contextData={{
          drives: upcoming.map((d) => ({
            company: d.company_name,
            role: d.role,
            drive_date: d.drive_date,
            eligibility_status: d.eligibility_status,
            rounds: d.rounds,
          })),
        }}
      />
    </div>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Hook to spawn the Placement Agent floating window.
 */
export function usePlacementAgent() {
  const { spawnWindow } = useWindowManager();

  const spawn = useCallback(() => {
    spawnWindow(
      "Placement Agent",
      "Placement Drives",
      <PlacementWindowContent />,
      {
        agentIcon: "💼",
        size: { width: 400, height: 460 },
        position: { x: 120, y: 80 },
      }
    );
  }, [spawnWindow]);

  return { spawn };
}
