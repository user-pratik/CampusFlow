"""Attendance Risk Agent — calculates skip/recovery metrics per course.

Pure computation, no LLM calls, no scheduling. Operates on Attendance records
already stored from VTOP sync.

NOTE ON THRESHOLD:
The 75% threshold used in this calculator is configured to match VIT's
actual minimum attendance requirement for FAT exam eligibility (per FFCS v4.0).
There IS a 9-pointer exemption: students with CGPA >= 9.0 and no backlogs are
exempted from this rule. This calculator does NOT automatically apply the exemption —
it always calculates against 75% as a universal reference point.
For actual regulation details (exemptions, medical leave rules, consequences),
refer to data/fabricated/academic_regulations.json.
"""

import math
from typing import Literal

from pydantic import BaseModel

# Tool tracking threshold — configured to match VIT's regulation (75% for FAT eligibility).
# Students with CGPA >= 9.0 and no backlogs are EXEMPTED from this rule (9-pointer exemption).
# This calculator always computes against 75% as a reference — the exemption is noted in
# the LLM context, not applied automatically in calculations.
THRESHOLD = 75.0


class AttendanceRisk(BaseModel):
    """Risk assessment for a single course."""

    course_code: str
    course_title: str
    current_percentage: float
    attended: int
    total: int
    risk_level: Literal["safe", "warning", "critical"]
    # How many more classes can be skipped while staying >= 75%
    max_skippable: int
    # How many consecutive classes needed to reach 75% (0 if already above)
    classes_needed_to_reach_75: int


def calculate_risk(
    course_code: str,
    course_title: str,
    attended: int,
    total: int,
) -> AttendanceRisk:
    """Calculate attendance risk for a single course.

    Logic:
    - max_skippable: largest n such that attended / (total + n) >= 0.75
      i.e. n <= (attended / 0.75) - total
    - classes_needed_to_reach_75: smallest m such that (attended + m) / (total + m) >= 0.75
      i.e. m >= (0.75 * total - attended) / (1 - 0.75) = (0.75*total - attended) / 0.25

    Risk levels:
    - critical: current < 75%
    - warning: current >= 75% but max_skippable <= 2
    - safe: current >= 75% and max_skippable > 2
    """
    if total == 0:
        return AttendanceRisk(
            course_code=course_code,
            course_title=course_title,
            current_percentage=0.0,
            attended=attended,
            total=total,
            risk_level="safe",
            max_skippable=0,
            classes_needed_to_reach_75=0,
        )

    current_pct = (attended / total) * 100

    # Classes needed to reach 75%
    if current_pct >= THRESHOLD:
        classes_needed = 0
    else:
        # (attended + m) / (total + m) >= 0.75
        # attended + m >= 0.75 * total + 0.75 * m
        # 0.25 * m >= 0.75 * total - attended
        # m >= (0.75 * total - attended) / 0.25
        needed = (THRESHOLD / 100 * total - attended) / (1 - THRESHOLD / 100)
        classes_needed = max(0, math.ceil(needed))

    # Max skippable while staying >= 75%
    if current_pct < THRESHOLD:
        max_skip = 0
    else:
        # attended / (total + n) >= 0.75
        # n <= attended / 0.75 - total
        skip = attended / (THRESHOLD / 100) - total
        max_skip = max(0, math.floor(skip))

    # Risk level
    if current_pct < THRESHOLD:
        risk_level: Literal["safe", "warning", "critical"] = "critical"
    elif max_skip <= 2:
        risk_level = "warning"
    else:
        risk_level = "safe"

    return AttendanceRisk(
        course_code=course_code,
        course_title=course_title,
        current_percentage=round(current_pct, 2),
        attended=attended,
        total=total,
        risk_level=risk_level,
        max_skippable=max_skip,
        classes_needed_to_reach_75=classes_needed,
    )
