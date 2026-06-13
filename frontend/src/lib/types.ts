export type PanelType =
  | "attendance"
  | "marks"
  | "whatsapp"
  | "email"
  | "calendar"
  | "timetable"
  | "groups"
  | null;

export type WidgetType = "schedule" | "calendar" | "task_list" | null;

export interface ScheduleBlock {
  time: string;
  activity: string;
  subject?: string | null;
  priority: "high" | "medium" | "low";
  duration_minutes?: number;
}

export interface CalendarEvent {
  id?: number;
  title: string;
  date: string;
  start_time: string;
  end_time?: string;
  location: string;
  type: "exam" | "deadline" | "meeting" | "event";
  course_code?: string | null;
  notes?: string;
}

export interface TaskItem {
  title: string;
  deadline?: string;
  priority?: "high" | "medium" | "low";
  completed?: boolean;
}

export interface WidgetData {
  type: WidgetType;
  schedule?: {
    schedule_type?: string;
    date?: string;
    blocks?: ScheduleBlock[];
    daily_goals?: string[];
    weekly_focus?: string[];
  };
  calendar?: CalendarEvent[];
  tasks?: TaskItem[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  suggestedActions?: SuggestedAction[];
  panel?: PanelType;
  panelData?: Record<string, unknown>;
  widget?: WidgetData;
}

export interface SuggestedAction {
  label: string;
  type: "reply" | "schedule" | "reminder" | "open_link" | "navigate";
  payload?: string;
}
