/**
 * CampusFlow API client.
 * Real data: VTOP (attendance, marks, academic profile, semesters, sync), notices, tasks, digest, profile
 * Fabricated: WhatsApp messages, emails, calendar, suggested groups, timetable (from mockData.json)
 */

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Real Backend Types ──────────────────────────────────────────────────────

export interface Profile {
  name: string;
  reg_no: string;
  branch: string;
  college: string;
  interests: string[];
  current_focus: string;
}

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

// ─── Real Backend Fetchers ───────────────────────────────────────────────────

export async function fetchProfile(): Promise<Profile> {
  const res = await fetch(`${BASE}/api/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json();
}

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
  if (!data || "message" in data) return null;
  return data as AcademicProfileData;
}

export async function fetchSemesters(): Promise<Record<string, string>> {
  const res = await fetch(`${BASE}/api/academic/semesters`, { cache: "no-store" });
  if (!res.ok) return {};
  const data = await res.json();
  return data.semesters || {};
}

export async function triggerVtopSync(semesterId?: string): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/academic/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ semester_id: semesterId || null }),
  });
  if (!res.ok) throw new Error("Failed to trigger VTOP sync");
  return res.json();
}

export async function fetchNotices(): Promise<Notice[]> {
  const res = await fetch(`${BASE}/api/notices`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchTasks(): Promise<Task[]> {
  const res = await fetch(`${BASE}/api/tasks`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchLatestDigest(): Promise<Digest | null> {
  const res = await fetch(`${BASE}/api/digest/latest`, { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json();
  if ("message" in data) return null;
  return data as Digest;
}

export async function triggerDigest(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/digest/trigger`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger digest");
  return res.json();
}

// ─── Service Status & Sync ───────────────────────────────────────────────────

export interface ServiceStatus {
  ngrok: { active: boolean; url: string | null };
  whatsapp: { connected: boolean; state: string };
  vtop: { session_valid: boolean };
}

export async function fetchServiceStatus(): Promise<ServiceStatus> {
  const res = await fetch(`${BASE}/api/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch service status");
  return res.json();
}

export async function triggerFullSync(): Promise<{ status: string; summary?: Record<string, unknown>; error?: string }> {
  const res = await fetch(`${BASE}/api/academic/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error("Failed to trigger sync");
  return res.json();
}

export async function triggerFullSetup(): Promise<Record<string, string>> {
  const res = await fetch(`${BASE}/api/academic/full-sync`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to trigger full sync");
  return res.json();
}

// ─── Agentic Chat API ────────────────────────────────────────────────────────

export interface ChatApiResponse {
  response: string;
  intent: string;
  sub_intent: string;
  actions: Array<{ label: string; type: string; payload?: string }>;
  pending_actions: Array<Record<string, unknown>>;
  panel: string | null;
  panel_data: Record<string, unknown> | null;
}

export async function sendChatMessage(
  message: string,
  sessionId: string = "default"
): Promise<ChatApiResponse> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}

export async function getPendingActions(): Promise<{
  actions: Array<Record<string, unknown>>;
  count: number;
}> {
  const res = await fetch(`${BASE}/api/chat/actions`, { cache: "no-store" });
  if (!res.ok) return { actions: [], count: 0 };
  return res.json();
}

export async function completeAction(
  actionId: string
): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/chat/actions/${actionId}/complete`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to complete action");
  return res.json();
}

export async function getChatHistory(
  sessionId: string = "default"
): Promise<{ messages: Array<Record<string, unknown>>; count: number }> {
  const res = await fetch(`${BASE}/api/chat/history/${sessionId}`, {
    cache: "no-store",
  });
  if (!res.ok) return { messages: [], count: 0 };
  return res.json();
}

export async function clearChatHistory(
  sessionId: string = "default"
): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/chat/history/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to clear history");
  return res.json();
}
