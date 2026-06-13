"use client";

import { useEffect, useState } from "react";
import { fetchAttendance, fetchAcademicProfile, type AttendanceRecord, type AcademicProfileData } from "@/lib/api";

interface Props {
  data: Record<string, unknown>;
}

export default function AttendancePanel({ data }: Props) {
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([]);
  const [academic, setAcademic] = useState<AcademicProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const highlight = data?.highlight as string | undefined;

  useEffect(() => {
    Promise.all([fetchAttendance(), fetchAcademicProfile()])
      .then(([att, prof]) => {
        setAttendance(att);
        setAcademic(prof);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-sm text-secondary">Loading attendance...</p>;
  }

  if (attendance.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-secondary">No attendance data yet.</p>
        <p className="text-xs text-secondary mt-1">Sync VTOP to load your attendance.</p>
      </div>
    );
  }

  const avg = Math.round(
    attendance.reduce((s, a) => s + a.percentage, 0) / attendance.length
  );

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="bg-surface rounded-xl p-4">
        <p className="text-xs text-secondary uppercase tracking-wide">
          Overall Attendance
        </p>
        <p
          className={`text-3xl font-display font-light mt-1 ${
            avg < 75 ? "text-urgent" : "text-foreground"
          }`}
        >
          {academic?.overall_attendance?.toFixed(0) || avg}%
        </p>
        <p className="text-xs text-secondary mt-1">
          {academic?.semester_name || "Current Semester"}
        </p>
      </div>

      {/* Per-course */}
      <div className="space-y-2">
        {attendance.map((rec) => (
          <div
            key={rec.id}
            className={`p-3 rounded-lg border transition-colors ${
              highlight === rec.course_code
                ? "border-accent bg-accent-light"
                : "border-border bg-surface"
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">
                  {rec.course_code}
                </p>
                <p className="text-xs text-secondary mt-0.5">
                  {rec.course_title}
                </p>
              </div>
              <span
                className={`text-sm font-semibold tabular-nums ${
                  rec.percentage < 75 ? "text-urgent" : "text-success"
                }`}
              >
                {rec.percentage}%
              </span>
            </div>
            <div className="mt-2 w-full h-1.5 bg-border rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  rec.percentage < 75 ? "bg-urgent" : "bg-success"
                }`}
                style={{ width: `${Math.min(rec.percentage, 100)}%` }}
              />
            </div>
            <p className="text-[10px] text-secondary mt-1">
              {rec.attended}/{rec.total} classes attended
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
