"use client";

import { WidgetData } from "@/lib/types";
import ScheduleWidget from "./ScheduleWidget";
import CalendarWidget from "./CalendarWidget";
import TaskListWidget from "./TaskListWidget";

interface Props {
  widget: WidgetData;
}

/**
 * ChatWidget — renders the appropriate inline widget based on widget.type.
 * Used inside chat message bubbles to show structured data
 * (schedules, calendars, task checklists) visually.
 */
export default function ChatWidget({ widget }: Props) {
  if (!widget || !widget.type) return null;

  switch (widget.type) {
    case "schedule":
      if (widget.schedule) {
        return <ScheduleWidget data={widget.schedule} />;
      }
      return null;

    case "calendar":
      if (widget.calendar && widget.calendar.length > 0) {
        return <CalendarWidget events={widget.calendar} />;
      }
      return null;

    case "task_list":
      if (widget.tasks && widget.tasks.length > 0) {
        return <TaskListWidget tasks={widget.tasks} />;
      }
      return null;

    default:
      return null;
  }
}
