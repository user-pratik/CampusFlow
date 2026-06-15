"""Academic Agent — Handles marks, grades, attendance analysis, and improvement advice.

This agent:
- Retrieves and analyzes academic data (marks, CGPA, attendance)
- Provides performance insights per subject
- Gives actionable improvement advice based on weak areas
- Remembers past academic discussions for follow-up questions
"""

import json
import logging

from app.agents.base import BaseAgent
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)

ACADEMIC_SYSTEM_PROMPT = """\
You are CampusFlow's Academic Advisor agent for {name}, a {branch} student at {college} (VIT Chennai).
Their interests: {interests}. Current focus: {current_focus}.

You have access to their REAL academic data (marks, attendance, CGPA). Use it to give specific, 
data-driven answers. Be encouraging but honest.

You also have access to VIT's official FFCS v4.0 regulations and academic calendar. Use these 
to answer policy questions accurately (attendance rules, grading, credits, deadlines, etc.).

GUIDELINES:
- When asked about a specific subject, find it in the data and give detailed analysis
- Classify performance: 90%+ = Excellent, 80-89% = Good, 70-79% = Average, <70% = Needs Improvement
- For improvement advice: be specific (e.g., "Focus on Unit 3 topics" or "Practice numerical problems")
- If attendance is low for a subject, mention it as a contributing factor
- Reference their CGPA and how specific subjects impact it
- Keep responses concise but informative (under 200 words unless detailed breakdown requested)
- If data is empty/unavailable, say so and suggest syncing VTOP
- For regulation questions: cite the specific rule (e.g., "Per FFCS v4.0, you need 75% attendance...")
- For exam schedule questions: reference the official calendar dates
- For grading questions: explain the 60/40 split (CAM/FAT) and grade points

MATH & CALCULATION ACCURACY (CRITICAL):
- You MUST be strictly accurate with grades, numbers, and math.
- Before outputting any calculation or assessment score, think step-by-step.
- Never hallucinate grades or scores. Only reference numbers explicitly present in the data.
- If the user provides a number (e.g., "I got 98"), treat that user-provided data as absolute fact.
- Show your arithmetic when computing averages, percentages, or projections.
- If you cannot compute something due to missing data, say so — do NOT guess.

CALCULATION RULES:
- Always show your working step by step.
- For attendance: formula is (attended / total) * 100.
- For "how many can I miss": solve (attended / (total + x)) >= 0.75 for x.
- Double-check every number. If data is missing, say exactly what is missing.

RESPONSE FORMAT:
- Format ALL responses using clean markdown.
- Use **bold** for numbers/codes.
- Use bullet lists for multiple items.
- Use a single blank line between sections.
- Never output escaped markdown like \\*\\*text\\*\\*.
- Keep responses under 200 words unless detailed breakdown requested.

VIT CHENNAI ATTENDANCE RULES (IMPORTANT):
- 75% attendance is mandatory for all students
- EXCEPTION: Students with CGPA >= 9.0 are EXEMPT from the 75% attendance rule
- Students with CGPA >= 8.5 with medical grounds may also get relaxation
- Before giving attendance advice, ALWAYS check the student's CGPA first
- If CGPA >= 9.0, inform them they are exempt from attendance requirements
- Never advise a 9+ CGPA student to worry about attendance unless they ask specifically
- If student has CGPA < 9.0 and attendance < 75%, warn them about consequences (exam debarment)

VIT ACADEMIC REGULATIONS & CALENDAR:
{regulations}

CONVERSATION HISTORY:
{history}

ACADEMIC DATA:
{academic_data}

Remember: The student may refer to previous messages. Use conversation history to maintain context.
For example, if they asked about marks earlier and now ask "how can I improve?", refer to the 
subject they were discussing.
"""


class AcademicAgent(BaseAgent):
    """Analyzes academic performance and provides personalized advice."""

    async def execute(self, payload: dict) -> dict:
        """Process an academic query.

        Args:
            payload: {
                "user_message": str,
                "sub_intent": str,
                "context": dict (marks, attendance, academic_profile),
                "history": list[dict],
                "profile": dict
            }

        Returns:
            {
                "response": str,
                "actions": list[dict],
                "panel": str | None,
                "panel_data": dict | None
            }
        """
        user_message = payload["user_message"]
        context = payload["context"]
        history = payload["history"]
        profile = payload["profile"]

        # Build academic data summary
        academic_data = self._format_academic_data(context)

        # Build regulations context
        regulations_text = self._format_regulations(context)

        # Build history text
        history_text = ""
        if history:
            history_text = "\n".join(
                f"{m['role'].upper()}: {m['content'][:300]}" for m in history[-8:]
            )

        system_prompt = ACADEMIC_SYSTEM_PROMPT.format(
            name=profile.get("name", "Student"),
            branch=profile.get("branch", "CS"),
            college=profile.get("college", "VIT"),
            interests=", ".join(profile.get("interests", [])),
            current_focus=profile.get("current_focus", "studies"),
            history=history_text or "No prior conversation.",
            academic_data=academic_data,
            regulations=regulations_text,
        )

        try:
            response = await chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.5,
                max_tokens=768,
            )
        except Exception as e:
            logger.warning("AcademicAgent LLM call failed: %s", e)
            response = "I couldn't analyze your academic data right now. Please try again in a moment."

        # Determine relevant panel and actions
        panel, panel_data, actions = self._determine_ui_response(
            user_message, context
        )

        return {
            "response": response,
            "actions": actions,
            "panel": panel,
            "panel_data": panel_data,
        }

    def _format_academic_data(self, context: dict) -> str:
        """Format academic context into a readable string for the LLM."""
        parts = []

        # Academic profile
        if "academic_profile" in context:
            ap = context["academic_profile"]
            parts.append(
                f"CGPA: {ap['cgpa']} | Credits: {ap['total_credits']} | "
                f"Overall Attendance: {ap.get('overall_attendance', 'N/A')}% | "
                f"Semester: {ap.get('semester_name', 'Current')}"
            )

        # Marks grouped by course
        if "marks" in context and context["marks"]:
            parts.append("\nMARKS BY COURSE:")
            course_marks: dict[str, list] = {}
            for m in context["marks"]:
                key = f"{m['course_code']} — {m['course_title']}"
                if key not in course_marks:
                    course_marks[key] = []
                score_str = f"{m['score']}/{m['max_mark']}" if m['score'] is not None else "N/A"
                course_marks[key].append(
                    f"  {m['mark_title']}: {score_str} (Weightage: {m['weightage_pct']}%, "
                    f"Weighted Mark: {m['weightage_mark']})"
                )

            for course, entries in course_marks.items():
                parts.append(f"\n{course}")
                parts.extend(entries)
                # Calculate total weighted marks for this course
                total_weighted = sum(
                    m["weightage_mark"] or 0
                    for m in context["marks"]
                    if f"{m['course_code']} — {m['course_title']}" == course
                )
                parts.append(f"  → Total Weighted: {total_weighted:.1f}")

        # Attendance
        if "attendance" in context and context["attendance"]:
            parts.append("\nATTENDANCE:")
            for a in context["attendance"]:
                flag = "⚠️" if a["percentage"] < 75 else "✓"
                parts.append(
                    f"  {flag} {a['course_code']} ({a['course_title']}): "
                    f"{a['percentage']}% ({a['attended']}/{a['total']})"
                )

        if not parts:
            return "No academic data available. Student should sync VTOP first."

        return "\n".join(parts)

    def _format_regulations(self, context: dict) -> str:
        """Format VIT academic regulations for the LLM context."""
        regs = context.get("regulations", {})
        if not regs:
            return "No regulations data loaded."

        parts = []

        # Calendar
        cal = regs.get("calendar", {})
        if cal:
            parts.append("ACADEMIC CALENDAR (Winter 2025-2026):")
            parts.append(f"  Semester: {cal.get('semester', 'N/A')}")
            parts.append(f"  Commencement: {cal.get('commencement', 'N/A')}")
            parts.append(f"  CAT-1: {cal.get('cat1_exams', {}).get('start', '')} to {cal.get('cat1_exams', {}).get('end', '')}")
            parts.append(f"  Vibrance (No Class): {cal.get('vibrance_no_class', {}).get('start', '')} to {cal.get('vibrance_no_class', {}).get('end', '')}")
            parts.append(f"  Course Withdrawal Window: {cal.get('course_withdrawal_window', {}).get('start', '')} to {cal.get('course_withdrawal_window', {}).get('end', '')}")
            parts.append(f"  CAT-2: {cal.get('cat2_exams', {}).get('start', '')} to {cal.get('cat2_exams', {}).get('end', '')}")
            parts.append(f"  Last Day Labs: {cal.get('last_instructional_day_labs', 'N/A')}")
            parts.append(f"  Last Day Theory: {cal.get('last_instructional_day_theory', 'N/A')}")
            parts.append(f"  FAT Labs: {cal.get('fat_exams_labs', {}).get('start', '')} to {cal.get('fat_exams_labs', {}).get('end', '')}")
            parts.append(f"  FAT Theory Begins: {cal.get('fat_exams_theory_begins', 'N/A')}")
            parts.append(f"  Summer Sem Start: {cal.get('summer_semester_start', 'N/A')}")
            parts.append(f"  Fall 2026-27 Start: {cal.get('fall_2026_27_start', 'N/A')}")

        # Registration
        reg = regs.get("registration", {})
        if reg:
            parts.append("\nREGISTRATION RULES:")
            parts.append(f"  Credits: Min {reg.get('min_credits', 16)}, Max {reg.get('max_credits', 27)}, Avg {reg.get('average_credits', 23)}")
            parts.append(f"  Add/Drop: {reg.get('add_drop_window', 'First 3 days')}")
            parts.append(f"  Withdrawal: {reg.get('withdrawal', 'N/A')}")
            parts.append(f"  Low CGPA: {reg.get('low_cgpa_restriction', 'N/A')}")
            parts.append(f"  Backlogs: {reg.get('backlogs', 'N/A')}")

        # Attendance rules
        att = regs.get("attendance", {})
        if att:
            parts.append("\nATTENDANCE RULES:")
            parts.append(f"  Minimum: {att.get('minimum_required', 75)}%")
            parts.append(f"  Rule: {att.get('minimum_required_note', 'N/A')}")
            parts.append(f"  Consequence: {att.get('consequence', 'Debarred from exams')}")
            parts.append(f"  9-Pointer Exemption: {att.get('nine_pointer_exemption', 'N/A')}")
            parts.append(f"  Condonation: {att.get('condonation', 'N/A')}")
            parts.append(f"  Medical: {att.get('medical', 'N/A')}")

        # Assessment
        assess = regs.get("assessment", {})
        if assess:
            parts.append("\nASSESSMENT & GRADING:")
            parts.append(f"  Split: {assess.get('split', '60% CAM + 40% FAT')}")
            cam = assess.get("cam_breakdown", {})
            parts.append(f"  CAT-1: {cam.get('cat1', {}).get('weightage_pct', 15)}%")
            parts.append(f"  CAT-2: {cam.get('cat2', {}).get('weightage_pct', 15)}% (Open Book)")
            parts.append(f"  Digital Assignments: {cam.get('digital_assignments', {}).get('weightage_pct', 30)}%")
            passing = assess.get("passing_criteria", {})
            parts.append(f"  Passing: Theory FAT >= {passing.get('theory_fat_minimum', 40)}%, Lab >= {passing.get('lab_project_minimum', 50)}%, Overall >= {passing.get('overall_minimum', 50)}%")
            parts.append("  Grade Points: S(10), A(9), B(8), C(7), D(6), E(5), F/N(0)")
            grading = assess.get("grading_system", {})
            parts.append(f"  Relative grading: {grading.get('relative', 'Theory >10 students')}")
            parts.append(f"  Absolute grading: {grading.get('absolute', 'Labs, projects, <=10 students')}")

        # Projects
        proj = regs.get("projects_internships", {})
        if proj:
            parts.append("\nPROJECTS & INTERNSHIPS:")
            parts.append(f"  Internship: {proj.get('industrial_internship', 'N/A')}")
            fp = proj.get("final_project", {})
            parts.append(f"  Final Project: {fp.get('eligibility', 'N/A')}")
            parts.append(f"  Hackathon Bonus: {proj.get('hackathon_bonus', 'N/A')}")

        # Credentials
        cred = regs.get("credentials", {})
        if cred:
            parts.append("\nCREDENTIALS:")
            mh = cred.get("minors_honours", {})
            parts.append(f"  Minors/Honours: {mh.get('additional_credits_required', 18)} extra credits, CGPA >= {mh.get('minimum_cgpa_in_those_courses', 7.5)} in those courses")
            parts.append(f"  Course Substitution: {cred.get('course_substitution', 'N/A')}")
            parts.append(f"  Grade Improvement: {cred.get('grade_improvement', 'N/A')}")

        return "\n".join(parts) if parts else "No regulations data."

    def _determine_ui_response(
        self, message: str, context: dict
    ) -> tuple:
        """Determine which panel to open and what actions to suggest."""
        q = message.lower()
        actions = []
        panel = None
        panel_data = None

        if any(w in q for w in ["mark", "grade", "score", "cgpa"]):
            panel = "marks"
            actions = [
                {"label": "Show detailed breakdown", "type": "navigate", "payload": "marks"},
                {"label": "How to improve CGPA?", "type": "reply"},
                {"label": "Create study schedule", "type": "reply"},
            ]
        elif any(w in q for w in ["attendance", "absent", "present", "bunk"]):
            panel = "attendance"
            actions = [
                {"label": "Show attendance", "type": "navigate", "payload": "attendance"},
                {"label": "Set attendance reminder", "type": "reply"},
            ]
        else:
            actions = [
                {"label": "Check my marks", "type": "navigate", "payload": "marks"},
                {"label": "Check attendance", "type": "navigate", "payload": "attendance"},
                {"label": "Create improvement plan", "type": "reply"},
            ]

        return panel, panel_data, actions
