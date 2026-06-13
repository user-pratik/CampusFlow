/**
 * Chat engine — powered by the real backend agentic pipeline.
 * Falls back to local processing only if the backend is unreachable.
 */

import { PanelType, SuggestedAction, WidgetData } from "./types";
import { sendChatMessage, ChatApiResponse } from "./api";

export interface AIResponse {
  content: string;
  actions?: SuggestedAction[];
  panel?: PanelType;
  panelData?: Record<string, unknown>;
  widget?: WidgetData;
}

/**
 * Main entry point — sends user query to the backend orchestrator agent.
 * The backend handles:
 * - Intent classification (academic, schedule, action, connector, general)
 * - Context gathering from DB (marks, attendance, tasks)
 * - Routing to specialist agents
 * - Conversation memory (multi-turn awareness)
 * - Action queue management (alarms, reminders, etc.)
 */
export async function getAIResponseAsync(query: string): Promise<AIResponse> {
  try {
    const response: ChatApiResponse = await sendChatMessage(query);

    // Map backend actions to frontend SuggestedAction format
    const actions: SuggestedAction[] = (response.actions || []).map((a) => ({
      label: a.label,
      type: (a.type as SuggestedAction["type"]) || "reply",
      payload: a.payload,
    }));

    // Map panel name to PanelType
    const panel = response.panel as PanelType | undefined;

    // Extract widget data from panel_data
    const widget = extractWidgetData(response);

    return {
      content: response.response,
      actions,
      panel: panel || undefined,
      panelData: response.panel_data || undefined,
      widget,
    };
  } catch (error) {
    console.error("Backend chat failed, using fallback:", error);
    return getFallbackResponse(query);
  }
}

/**
 * Extract structured widget data from the backend response.
 * The backend sends schedule/calendar/task data in panel_data and pending_actions.
 */
function extractWidgetData(response: ChatApiResponse): WidgetData | undefined {
  const panelData = response.panel_data;
  const intent = response.intent;
  const pendingActions = response.pending_actions || [];

  // Schedule widget — from ScheduleAgent
  if (intent === "schedule" && panelData?.schedule) {
    const schedule = panelData.schedule as Record<string, unknown>;
    return {
      type: "schedule",
      schedule: {
        schedule_type: schedule.schedule_type as string,
        date: schedule.date as string,
        blocks: (schedule.blocks as Array<Record<string, unknown>> || []).map((b) => ({
          time: (b.time as string) || "",
          activity: (b.activity as string) || "",
          subject: b.subject as string | null,
          priority: (b.priority as "high" | "medium" | "low") || "medium",
          duration_minutes: b.duration_minutes as number,
        })),
        daily_goals: schedule.daily_goals as string[],
        weekly_focus: schedule.weekly_focus as string[],
      },
    };
  }

  // Calendar widget — from ConnectorAgent when showing calendar
  if (intent === "connector" && response.panel === "calendar") {
    const calendarEvents = panelData?.calendar_events as Array<Record<string, unknown>> | undefined;
    if (calendarEvents && calendarEvents.length > 0) {
      return {
        type: "calendar",
        calendar: calendarEvents.map((e) => ({
          title: (e.title as string) || "",
          date: (e.date as string) || "",
          start_time: (e.start_time as string) || "",
          end_time: e.end_time as string | undefined,
          location: (e.location as string) || "",
          type: (e.type as "exam" | "deadline" | "meeting" | "event") || "event",
          course_code: e.course_code as string | null,
          notes: e.notes as string | undefined,
        })),
      };
    }
  }

  // Task list widget — from pending actions (reminders/schedule items)
  if (pendingActions.length > 0) {
    const tasks = pendingActions.map((a) => ({
      title: (a.display_text as string) || (a.data as Record<string, unknown>)?.title as string || (a.title as string) || "Task",
      deadline: (a.data as Record<string, unknown>)?.time as string || (a.data as Record<string, unknown>)?.date as string,
      priority: ((a.data as Record<string, unknown>)?.priority as "high" | "medium" | "low") || (a.priority as "high" | "medium" | "low") || "medium",
      completed: false,
    }));
    return {
      type: "task_list",
      tasks,
    };
  }

  return undefined;
}

/**
 * Fallback response when backend is unreachable.
 */
function getFallbackResponse(query: string): AIResponse {
  return {
    content:
      "I'm having trouble connecting to the AI backend right now. " +
      "Make sure the backend server is running (python run.py) and try again.\n\n" +
      "In the meantime, you can check your data directly using the panels on the right.",
    actions: [
      { label: "Check attendance", type: "navigate", payload: "attendance" },
      { label: "View marks", type: "navigate", payload: "marks" },
      { label: "Show calendar", type: "navigate", payload: "calendar" },
    ],
  };
}
