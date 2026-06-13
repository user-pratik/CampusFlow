"use client";

import { useEffect, useState } from "react";
import { fetchMarks, fetchAcademicProfile, type CourseMarkRecord, type AcademicProfileData } from "@/lib/api";

interface Props {
  data: Record<string, unknown>;
}

interface CourseGroup {
  course_code: string;
  course_title: string;
  marks: CourseMarkRecord[];
  total_weightage: number;
}

function groupByCourse(marks: CourseMarkRecord[]): CourseGroup[] {
  const map = new Map<string, CourseGroup>();
  for (const m of marks) {
    if (!map.has(m.course_code)) {
      map.set(m.course_code, {
        course_code: m.course_code,
        course_title: m.course_title,
        marks: [],
        total_weightage: 0,
      });
    }
    const g = map.get(m.course_code)!;
    g.marks.push(m);
    g.total_weightage += m.weightage_mark ?? 0;
  }
  return Array.from(map.values());
}

export default function MarksPanel({ data }: Props) {
  const [groups, setGroups] = useState<CourseGroup[]>([]);
  const [academic, setAcademic] = useState<AcademicProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    Promise.all([fetchMarks(), fetchAcademicProfile()])
      .then(([marks, prof]) => {
        setGroups(groupByCourse(marks));
        setAcademic(prof);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggleCourse = (code: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  };

  if (loading) {
    return <p className="text-sm text-secondary">Loading marks...</p>;
  }

  if (groups.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-secondary">No marks data yet.</p>
        <p className="text-xs text-secondary mt-1">Sync VTOP to load your grades.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      {academic && (
        <div className="bg-surface rounded-xl p-4">
          <div className="flex items-baseline gap-6">
            <div>
              <p className="text-xs text-secondary uppercase tracking-wide">CGPA</p>
              <p className="text-3xl font-display font-light text-foreground mt-1">
                {academic.cgpa.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-secondary uppercase tracking-wide">Credits</p>
              <p className="text-2xl font-display font-light text-foreground mt-1">
                {academic.total_credits}
              </p>
            </div>
          </div>
          {academic.semester_name && (
            <p className="text-xs text-secondary mt-2">{academic.semester_name}</p>
          )}
        </div>
      )}

      {/* Course-wise marks */}
      <div className="space-y-2">
        {groups.map((g) => {
          const isOpen = expanded.has(g.course_code);
          return (
            <div key={g.course_code} className="rounded-lg border border-border bg-surface overflow-hidden">
              <button
                onClick={() => toggleCourse(g.course_code)}
                className="w-full p-3 flex items-center justify-between text-left hover:bg-surface-hover transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{g.course_code}</p>
                  <p className="text-xs text-secondary">{g.course_title}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground tabular-nums">
                    {g.total_weightage.toFixed(1)}%
                  </span>
                  <span className="text-xs text-secondary">{isOpen ? "▾" : "▸"}</span>
                </div>
              </button>

              {isOpen && (
                <div className="px-3 pb-3 border-t border-border">
                  <table className="w-full text-xs mt-2">
                    <thead>
                      <tr className="text-secondary">
                        <th className="text-left pb-1 font-medium">Assessment</th>
                        <th className="text-right pb-1 font-medium">Score</th>
                        <th className="text-right pb-1 font-medium">Wt%</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {g.marks.map((m) => (
                        <tr key={m.id}>
                          <td className="py-1.5 text-foreground">{m.mark_title}</td>
                          <td className="py-1.5 text-right tabular-nums text-foreground">
                            {m.score ?? "—"}/{m.max_mark ?? "—"}
                          </td>
                          <td className="py-1.5 text-right tabular-nums font-semibold text-foreground">
                            {m.weightage_mark?.toFixed(1) ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
