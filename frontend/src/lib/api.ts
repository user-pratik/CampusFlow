/**
 * CampusFlow API client.
 * Consumes the FastAPI backend at localhost:8000.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface Profile {
  name: string;
  branch: string;
  college: string;
  interests: string[];
  current_focus: string;
}

export interface Notice {
  id: number;
  text_hash: string;
  source_group: string;
  raw_text: string;
  parsed_title: string;
  category: string;
  is_processed: boolean;
  created_at: string;
}

export interface Task {
  id: number;
  title: string;
  deadline: string;
  status: string;
  related_notice_id: number | null;
  is_conflict: boolean;
}

export interface Digest {
  id: number;
  content: string;
  generated_at: string;
}

// ─── Fetchers ────────────────────────────────────────────────────────────────

export async function fetchProfile(): Promise<Profile> {
  const res = await fetch(`${BASE}/api/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json();
}

export async function fetchNotices(): Promise<Notice[]> {
  const res = await fetch(`${BASE}/api/notices`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch notices");
  return res.json();
}

export async function fetchTasks(): Promise<Task[]> {
  const res = await fetch(`${BASE}/api/tasks`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch tasks");
  return res.json();
}

export async function fetchLatestDigest(): Promise<Digest | null> {
  const res = await fetch(`${BASE}/api/digest/latest`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch digest");
  const data = await res.json();
  // Backend returns {"message": "No digest available"} when empty
  if ("message" in data) return null;
  return data as Digest;
}

export async function triggerDigest(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/digest/trigger`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to trigger digest");
  return res.json();
}

// ─── Phase 6: Academic Data Types ────────────────────────────────────────────

export interface AttendanceRecord {
  id: number;
  course_code: string;
  course_title: string;
  percentage: number;
  attended: number;
  total: number;
  updated_at: string;
}

export interface CourseMarkRecord {
  id: number;
  course_code: string;
  course_title: string;
  mark_title: string;
  max_mark: number | null;
  weightage_pct: number | null;
  score: number | null;
  weightage_mark: number | null;
  status: string | null;
  updated_at: string;
}

export interface AcademicProfileData {
  id: number;
  cgpa: number;
  total_credits: number;
  overall_attendance: number | null;
  semester_name: string | null;
  updated_at: string;
}

// ─── Phase 6: Academic Fetchers ──────────────────────────────────────────────

export async function fetchAttendance(): Promise<AttendanceRecord[]> {
  const res = await fetch(`${BASE}/api/academic/attendance`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchMarks(): Promise<CourseMarkRecord[]> {
  const res = await fetch(`${BASE}/api/academic/marks`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchAcademicProfile(): Promise<AcademicProfileData | null> {
  const res = await fetch(`${BASE}/api/academic/profile`, { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json();
  if (!data || !("cgpa" in data)) return null;
  return data as AcademicProfileData;
}

export async function triggerVtopSync(semesterId?: string): Promise<{ status: string; summary?: Record<string, unknown> }> {
  const res = await fetch(`${BASE}/api/academic/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ semester_id: semesterId || null }),
  });
  if (!res.ok) throw new Error("Failed to trigger VTOP sync");
  return res.json();
}

export async function fetchSemesters(): Promise<Record<string, string>> {
  const res = await fetch(`${BASE}/api/academic/semesters`, { cache: "no-store" });
  if (!res.ok) return {};
  const data = await res.json();
  return data.semesters || {};
}
