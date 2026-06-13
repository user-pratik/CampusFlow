"use client";

import { useEffect, useState } from "react";
import {
  fetchAttendance,
  fetchMarks,
  fetchAcademicProfile,
  fetchSemesters,
  triggerVtopSync,
  type AttendanceRecord,
  type CourseMarkRecord,
  type AcademicProfileData,
} from "@/lib/api";

interface CourseGroup {
  course_code: string;
  course_title: string;
  marks: CourseMarkRecord[];
  aggregate_weightage: number;
}

function groupMarksByCourse(marks: CourseMarkRecord[]): CourseGroup[] {
  const map = new Map<string, CourseGroup>();

  for (const mark of marks) {
    const key = mark.course_code;
    if (!map.has(key)) {
      map.set(key, {
        course_code: mark.course_code,
        course_title: mark.course_title,
        marks: [],
        aggregate_weightage: 0,
      });
    }
    const group = map.get(key)!;
    group.marks.push(mark);
    group.aggregate_weightage += mark.weightage_mark ?? 0;
  }

  return Array.from(map.values());
}

export default function AcademicDashboard() {
  const [profile, setProfile] = useState<AcademicProfileData | null>(null);
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([]);
  const [courseGroups, setCourseGroups] = useState<CourseGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Semester selection state
  const [semesters, setSemesters] = useState<Record<string, string>>({});
  const [selectedSemester, setSelectedSemester] = useState<string>("");
  const [syncing, setSyncing] = useState(false);
  const [semestersLoading, setSemestersLoading] = useState(false);

  // Load semesters on mount
  useEffect(() => {
    setSemestersLoading(true);
    fetchSemesters()
      .then((sems) => {
        setSemesters(sems);
        // Default to first (latest) semester
        const keys = Object.keys(sems);
        if (keys.length > 0) setSelectedSemester(sems[keys[0]]);
      })
      .catch(() => {})
      .finally(() => setSemestersLoading(false));
  }, []);

  // Load academic data on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = () => {
    setLoading(true);
    Promise.all([fetchAcademicProfile(), fetchAttendance(), fetchMarks()])
      .then(([p, a, m]) => {
        setProfile(p);
        setAttendance(a);
        setCourseGroups(groupMarksByCourse(m));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  const handleSync = async () => {
    if (!selectedSemester) return;
    setSyncing(true);
    try {
      await triggerVtopSync(selectedSemester);
      // Reload data after sync
      await new Promise((r) => setTimeout(r, 1000));
      loadData();
    } catch (e) {
      // silent
    } finally {
      setSyncing(false);
    }
  };

  const toggleCourse = (code: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  if (loading && !semestersLoading) {
    return (
      <section className="max-w-2xl mx-auto px-6 py-8">
        <p className="text-secondary text-sm">Loading academic data…</p>
      </section>
    );
  }

  return (
    <section className="max-w-2xl mx-auto px-6 py-10 space-y-10">
      {/* ─── Semester Selector ─── */}
      <div>
        <p className="text-secondary text-xs uppercase tracking-widest mb-3">
          Select Semester
        </p>
        <div className="flex items-center gap-3">
          <select
            value={selectedSemester}
            onChange={(e) => setSelectedSemester(e.target.value)}
            disabled={semestersLoading || syncing}
            className="flex-1 px-3 py-2 text-sm text-foreground bg-surface border border-border rounded-none appearance-none focus:outline-none focus:border-foreground disabled:opacity-40"
          >
            {semestersLoading ? (
              <option>Loading semesters…</option>
            ) : Object.keys(semesters).length === 0 ? (
              <option>No semesters available</option>
            ) : (
              Object.entries(semesters).map(([name, id]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))
            )}
          </select>
          <button
            onClick={handleSync}
            disabled={syncing || !selectedSemester}
            className="px-4 py-2 text-xs font-medium text-foreground bg-surface border border-border hover:bg-foreground hover:text-background transition-colors disabled:opacity-40"
          >
            {syncing ? "Syncing…" : "Load Data"}
          </button>
        </div>
      </div>
      {/* ─── Profile: CGPA + Credits + Overall Attendance ─── */}
      {profile && profile.cgpa != null && (
        <div>
          <p className="text-secondary text-xs uppercase tracking-widest mb-1">
            Academic Standing
            {profile.semester_name && (
              <span className="ml-2 normal-case tracking-normal text-secondary/60">
                — {profile.semester_name}
              </span>
            )}
          </p>
          <div className="flex items-baseline gap-10 mt-4">
            <div>
              <p className="font-display text-5xl font-light text-foreground tracking-tight">
                {profile.cgpa.toFixed(2)}
              </p>
              <p className="text-xs text-secondary mt-1 uppercase tracking-wide">CGPA</p>
            </div>
            <div>
              <p className="font-display text-3xl font-light text-foreground">
                {profile.total_credits}
              </p>
              <p className="text-xs text-secondary mt-1 uppercase tracking-wide">Credits</p>
            </div>
            {profile.overall_attendance != null && (
              <div>
                <p
                  className={`font-display text-3xl font-light ${
                    profile.overall_attendance < 75 ? "text-[#DC2626]" : "text-foreground"
                  }`}
                >
                  {profile.overall_attendance.toFixed(0)}%
                </p>
                <p className="text-xs text-secondary mt-1 uppercase tracking-wide">
                  Overall Attendance
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Attendance Per Course ─── */}
      {attendance.length > 0 && (
        <div>
          <p className="text-secondary text-xs uppercase tracking-widest mb-4">
            Attendance by Course
          </p>
          <ul className="divide-y divide-border">
            {attendance.map((rec) => (
              <li key={rec.id} className="py-3 flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {rec.course_code}
                  </p>
                  <p className="text-xs text-secondary mt-0.5">
                    {rec.attended}/{rec.total} classes
                  </p>
                </div>
                <span
                  className={`text-sm font-semibold tabular-nums ${
                    rec.percentage < 75 ? "text-[#DC2626]" : "text-foreground"
                  }`}
                >
                  {rec.percentage}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ─── Marks Per Course (expandable) ─── */}
      {courseGroups.length > 0 && (
        <div>
          <p className="text-secondary text-xs uppercase tracking-widest mb-4">
            Marks by Course
          </p>
          <div className="space-y-1">
            {courseGroups.map((group) => {
              const isOpen = expanded.has(group.course_code);
              return (
                <div key={group.course_code} className="border-b border-border">
                  {/* Course header — click to expand */}
                  <button
                    onClick={() => toggleCourse(group.course_code)}
                    className="w-full py-3 flex items-center justify-between text-left hover:bg-surface/50 transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground">
                        {group.course_code}
                        <span className="ml-2 font-normal text-secondary">
                          {group.course_title}
                        </span>
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-sm font-semibold tabular-nums text-foreground">
                        {group.aggregate_weightage.toFixed(1)}%
                      </span>
                      <span className="text-xs text-secondary">
                        {isOpen ? "▾" : "▸"}
                      </span>
                    </div>
                  </button>

                  {/* Expanded marks table */}
                  {isOpen && (
                    <div className="pb-4 pl-2 overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-left text-secondary uppercase tracking-wider">
                            <th className="pb-2 pr-3 font-medium">Title</th>
                            <th className="pb-2 pr-3 font-medium text-right">Max</th>
                            <th className="pb-2 pr-3 font-medium text-right">Wt%</th>
                            <th className="pb-2 pr-3 font-medium text-right">Score</th>
                            <th className="pb-2 pr-3 font-medium text-right">Wt Mark</th>
                            <th className="pb-2 font-medium">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/50">
                          {group.marks.map((mark) => (
                            <tr key={mark.id}>
                              <td className="py-2 pr-3 text-foreground">
                                {mark.mark_title}
                              </td>
                              <td className="py-2 pr-3 text-right tabular-nums text-secondary">
                                {mark.max_mark ?? "—"}
                              </td>
                              <td className="py-2 pr-3 text-right tabular-nums text-secondary">
                                {mark.weightage_pct ?? "—"}
                              </td>
                              <td className="py-2 pr-3 text-right tabular-nums font-medium text-foreground">
                                {mark.score ?? "—"}
                              </td>
                              <td className="py-2 pr-3 text-right tabular-nums font-semibold text-foreground">
                                {mark.weightage_mark != null
                                  ? mark.weightage_mark.toFixed(1)
                                  : "—"}
                              </td>
                              <td className="py-2 text-secondary">
                                {mark.status || "—"}
                              </td>
                            </tr>
                          ))}
                          {/* Aggregate row */}
                          <tr className="border-t border-foreground/10">
                            <td className="py-2 pr-3 font-semibold text-foreground" colSpan={4}>
                              Total Weightage
                            </td>
                            <td className="py-2 pr-3 text-right tabular-nums font-bold text-foreground">
                              {group.aggregate_weightage.toFixed(1)}
                            </td>
                            <td></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
