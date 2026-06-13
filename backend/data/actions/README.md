# Action Queue

This directory stores pending actions from the CampusFlow agent system.

Each action is saved as an individual JSON file (`{type}_{id}.json`) and also appended to `action_log.json`.

## Action Types

### alarm
```json
{
  "id": "abc12345",
  "type": "alarm",
  "status": "pending",
  "created_at": "2026-06-14T08:00:00",
  "data": {
    "time": "07:30",
    "date": "2026-06-15",
    "label": "Wake up for DSA class",
    "repeat": "weekdays"
  },
  "display_text": "Alarm set for 7:30 AM on weekdays — DSA class"
}
```

### reminder
```json
{
  "id": "def67890",
  "type": "reminder",
  "status": "pending",
  "created_at": "2026-06-14T10:00:00",
  "data": {
    "time": "17:00",
    "date": "2026-06-16",
    "message": "Submit OS assignment on VTOP",
    "priority": "high"
  },
  "display_text": "Reminder: Submit OS assignment by 5 PM"
}
```

### whatsapp_message
```json
{
  "id": "ghi11223",
  "type": "whatsapp_message",
  "status": "pending",
  "created_at": "2026-06-14T12:00:00",
  "data": {
    "recipient": "Rahul",
    "message": "Hey, can you share the ML lab manual?",
    "group": null
  },
  "display_text": "Send WhatsApp message to Rahul"
}
```

### open_link
```json
{
  "id": "jkl44556",
  "type": "open_link",
  "status": "pending",
  "created_at": "2026-06-14T09:00:00",
  "data": {
    "url": "https://vtop.vit.ac.in/vtop/assignments",
    "label": "OS Assignment submission",
    "portal": "vtop"
  },
  "display_text": "Open VTOP — OS Assignment"
}
```

### calendar_event
```json
{
  "id": "mno77889",
  "type": "calendar_event",
  "status": "pending",
  "created_at": "2026-06-14T11:00:00",
  "data": {
    "title": "Study group for CAT 2",
    "date": "2026-06-17",
    "start_time": "16:00",
    "end_time": "18:00",
    "location": "Library Block 2",
    "description": "Group study session for DBMS CAT 2"
  },
  "display_text": "Calendar: Study group for CAT 2 on June 17"
}
```

### recurring_reminder
```json
{
  "id": "pqr00112",
  "type": "recurring_reminder",
  "status": "pending",
  "created_at": "2026-06-14T08:30:00",
  "data": {
    "time": "21:00",
    "message": "Review today's lecture notes",
    "frequency": "weekdays",
    "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
  },
  "display_text": "Daily reminder at 9 PM — Review lecture notes"
}
```

## Integration Guide

When integrating with real services:
1. Read `action_log.json` for all pending actions
2. Filter by `status == "pending"`
3. Execute via the appropriate service (alarm API, WhatsApp Evolution API, etc.)
4. Mark as completed via `POST /api/chat/actions/{id}/complete`
