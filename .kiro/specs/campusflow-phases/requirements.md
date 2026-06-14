# Requirements Document

## Introduction

CampusFlow is a multi-agent campus assistant for VIT students, built on a Python FastAPI backend and React/TypeScript frontend. This document specifies requirements for a phased implementation plan that evolves the system from bug-fix stabilization (Phase 0) through core data agents, notification infrastructure, placement preparation, a unified dashboard, and final polish (Phase 5). Each phase builds on prior phases, enabling incremental delivery of value while maintaining system stability.

## Glossary

- **CampusFlow**: The complete campus assistant system comprising a FastAPI backend, React frontend, and multi-agent orchestration layer
- **VTOP_Connector**: The backend module that scrapes academic data (attendance, marks, timetable, CGPA) from VIT's VTOP student portal
- **Email_Classifier**: The rule-based module that categorizes Gmail messages into PLACEMENT, EXAM, FEE, EVENT, ANNOUNCEMENT, or GENERAL with urgency-aware priority
- **Connector_Agent**: The specialist agent handling queries about WhatsApp messages, emails, calendar events, and eligibility pre-filtering
- **Orchestrator**: The central routing agent that classifies user intent and delegates to specialist agents
- **Eligibility_Filter**: Logic within Connector_Agent that cross-checks placement posting criteria (degree, branch, batch, CGPA) against the student's academic profile
- **Timetable_Agent**: A new agent that parses real VTOP timetable data and provides free-slot detection
- **Attendance_Alerter**: A new module that calculates attendance risk and generates proactive warnings
- **GPA_Projector**: A new computation module that projects semester GPA and CGPA based on current marks
- **Notification_System**: Unified notification infrastructure including a data model, API, frontend bell/dropdown, and background scheduler
- **Deadline_Aggregator**: An agent that pulls deadlines from Gmail, WhatsApp, and VTOP into a unified timeline
- **Placement_Prep_Agent**: An agent that monitors placement emails, extracts drive details via LLM, checks eligibility, and provides countdown nudges
- **Dashboard**: A unified home screen aggregating key data from all agents into a single view
- **Study_Companion**: An agent that assists with exam preparation and study planning
- **APScheduler**: The Python background task scheduler (already a dependency) used for proactive alerts and periodic data sync
- **TimetableSlot**: A data model representing a single class slot with day, time, course, room, and faculty
- **PlacementDrive**: A data model representing a placement opportunity with company, date, rounds, eligibility, and status
- **PrepChecklist**: A data model representing preparation steps for a specific placement drive
- **User_Profile**: The student's stored academic identity (degree: BTech, branch: CSE/AIML, batch: 2027, CGPA: 9.11)

## Requirements

### Requirement 1: EmailPanel Backend Connectivity Fix

**User Story:** As a student, I want the Email panel to reliably load my emails, so that I can view classified messages without encountering "Failed to fetch" errors.

#### Acceptance Criteria

1. WHEN the frontend requests emails from the backend, THE EmailPanel SHALL receive a valid JSON response containing an array of email objects within 5 seconds, measured from the moment the request is sent until the response is fully received
2. IF the backend is unreachable or returns a non-2xx status, THEN THE EmailPanel SHALL display an inline error message within the panel area indicating the nature of the connection issue (e.g., network unreachable, server error, or timeout) and SHALL retain any previously loaded email data on screen
3. THE Backend SHALL include CORS headers that permit cross-origin requests from the frontend origin on all Gmail-related API endpoints (prefixed with /api/gmail), including support for preflight OPTIONS requests
4. IF the Gmail OAuth token has expired, THEN THE Backend SHALL attempt a token refresh using the stored refresh token before returning an authentication error response to the frontend, and SHALL return the authentication error only if the refresh attempt fails
5. WHEN an email fetch request fails due to a transient error (defined as: network timeout, HTTP 429, or HTTP 5xx response from the Gmail API), THE Backend SHALL retry the request exactly once after a delay of no more than 2 seconds before returning an error response to the frontend
6. IF no emails have been synced yet or the email store is empty, THEN THE EmailPanel SHALL display an empty-state message indicating that no emails are available and prompting the user to trigger a sync

---

### Requirement 2: Email Classifier Mis-Prioritization Fix

**User Story:** As a student, I want emails from Unstop, Kaggle, Read AI, and security alerts to be classified as low priority, so that my inbox view surfaces genuinely urgent messages first.

#### Acceptance Criteria

1. WHEN an email is received from a sender whose address contains (case-insensitive substring match) any entry in the noise sender list (unstop, dare2compete, kaggle, read.ai, readai, security-noreply, noreply@google, newsletter, digest, mailer-daemon, coursera, udemy, linkedin, internshala), THE Email_Classifier SHALL assign a priority of "low" regardless of email body content or subject keywords
2. WHEN an email subject matches a noise subject pattern (security alert, new competition, weekly digest, verify your email, confirm your email, welcome to, reset password, monthly digest, newsletter), THE Email_Classifier SHALL assign a priority of "low" regardless of email body content
3. IF an email does not match any noise sender or noise subject pattern, THEN THE Email_Classifier SHALL assign "high" priority ONLY when the email contains at least one actionable signal (register before, apply by, submit by, fill the form, report to, appear for, slot booking, or scheduled on with a date) AND at least one urgency indicator (an explicit deadline date, or keywords: last date, deadline, mandatory, compulsory, immediately, within 24 hours, within 48 hours, final reminder, urgent, action required)
4. WHEN the Email_Classifier processes a batch of emails containing one or more noise sender emails, THE Email_Classifier SHALL assign "low" priority to every email whose sender matches the noise sender list, producing zero "high" or "medium" classifications for those emails
5. IF an email is classified as "high" priority, THEN THE Email_Classifier SHALL have verified that the email body or subject contains at least one actionable signal (registration, submission, attendance requirement, or scheduled assessment) combined with a date or time-bound reference within 7 days
6. IF an email does not contain both an actionable signal and an urgency indicator, THEN THE Email_Classifier SHALL assign a priority of "medium" when the email contains an actionable signal alone, or "low" when no actionable signal is present

---

### Requirement 3: Eligibility Pre-Filter in Connector Agent

**User Story:** As a student, I want placement emails to be automatically checked against my academic profile, so that I immediately know which opportunities I qualify for.

#### Acceptance Criteria

1. WHEN a user query contains any of the placement-related keywords (job, placement, eligible, apply, intern, cdc, hiring, opportunity), THE Eligibility_Filter SHALL extract degree, branch, batch year, and CGPA requirements from the body of up to 10 placement-category emails
2. IF all extracted criteria (degree, branch, batch year, CGPA) match the User_Profile, THEN THE Eligibility_Filter SHALL tag the email as "Eligible"
3. IF at least one extracted criterion conflicts with the User_Profile (wrong degree level, wrong batch year, or CGPA below the stated cutoff), THEN THE Eligibility_Filter SHALL tag the email as "Likely Not Eligible" with a reason identifying each conflicting criterion and the mismatch (e.g., required value vs. user value)
4. IF none of the four eligibility criteria (degree, branch, batch year, CGPA) can be extracted from the email body, THEN THE Eligibility_Filter SHALL tag the email as "Unclear — Verify" and advise the student to confirm manually
5. THE Eligibility_Filter SHALL use the real-time CGPA value from the AcademicProfile database record rather than a hardcoded value
6. IF the AcademicProfile database record is unreachable or returns no CGPA value, THEN THE Eligibility_Filter SHALL skip the CGPA comparison, tag affected emails as "Unclear — Verify", and indicate that CGPA could not be confirmed
7. THE Eligibility_Filter SHALL evaluate all four criteria (degree AND branch AND batch year AND CGPA) in a single pass per email, producing exactly one eligibility tag per email

---

### Requirement 4: VTOP CGPA Extraction Verification

**User Story:** As a student, I want my CGPA to be correctly extracted from VTOP, so that eligibility checks and academic projections use accurate data.

#### Acceptance Criteria

1. WHEN the VTOP_Connector scrapes academic profile data, THE VTOP_Connector SHALL extract a CGPA value greater than 0.0 for enrolled students
2. IF the VTOP_Connector extracts a CGPA value of 0.0, THEN THE VTOP_Connector SHALL log a warning and retry the extraction using an alternate parsing strategy (searching for CGPA in alternate table structures or text patterns on the page), with a maximum of 2 retry attempts
3. WHEN CGPA is successfully extracted, THE VTOP_Connector SHALL persist the value to the AcademicProfile table with an updated timestamp
4. THE VTOP_Connector SHALL validate that the extracted CGPA falls within the range 0.01 to 10.0 before persisting
5. IF the extracted CGPA fails validation (outside 0.01 to 10.0 range) after all retry attempts, THEN THE VTOP_Connector SHALL log an error, retain the previously stored CGPA value unchanged, and report extraction failure to the caller

---

### Requirement 5: Smart Timetable Agent

**User Story:** As a student, I want my real VTOP timetable parsed and displayed, so that I can see my actual class schedule and find free slots for study or meetings.

#### Acceptance Criteria

1. WHEN the VTOP_Connector fetches timetable data from the StudentTimeTableChn page, THE Timetable_Agent SHALL parse the HTML response into a list of TimetableSlot objects containing one entry per scheduled class across all weekdays (Monday through Saturday)
2. THE TimetableSlot model SHALL store day of week (Monday through Saturday), start time (HH:MM 24-hour format), end time (HH:MM 24-hour format), course code (up to 20 characters), course title (up to 100 characters), slot code (up to 10 characters), room number (up to 20 characters), and faculty name (up to 100 characters)
3. WHEN a user asks about free slots, THE Timetable_Agent SHALL compute all time gaps between scheduled classes on the specified day, considering only gaps within the range of 08:00 to 21:00 that are at least 30 minutes long, and return each gap with its start time, end time, and duration in minutes
4. WHEN a user asks about today's schedule, THE Timetable_Agent SHALL return only slots for the current day of the week ordered by start time; IF the current day has no scheduled classes (e.g., Sunday), THEN THE Timetable_Agent SHALL return an empty list with a message indicating no classes are scheduled for that day
5. THE TimetablePanel frontend component SHALL replace the existing fabricated timetable data with real parsed VTOP timetable data fetched from the backend API
6. IF the VTOP session is expired or the timetable fetch returns no data, THEN THE Timetable_Agent SHALL display the last successfully cached timetable data and show a staleness indicator containing the date and time of the last successful sync
7. IF the VTOP_Connector receives an HTML response that contains no parseable timetable table rows, THEN THE Timetable_Agent SHALL return an empty list without overwriting previously cached timetable data

---

### Requirement 6: Attendance Risk Alerter

**User Story:** As a student, I want proactive alerts when my attendance in any course drops near the 75% threshold, so that I can plan which classes to prioritize.

#### Acceptance Criteria

1. THE Attendance_Alerter SHALL calculate a skippable class count for each course using the formula: floor(attended / 0.75) - total, where attended and total are sourced from the Attendance database table
2. IF a course has 3 or fewer skippable classes remaining, THEN THE Attendance_Alerter SHALL flag the course as "high risk"
3. IF a course has between 4 and 6 skippable classes remaining, THEN THE Attendance_Alerter SHALL flag the course as "medium risk"
4. IF a course has more than 6 skippable classes remaining, THEN THE Attendance_Alerter SHALL flag the course as "safe"
5. WHEN the AttendancePanel frontend component loads, THE AttendancePanel SHALL display a risk badge labeled "high risk", "medium risk", or "safe" next to each course attendance entry
6. WHEN the Timetable_Agent provides today's class context, THE Attendance_Alerter SHALL annotate each of today's classes with its current risk level so the student can identify which classes are high-risk to skip
7. IF attendance data for a course is unavailable or has not been updated within the last 7 days, THEN THE Attendance_Alerter SHALL display the course risk as "unknown" instead of calculating a risk score
8. THE Attendance_Alerter SHALL recalculate risk scores each time attendance data is synced from the Attendance database table

---

### Requirement 7: GPA/CGPA Projection Agent

**User Story:** As a student, I want to see projected GPA and CGPA based on my current marks, so that I can estimate my semester performance and set realistic targets.

#### Acceptance Criteria

1. WHEN a user requests a GPA projection, THE GPA_Projector SHALL compute the projected semester GPA as the credit-weighted average of grade points across all courses that have at least one non-null score in CourseMark, using VIT's 10-point grading scale
2. THE GPA_Projector SHALL map total weighted marks (sum of weightage_mark for all assessments in a course, scaled to 100) to grade points using VIT grading thresholds: S=10 (≥90%), A=9 (≥80%), B=8 (≥70%), C=7 (≥60%), D=6 (≥50%), E=5 (≥40%), F=0 (<40%)
3. THE GPA_Projector SHALL compute projected CGPA using the formula: ((historical_CGPA × historical_credits) + (projected_semester_GPA × current_semester_credits)) / (historical_credits + current_semester_credits), using values from AcademicProfile
4. WHEN marks for an assessment are missing (score is null), THE GPA_Projector SHALL provide a best-case projection assuming the maximum possible score for missing assessments and a worst-case projection assuming a score of zero for missing assessments
5. IF all assessments for every course have null scores (no marks data available), THEN THE GPA_Projector SHALL return an error indication stating that insufficient data exists for projection instead of computing a GPA
6. THE MarksPanel frontend component SHALL display a projection widget showing the estimated semester GPA, projected CGPA, and the best-case/worst-case range alongside current marks
7. WHEN a user submits a what-if query specifying target scores (as percentages between 0 and 100) for one or more remaining assessments, THE GPA_Projector SHALL recompute the projected GPA and CGPA using those target scores in place of null values

---

### Requirement 8: Unified Notification Model and API

**User Story:** As a student, I want all alerts (deadlines, attendance warnings, placement reminders) delivered through a single notification system, so that I have one place to check for important updates.

#### Acceptance Criteria

1. THE Notification_System SHALL define a Notification database model with fields: id, title (max 200 characters), body (max 2000 characters), category (one of: deadline, attendance, placement, general), priority (one of: high, medium, low), source_agent, is_read (default false), created_at, action_url (max 500 characters, nullable)
2. THE Backend SHALL expose a GET /api/notifications endpoint that returns notifications sorted by created_at descending, with pagination via limit (default 20, maximum 100) and offset (default 0) query parameters, and an optional category query parameter to filter results by category
3. IF a PATCH request is made to /api/notifications/{id}/read with a notification id that does not exist, THEN THE Backend SHALL return an error response indicating the notification was not found
4. WHEN a PATCH request is made to /api/notifications/{id}/read with a valid notification id, THE Backend SHALL set is_read to true and return the updated notification record
5. THE Frontend SHALL render a notification bell icon in the top navigation bar showing the count of unread notifications, displaying "99+" when the unread count exceeds 99
6. WHEN the notification bell is clicked, THE Frontend SHALL display a dropdown listing the 10 most recent notifications with title, time relative to now, and category badge
7. WHEN a notification in the dropdown is clicked, THE Frontend SHALL mark the notification as read and navigate to the action_url if present

---

### Requirement 9: Background Scheduler Integration

**User Story:** As a student, I want the system to proactively run checks and send alerts on a schedule, so that I receive timely reminders without manually querying the assistant.

#### Acceptance Criteria

1. THE Backend SHALL initialize APScheduler during FastAPI application startup and shut it down on application shutdown, allowing currently executing jobs up to 30 seconds to complete before forcing termination
2. THE Background_Scheduler SHALL support registering periodic jobs with a minimum interval of 60 seconds and one-time jobs scheduled for a specific date and time, with a maximum of 50 concurrent registered jobs
3. WHEN a scheduled job fails with an exception, THE Background_Scheduler SHALL log the error and retry the job once after a 60-second delay
4. IF a scheduled job retry also fails with an exception, THEN THE Background_Scheduler SHALL log the final failure and skip the job execution until the next scheduled trigger
5. THE Background_Scheduler SHALL support adding new jobs at runtime via internal Python function calls without requiring application restart
6. THE Background_Scheduler SHALL run attendance risk checks every 6 hours and generate a notification via the Notification_System for each course that transitions from non-high-risk to high-risk status since the previous check
7. IF attendance data is unavailable or stale (last synced more than 24 hours ago) when a scheduled attendance risk check executes, THEN THE Background_Scheduler SHALL skip the check, log a warning, and retry at the next scheduled interval without generating notifications

---

### Requirement 10: Smart Deadline Aggregator Agent

**User Story:** As a student, I want all my deadlines from Gmail, WhatsApp, and VTOP aggregated into a single timeline, so that I never miss a submission or registration date.

#### Acceptance Criteria

1. THE Deadline_Aggregator SHALL pull deadline information from EmailNotification records (parsed dates from email bodies), WhatsApp Notice/Task records, and VTOP assignment dates, and SHALL skip any source record from which a valid date cannot be extracted
2. THE Deadline_Aggregator SHALL deduplicate deadlines by matching on title similarity (greater than 80% fuzzy match) and date proximity (within 24 hours), and SHALL retain the entry with the longest combined title and body text as the primary record
3. THE Backend SHALL expose a GET /api/deadlines endpoint returning a paginated list (limit/offset, default limit 20, maximum limit 50) of deadlines with due dates within the next 30 days, sorted by due date ascending, where each entry includes: title, due date, source (Gmail, WhatsApp, or VTOP), source record ID, and status (pending or completed)
4. THE DeadlineTimelinePanel frontend component SHALL display deadlines as a chronological timeline with source indicators (Gmail, WhatsApp, VTOP) and SHALL visually distinguish deadlines due within 48 hours from later deadlines
5. WHEN a deadline is 24 hours away and no notification has been previously created for that deadline, THE Deadline_Aggregator SHALL create a proactive notification via the Notification_System with category "deadline" and priority "high"
6. WHEN a deadline has been matched from at least two distinct sources, THE Deadline_Aggregator SHALL sync that deadline to the user's Google Calendar using the existing calendar_client integration
7. IF the Google Calendar sync fails due to authentication error or network failure, THEN THE Deadline_Aggregator SHALL log the failure, mark the deadline as "sync_failed", and retry the sync on the next scheduled aggregation run
8. WHEN a duplicate deadline is detected, THE Deadline_Aggregator SHALL merge the entries and retain the source record that has the longest combined title and description text as the primary detail source

---

### Requirement 11: Placement Prep Agent

**User Story:** As a student, I want the system to monitor placement emails, extract drive details, check my eligibility, and give me countdown nudges, so that I am well-prepared for every eligible opportunity.

#### Acceptance Criteria

1. WHEN a new email is classified as PLACEMENT by the Email_Classifier, THE Placement_Prep_Agent SHALL extract company name, drive date, rounds (aptitude/coding/interview), role, and eligibility criteria using LLM-based extraction and store results within 30 seconds of classification
2. IF the LLM-based extraction cannot determine the drive date or company name from the email body, THEN THE Placement_Prep_Agent SHALL store the record with status "incomplete" and flag it for manual review by the student via the Notification_System
3. THE Placement_Prep_Agent SHALL store extracted details in a PlacementDrive database model with fields: id, company_name, drive_date, role, rounds_json, eligibility_json, email_id, status (where status is one of: "eligible", "ineligible", "incomplete", "past")
4. WHEN a PlacementDrive is created with status other than "incomplete", THE Placement_Prep_Agent SHALL cross-check eligibility by evaluating degree, branch, batch year, and CGPA criteria against the student's AcademicProfile using the Eligibility_Filter logic
5. WHEN the student is eligible for a drive, THE Placement_Prep_Agent SHALL generate a PrepChecklist containing at least 3 preparation steps covering: resume verification, role-relevant coding or aptitude practice topics, and company research notes
6. WHEN a placement drive is 7 days away, THE Placement_Prep_Agent SHALL create a countdown notification via the Notification_System at 09:00 local time and continue with one notification per day until the drive date
7. WHEN the PlacementPrepPanel is loaded, THE PlacementPrepPanel frontend component SHALL display upcoming drives (status not "past") with eligibility status, days remaining as an integer countdown, and preparation checklist progress as a ratio of completed items to total items
8. IF the student is not eligible for a drive, THEN THE Placement_Prep_Agent SHALL store the drive record with status "ineligible" and persist the specific disqualifying criterion (degree mismatch, branch mismatch, batch year mismatch, or CGPA below cutoff) in the eligibility_json field
9. WHEN a PlacementDrive's drive_date has passed, THE Placement_Prep_Agent SHALL update the drive status to "past" and cease sending countdown notifications for that drive

---

### Requirement 12: Unified Dashboard Home Screen

**User Story:** As a student, I want a single dashboard view that shows my most important information at a glance, so that I can quickly assess my academic status without navigating multiple panels.

#### Acceptance Criteria

1. THE DashboardPanel frontend component SHALL display summary widgets for: today's schedule (from Timetable_Agent), attendance risk alerts (from Attendance_Alerter), upcoming deadlines due within the next 7 days (from Deadline_Aggregator), the 5 most recent unread notifications, and GPA projection
2. WHEN the dashboard loads, THE Frontend SHALL fetch data from all required endpoints in parallel, display a loading skeleton for each widget, and render each widget independently as its data becomes available
3. THE Dashboard SHALL display high-risk attendance courses and deadlines due within 48 hours in a priority section at the top of the view, above all other widgets
4. THE Dashboard SHALL include quick-action buttons for common tasks: check emails, view marks, ask the assistant
5. IF any single data source does not respond within 10 seconds, THEN THE Dashboard SHALL render remaining widgets that have loaded successfully and display a retry button for the timed-out section
6. WHILE any widget is awaiting data, THE Dashboard SHALL display a placeholder skeleton for that widget indicating a loading state

---

### Requirement 13: Exam Prep / Study Companion Agent

**User Story:** As a student, I want AI-assisted study planning and exam preparation guidance, so that I can optimize my revision strategy based on my actual marks and syllabus.

#### Acceptance Criteria

1. WHEN a user requests exam prep help, THE Study_Companion SHALL analyze the user's CourseMark data to identify weak areas (assessments scored below 60% of max) and produce a study plan containing: a ranked list of courses ordered by risk priority, weak topics per course, recommended daily study hours per course, and target dates for completion
2. THE Study_Companion SHALL generate a prioritized study plan considering exams occurring within the next 30 days (from calendar/deadline data), weak areas, and credit weightage of each course, where priority is calculated as: (1 − current_weighted_percentage/100) × course_credits × (1/days_until_exam)
3. THE Study_Companion SHALL provide topic-level recommendations by using LLM inference to map mark_title fields (assessment names such as "CAT 1", "Digital Assignment 2") to likely syllabus topics for each course
4. WHEN multiple exams are within the same 7-day window, THE Study_Companion SHALL suggest a time-allocation strategy that distributes available study hours across courses proportionally to each course's risk score (low current score + high credit weight = high priority)
5. THE Study_Companion SHALL integrate with the Timetable_Agent to suggest study slots of at least 30 minutes duration that fit within the student's free time over the next 7 days
6. IF the user has fewer than 2 courses with CourseMark data available, THEN THE Study_Companion SHALL inform the user that insufficient academic data exists to generate a study plan and suggest syncing VTOP data first
7. IF no upcoming exams are found within the next 30 days, THEN THE Study_Companion SHALL notify the user that no imminent exams were detected and offer to generate a general revision plan based on weak areas alone

---

### Requirement 14: Onboarding Flow

**User Story:** As a new user, I want a guided setup process that connects my VTOP account, Gmail, and preferences, so that CampusFlow can start working with my real data immediately.

#### Acceptance Criteria

1. WHEN a user launches CampusFlow for the first time, THE Frontend SHALL display an onboarding wizard with sequential steps: welcome, VTOP login, Gmail OAuth, notification preferences, completion
2. THE Onboarding flow SHALL validate each connection step by confirming a successful response from the respective service (VTOP session established, Gmail OAuth token obtained) before enabling the next step, with a validation timeout of 30 seconds per step
3. WHEN VTOP login succeeds, THE Backend SHALL trigger a data sync (attendance, marks, timetable, academic profile) within 5 seconds and THE Frontend SHALL display a progress indicator showing sync status until completion or timeout after 60 seconds
4. WHEN Gmail OAuth succeeds, THE Backend SHALL fetch and classify the 50 most recent emails and THE Frontend SHALL display a progress indicator until classification completes or times out after 30 seconds
5. THE Onboarding flow SHALL allow users to skip optional steps (WhatsApp integration) and complete setup with only VTOP and Gmail connected
6. IF VTOP login fails during onboarding (invalid credentials, VTOP unreachable, or timeout), THEN THE Frontend SHALL display an error message indicating the failure reason and allow the user to retry without losing progress on previously completed steps
7. IF Gmail OAuth fails during onboarding (user denies permission, token exchange fails, or timeout), THEN THE Frontend SHALL display an error message indicating the failure reason and allow the user to retry without losing progress on previously completed steps
8. IF the data sync triggered after VTOP login exceeds 60 seconds, THEN THE Frontend SHALL allow the user to proceed to the next onboarding step and complete the sync in the background

---

### Requirement 15: Offline and Low-Connectivity Mode

**User Story:** As a student on campus with unreliable Wi-Fi, I want the app to remain functional with cached data when offline, so that I can still check my schedule and marks.

#### Acceptance Criteria

1. THE Frontend SHALL cache the most recent timetable (current semester), attendance (all enrolled courses), marks (all enrolled courses), and deadline data (next 30 days) in browser local storage, consuming no more than 5 MB total
2. WHEN the device is offline or the backend is unreachable, THE Frontend SHALL display cached data with a visible "Offline" banner and a timestamp showing the date and time of the last successful sync
3. WHEN connectivity is restored, THE Frontend SHALL automatically re-sync data with the backend within 30 seconds of detecting connectivity and update the display with fresh data
4. WHILE the device is offline, THE Frontend SHALL disable actions that require network connectivity (send message, refresh emails) and render those controls in a visually distinct disabled state with a tooltip indicating network is required
5. IF cached data is older than 24 hours, THEN THE Frontend SHALL display a warning indicating the data may be stale, including the elapsed time since last sync
6. IF the device goes offline and no cached data is available for a data category, THEN THE Frontend SHALL display a message indicating that no offline data is available for that category and that a network connection is required for first load

---

### Requirement 16: Privacy and Data Control Panel

**User Story:** As a student, I want control over what data CampusFlow stores and processes, so that I can manage my privacy preferences and delete data if needed.

#### Acceptance Criteria

1. THE Backend SHALL expose a GET /api/privacy/data-summary endpoint returning a summary of all stored data categories (emails, attendance, marks, notifications, notices, tasks, events) with per-category record counts and the timestamp of the most recent record in each category
2. THE Backend SHALL expose a DELETE /api/privacy/data/{category} endpoint that permanently removes all records of a specified data category, where valid categories are: emails, attendance, marks, notifications, notices, tasks, events
3. IF a DELETE /api/privacy/data/{category} request specifies a category not in the valid categories list, THEN THE Backend SHALL return an error response indicating the invalid category and listing the valid options
4. THE Frontend SHALL provide a Privacy Settings panel showing connected services with their connection status, data categories stored with record counts, and per-category delete buttons that require a confirmation step before executing deletion
5. WHEN a user confirms deletion of a data category, THE Backend SHALL permanently remove all records of that category, return a response containing the count of records removed, and persist an audit log entry recording the user action, category deleted, record count, and timestamp
6. WHEN a user disconnects an individual service (VTOP, Gmail, or WhatsApp), THE Backend SHALL revoke or delete stored credentials and tokens for that service and permanently purge all data records sourced from that service, then return a confirmation indicating the service was disconnected and the count of records removed
7. THE Frontend SHALL require a confirmation step before disconnecting a service, informing the user that all associated data will be permanently deleted

---

### Requirement 17: WhatsApp Integration (Conditional)

**User Story:** As a student, I want WhatsApp messages from class groups ingested into CampusFlow, so that notices and deadlines shared via WhatsApp are captured alongside email and VTOP data.

#### Acceptance Criteria

1. WHERE the WhatsApp Docker/Evolution API environment is available, THE Backend SHALL connect to the Evolution API instance and register a webhook endpoint for incoming group messages, confirming connection by receiving a successful connection state response within 15 seconds
2. WHEN a WhatsApp message is received with non-empty text content, THE Backend SHALL parse and store it as a Notice record with source_group (group identifier from the message JID), raw_text (full message body, max 4096 characters), and parsed metadata including parsed_title and category
3. WHEN a WhatsApp message is received with a text_hash matching an already-stored Notice, THE Backend SHALL discard the duplicate message and return a duplicate-dropped status without creating a new record
4. WHILE WhatsApp integration is active, THE Deadline_Aggregator SHALL include WhatsApp-sourced deadlines (Tasks linked to WhatsApp-originated Notices) in the unified timeline
5. IF the WhatsApp Docker environment is unavailable or the Evolution API does not respond within 10 seconds during startup, THEN THE Backend SHALL log a warning, skip WhatsApp webhook registration, and continue startup of all other system functionality without error
6. IF a WhatsApp message is received with empty text content (no conversation, extended text, or image caption), THEN THE Backend SHALL ignore the message and return an ignored status without storing a record
7. THE Frontend WhatsAppPanel SHALL display ingested messages grouped by source_group, showing for each message the group name, sender, message text, message type, and a relative timestamp (e.g., "2h ago", "3d ago"), ordered with most recent messages first

---

### Requirement 18: Descoped Features Boundary

**User Story:** As a project stakeholder, I want clarity on which features are explicitly out of scope for this implementation plan, so that development stays focused on committed deliverables.

#### Acceptance Criteria

1. THE CampusFlow implementation plan SHALL NOT include an Expense/Mess-Wallet Tracker feature in any phase
2. THE CampusFlow implementation plan SHALL NOT include an Analytics/Insights admin dashboard in any phase
3. THE CampusFlow implementation plan SHALL treat the Campus Q&A Knowledge Base Agent as stretch-only scope that requires explicit written approval from the project stakeholder before development begins
4. THE CampusFlow implementation plan SHALL treat Hostel/Transport Notice Agent and Peer/Club Event Discovery as stretch-only scope within Phase 4, contingent on confirmed data source availability
