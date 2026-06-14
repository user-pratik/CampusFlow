"use client";

import { useEffect, useRef, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";
import WindowChat from "./WindowChat";

interface CourseRisk {
  course_code: string;
  course_title: string;
  current_percentage: number;
  attended: number;
  total: number;
  risk_level: "safe" | "warning" | "critical";
  max_skippable: number;
  classes_needed_to_reach_75: number;
}

interface RiskResponse {
  risks: CourseRisk[];
  summary: {
    total_courses: number;
    critical: number;
    warning: number;
    safe: number;
  };
  message?: string;
}

function skipMessage(risk: CourseRisk): string {
  if (risk.total === 0) return "No data yet";

  // Calculate what percentage would be if they skip one more class
  const newPct = (risk.attended / (risk.total + 1)) * 100;

  if (risk.risk_level === "critical") {
    return `Need ${risk.classes_needed_to_reach_75} more class${risk.classes_needed_to_reach_75 !== 1 ? "es" : ""} to reach 75%`;
  }

  if (risk.max_skippable === 0) {
    return `Skip today → drops to ${newPct.toFixed(1)}% (below 75%)`;
  }

  return `Can skip ${risk.max_skippable} more · skip today → ${newPct.toFixed(1)}%`;
}

function riskBadgeClasses(level: "safe" | "warning" | "critical"): string {
  switch (level) {
    case "critical":
      return "bg-urgent/10 text-urgent border-urgent/20";
    case "warning":
      return "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20";
    case "safe":
      return "bg-success/10 text-success border-success/20";
  }
}

function riskIcon(level: "safe" | "warning" | "critical"): string {
  switch (level) {
    case "critical":
      return "🚨";
    case "warning":
      return "⚠️";
    case "safe":
      return "✅";
  }
}

function AttendanceRiskWindowContent() {
  const [data, setData] = useState<RiskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRisk() {
      try {
        const res = await fetch("/api/attendance/risk", { cache: "no-store" });
        if (!res.ok) {
          setError("Could not fetch attendance risk data");
          setLoading(false);
          return;
        }
        const json: RiskResponse = await res.json();
        setData(json);
        setLoading(false);
      } catch {
        setError("Unable to reach backend");
        setLoading(false);
      }
    }
    fetchRisk();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-secondary py-4">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span>Attendance Agent analyzing risk...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-xs text-urgent py-2">
        <p>⚠️ {error}</p>
        <p className="text-secondary mt-1">Make sure the backend is running and VTOP is synced.</p>
      </div>
    );
  }

  if (!data || data.risks.length === 0) {
    return (
      <div className="text-center py-4">
        <p className="text-2xl mb-2">📊</p>
        <p className="text-sm text-foreground font-medium">No attendance data</p>
        <p className="text-xs text-secondary mt-1">Sync VTOP first to get attendance records.</p>
      </div>
    );
  }

  // Sort: critical first, then warning, then safe
  const sortedRisks = [...data.risks].sort((a, b) => {
    const order = { critical: 0, warning: 1, safe: 2 };
    return order[a.risk_level] - order[b.risk_level];
  });

  return (
    <div className="space-y-2">
      {/* Summary strip */}
      <div className="flex items-center gap-3 px-1 pb-2 border-b border-border">
        {data.summary.critical > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-urgent/10 text-urgent font-medium">
            {data.summary.critical} critical
          </span>
        )}
        {data.summary.warning > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 font-medium">
            {data.summary.warning} warning
          </span>
        )}
        {data.summary.safe > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-success/10 text-success font-medium">
            {data.summary.safe} safe
          </span>
        )}
      </div>

      {/* Per-course cards */}
      {sortedRisks.map((risk, index) => (
        <div
          key={`${risk.course_code}-${index}`}
          className={`p-2.5 rounded-md border ${riskBadgeClasses(risk.risk_level)}`}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-sm shrink-0">{riskIcon(risk.risk_level)}</span>
              <span className="text-xs font-medium text-foreground truncate">
                {risk.course_code}
              </span>
            </div>
            <span className="text-xs font-semibold text-foreground shrink-0">
              {risk.current_percentage}%
            </span>
          </div>
          <p className="text-[11px] text-secondary mt-0.5 truncate pl-6">
            {risk.course_title}
          </p>
          <div className="flex items-center justify-between mt-1.5 pl-6">
            <p className="text-[10px] text-secondary">
              {risk.attended}/{risk.total} classes
            </p>
            <p className="text-[10px] text-foreground font-medium">
              {skipMessage(risk)}
            </p>
          </div>
        </div>
      ))}

      {/* In-window conversational follow-up */}
      <WindowChat
        agentType="attendance_risk"
        contextData={{ risks: sortedRisks, summary: data.summary }}
      />
    </div>
  );
}

/**
 * Hook to spawn the Attendance Risk Agent floating window.
 *
 * Usage:
 * - `spawn()` — manually trigger (e.g. user asks "how's my attendance")
 * - `checkAndSpawn()` — fetch risk data and only spawn if warning/critical found
 *   (placeholder for scheduled checks in Prompt 9)
 */
export function useAttendanceRiskAgent() {
  const { spawnWindow } = useWindowManager();
  const spawnedRef = useRef(false);

  const spawn = () => {
    spawnWindow(
      "Academic Agent",
      "Attendance Check",
      <AttendanceRiskWindowContent />,
      {
        agentIcon: "📊",
        size: { width: 400, height: 380 },
        position: { x: 440, y: 60 },
      }
    );
  };

  /**
   * Check attendance risk and only spawn the window if there are
   * warning or critical courses. Placeholder for scheduled agent check.
   */
  const checkAndSpawn = async () => {
    if (spawnedRef.current) return;
    try {
      const res = await fetch("/api/attendance/risk", { cache: "no-store" });
      if (!res.ok) return;
      const data: RiskResponse = await res.json();
      if (data.summary && (data.summary.critical > 0 || data.summary.warning > 0)) {
        spawnedRef.current = true;
        spawn();
      }
    } catch {
      // Silently fail — agent won't spawn if backend is unreachable
    }
  };

  return { spawn, checkAndSpawn };
}
