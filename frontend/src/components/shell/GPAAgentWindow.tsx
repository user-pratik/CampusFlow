"use client";

import { useEffect, useRef, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";
import WindowChat from "./WindowChat";

const GRADES = ["S", "A", "B", "C", "D", "E", "F"] as const;

interface ProjectionResult {
  current_cgpa: number;
  current_credits: number;
  projected_cgpa: number;
  delta: number;
  course_code: string;
  expected_grade: string;
  grade_points: number;
  credits_used: number;
  error?: string;
}

interface RequiredGradeEntry {
  course_code: string;
  min_grade: string;
  grade_points: number;
  credits: number;
}

interface RequiredGradeResult {
  current_cgpa: number;
  current_credits: number;
  target_cgpa: number;
  achievable: boolean;
  required_grades: RequiredGradeEntry[];
  uniform_grade_needed: string | null;
  message: string;
  error?: string;
}

interface CourseInfo {
  course_code: string;
  course_title: string;
}

// ─── What-If Tab ─────────────────────────────────────────────────────────────

function WhatIfTab({ courses }: { courses: CourseInfo[] }) {
  const [selectedCourse, setSelectedCourse] = useState(courses[0]?.course_code || "");
  const [selectedGrade, setSelectedGrade] = useState<string>("A");
  const [result, setResult] = useState<ProjectionResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleProject = async () => {
    if (!selectedCourse || !selectedGrade) return;
    setLoading(true);
    try {
      const res = await fetch(
        `/api/academic/projection?course=${encodeURIComponent(selectedCourse)}&grade=${selectedGrade}&credits=3`,
        { cache: "no-store" }
      );
      if (res.ok) {
        const data: ProjectionResult = await res.json();
        setResult(data);
      }
    } catch {
      // silently fail
    }
    setLoading(false);
  };

  // Auto-calculate on selection change
  useEffect(() => {
    if (selectedCourse && selectedGrade) {
      handleProject();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCourse, selectedGrade]);

  return (
    <div className="space-y-3">
      <p className="text-[10px] text-secondary uppercase tracking-wide font-medium">
        What-If Calculator
      </p>

      {/* Course selector */}
      <div className="space-y-1.5">
        <label className="text-[11px] text-secondary">Course</label>
        <select
          value={selectedCourse}
          onChange={(e) => setSelectedCourse(e.target.value)}
          className="w-full text-xs bg-surface border border-border rounded-md px-2.5 py-1.5 text-foreground outline-none focus:border-accent"
        >
          {courses.map((c) => (
            <option key={c.course_code} value={c.course_code}>
              {c.course_code} — {c.course_title}
            </option>
          ))}
        </select>
      </div>

      {/* Grade selector */}
      <div className="space-y-1.5">
        <label className="text-[11px] text-secondary">Expected Grade</label>
        <div className="flex gap-1">
          {GRADES.map((g) => (
            <button
              key={g}
              onClick={() => setSelectedGrade(g)}
              className={`flex-1 text-xs py-1.5 rounded-md border transition-colors font-medium ${
                selectedGrade === g
                  ? "bg-accent text-white border-accent"
                  : "bg-surface border-border text-secondary hover:text-foreground hover:border-foreground/20"
              }`}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {/* Result */}
      {loading && (
        <div className="flex items-center gap-2 text-[11px] text-secondary py-2">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          Calculating...
        </div>
      )}

      {result && !result.error && !loading && (
        <div className="p-3 rounded-md bg-surface border border-border space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-secondary">Current CGPA</span>
            <span className="text-sm font-semibold text-foreground">{result.current_cgpa.toFixed(2)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-secondary">Projected CGPA</span>
            <span className="text-sm font-semibold text-foreground">{result.projected_cgpa.toFixed(4)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-secondary">Change</span>
            <span className={`text-xs font-medium ${result.delta >= 0 ? "text-success" : "text-urgent"}`}>
              {result.delta >= 0 ? "+" : ""}{result.delta.toFixed(4)}
            </span>
          </div>
        </div>
      )}

      {result?.error && (
        <p className="text-xs text-urgent">{result.error}</p>
      )}
    </div>
  );
}

// ─── Target CGPA Tab ─────────────────────────────────────────────────────────

function TargetTab() {
  const [target, setTarget] = useState("9.0");
  const [result, setResult] = useState<RequiredGradeResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCalculate = async () => {
    const val = parseFloat(target);
    if (isNaN(val) || val < 0 || val > 10) return;
    setLoading(true);
    try {
      const res = await fetch(
        `/api/academic/required-grade?target_cgpa=${val}`,
        { cache: "no-store" }
      );
      if (res.ok) {
        const data: RequiredGradeResult = await res.json();
        setResult(data);
      }
    } catch {
      // silently fail
    }
    setLoading(false);
  };

  return (
    <div className="space-y-3">
      <p className="text-[10px] text-secondary uppercase tracking-wide font-medium">
        Target CGPA Planner
      </p>

      <div className="flex items-end gap-2">
        <div className="flex-1 space-y-1">
          <label className="text-[11px] text-secondary">Target CGPA</label>
          <input
            type="number"
            min="0"
            max="10"
            step="0.1"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCalculate()}
            className="w-full text-xs bg-surface border border-border rounded-md px-2.5 py-1.5 text-foreground outline-none focus:border-accent"
          />
        </div>
        <button
          onClick={handleCalculate}
          disabled={loading}
          className="px-3 py-1.5 bg-accent text-white text-xs font-medium rounded-md hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          {loading ? "..." : "Calculate"}
        </button>
      </div>

      {/* Result */}
      {result && !result.error && (
        <div className="space-y-2">
          <div className={`p-2.5 rounded-md border ${
            result.achievable
              ? "bg-success/5 border-success/20"
              : "bg-urgent/5 border-urgent/20"
          }`}>
            <p className="text-xs text-foreground font-medium">
              {result.achievable ? "✅ Achievable" : "❌ Not Achievable"}
            </p>
            <p className="text-[11px] text-secondary mt-1">{result.message}</p>
          </div>

          {result.achievable && result.required_grades.length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] text-secondary font-medium">Per-course minimum:</p>
              {result.required_grades.map((rg) => (
                <div
                  key={rg.course_code}
                  className="flex items-center justify-between px-2 py-1.5 rounded bg-surface border border-border"
                >
                  <span className="text-[11px] text-foreground">{rg.course_code}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-secondary">{rg.credits} cr</span>
                    <span className="text-xs font-semibold text-accent">{rg.min_grade}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {result?.error && (
        <p className="text-xs text-urgent">{result.error}</p>
      )}
    </div>
  );
}

// ─── Main GPA Window Content ─────────────────────────────────────────────────

function GPAWindowContent() {
  const [tab, setTab] = useState<"whatif" | "target">("whatif");
  const [courses, setCourses] = useState<CourseInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadCourses() {
      try {
        const res = await fetch("/api/academic/marks", { cache: "no-store" });
        if (res.ok) {
          const marks: Array<{ course_code: string; course_title: string }> = await res.json();
          // Deduplicate
          const seen = new Set<string>();
          const unique: CourseInfo[] = [];
          for (const m of marks) {
            if (!seen.has(m.course_code)) {
              seen.add(m.course_code);
              unique.push({ course_code: m.course_code, course_title: m.course_title });
            }
          }
          setCourses(unique);
        }
      } catch {
        // fall through
      }
      setLoading(false);
    }
    loadCourses();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-secondary py-4">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span>GPA Agent loading courses...</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Tab switcher */}
      <div className="flex rounded-lg bg-surface border border-border p-0.5">
        <button
          onClick={() => setTab("whatif")}
          className={`flex-1 text-[11px] py-1.5 rounded-md font-medium transition-colors ${
            tab === "whatif"
              ? "bg-panel-bg text-foreground shadow-sm"
              : "text-secondary hover:text-foreground"
          }`}
        >
          What-If
        </button>
        <button
          onClick={() => setTab("target")}
          className={`flex-1 text-[11px] py-1.5 rounded-md font-medium transition-colors ${
            tab === "target"
              ? "bg-panel-bg text-foreground shadow-sm"
              : "text-secondary hover:text-foreground"
          }`}
        >
          Target CGPA
        </button>
      </div>

      {/* Content */}
      {tab === "whatif" ? (
        courses.length > 0 ? (
          <WhatIfTab courses={courses} />
        ) : (
          <div className="text-center py-4">
            <p className="text-xs text-secondary">No courses found. Sync VTOP first.</p>
          </div>
        )
      ) : (
        <TargetTab />
      )}

      {/* In-window conversational follow-up */}
      <WindowChat
        agentType="gpa_projection"
        contextData={{ courses: courses.map((c) => c.course_code) }}
      />
    </div>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Hook to spawn the GPA Agent floating window.
 *
 * Usage:
 * - `spawn()` — open the GPA calculator window
 */
export function useGPAAgent() {
  const { spawnWindow } = useWindowManager();

  const spawn = () => {
    spawnWindow(
      "Academic Agent",
      "GPA Calculator",
      <GPAWindowContent />,
      {
        agentIcon: "🎯",
        size: { width: 380, height: 440 },
        position: { x: 100, y: 100 },
      }
    );
  };

  return { spawn };
}
