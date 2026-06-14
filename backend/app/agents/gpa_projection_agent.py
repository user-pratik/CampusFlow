"""GPA/CGPA Projection Agent — what-if analysis using VIT's 10-point grading scale.

Pure computation against stored AcademicProfile and CourseMark data.
No LLM calls, no scheduling.
"""

from pydantic import BaseModel

# VIT 10-point grading scale
GRADE_POINTS: dict[str, float] = {
    "S": 10.0,
    "A": 9.0,
    "B": 8.0,
    "C": 7.0,
    "D": 6.0,
    "E": 5.0,
    "F": 0.0,
}

VALID_GRADES = list(GRADE_POINTS.keys())


class ProjectionInput(BaseModel):
    """Input for a single what-if projection."""

    course_code: str
    expected_grade: str  # S, A, B, C, D, E, F
    credits: int = 3  # Default credit weight if not known


class ProjectionResult(BaseModel):
    """Result of a CGPA projection."""

    current_cgpa: float
    current_credits: int
    projected_cgpa: float
    delta: float  # projected - current
    course_code: str
    expected_grade: str
    grade_points: float
    credits_used: int


class RequiredGradeResult(BaseModel):
    """What grades are needed to reach a target CGPA."""

    current_cgpa: float
    current_credits: int
    target_cgpa: float
    achievable: bool
    # Per remaining course: minimum grade needed
    required_grades: list[dict]  # [{course_code, min_grade, grade_points}]
    # If all courses get this grade, target is reached
    uniform_grade_needed: str | None
    message: str


def project_cgpa(
    current_cgpa: float,
    current_credits: int,
    course_code: str,
    expected_grade: str,
    course_credits: int = 3,
) -> ProjectionResult:
    """Project new CGPA if a specific grade is achieved in one course.

    Formula: new_cgpa = (current_cgpa * current_credits + grade_points * course_credits)
                       / (current_credits + course_credits)

    Args:
        current_cgpa: Current cumulative GPA.
        current_credits: Total credits earned so far.
        course_code: The course being projected.
        expected_grade: Expected grade (S/A/B/C/D/E/F).
        course_credits: Credit weight of the course.

    Returns:
        ProjectionResult with projected CGPA and delta.
    """
    grade = expected_grade.upper().strip()
    gp = GRADE_POINTS.get(grade, 0.0)

    if current_credits == 0:
        projected = gp
    else:
        total_points = current_cgpa * current_credits + gp * course_credits
        total_credits = current_credits + course_credits
        projected = total_points / total_credits

    return ProjectionResult(
        current_cgpa=current_cgpa,
        current_credits=current_credits,
        projected_cgpa=round(projected, 4),
        delta=round(projected - current_cgpa, 4),
        course_code=course_code,
        expected_grade=grade,
        grade_points=gp,
        credits_used=course_credits,
    )


def compute_required_grades(
    current_cgpa: float,
    current_credits: int,
    target_cgpa: float,
    remaining_courses: list[dict],  # [{course_code, credits}]
) -> RequiredGradeResult:
    """Determine what grades are needed across remaining courses to hit target CGPA.

    Strategy:
    1. Calculate total grade points needed across all remaining courses.
    2. Determine minimum uniform grade that achieves the target.
    3. Per-course: find the minimum grade that contributes enough.

    Args:
        current_cgpa: Current cumulative GPA.
        current_credits: Total credits earned so far.
        target_cgpa: Desired CGPA to achieve.
        remaining_courses: List of courses with credits still to be graded.

    Returns:
        RequiredGradeResult with per-course breakdown and achievability.
    """
    if not remaining_courses:
        achievable = current_cgpa >= target_cgpa
        return RequiredGradeResult(
            current_cgpa=current_cgpa,
            current_credits=current_credits,
            target_cgpa=target_cgpa,
            achievable=achievable,
            required_grades=[],
            uniform_grade_needed=None,
            message="Already at target." if achievable else "No remaining courses to improve CGPA.",
        )

    remaining_credits = sum(c.get("credits", 3) for c in remaining_courses)
    total_credits_after = current_credits + remaining_credits

    # Total grade points needed from remaining courses
    # target_cgpa = (current_cgpa * current_credits + needed_points) / total_credits_after
    needed_points = target_cgpa * total_credits_after - current_cgpa * current_credits

    # Check if achievable (max possible = all S grades = 10 * remaining_credits)
    max_possible_points = 10.0 * remaining_credits

    if needed_points > max_possible_points:
        return RequiredGradeResult(
            current_cgpa=current_cgpa,
            current_credits=current_credits,
            target_cgpa=target_cgpa,
            achievable=False,
            required_grades=[],
            uniform_grade_needed=None,
            message=f"Target {target_cgpa} is not achievable even with all S grades. "
                    f"Max possible: {round((current_cgpa * current_credits + max_possible_points) / total_credits_after, 2)}",
        )

    if needed_points <= 0:
        return RequiredGradeResult(
            current_cgpa=current_cgpa,
            current_credits=current_credits,
            target_cgpa=target_cgpa,
            achievable=True,
            required_grades=[
                {"course_code": c.get("course_code", "?"), "min_grade": "F", "grade_points": 0.0}
                for c in remaining_courses
            ],
            uniform_grade_needed="F",
            message=f"Already above target! Even F grades won't drop below {target_cgpa}.",
        )

    # Uniform grade needed: needed_points / remaining_credits = required GP per credit
    required_gp_per_credit = needed_points / remaining_credits

    # Find minimum uniform grade
    uniform_grade = None
    for grade in ["F", "E", "D", "C", "B", "A", "S"]:
        if GRADE_POINTS[grade] >= required_gp_per_credit:
            uniform_grade = grade
            break

    # Per-course minimum (simplified: assume equal distribution)
    per_course_grades = []
    for course in remaining_courses:
        credits = course.get("credits", 3)
        # Points this course needs to contribute (proportional)
        course_needed = required_gp_per_credit  # GP per credit is same for all
        min_grade = "S"
        for grade in ["F", "E", "D", "C", "B", "A", "S"]:
            if GRADE_POINTS[grade] >= course_needed:
                min_grade = grade
                break
        per_course_grades.append({
            "course_code": course.get("course_code", "?"),
            "min_grade": min_grade,
            "grade_points": GRADE_POINTS[min_grade],
            "credits": credits,
        })

    return RequiredGradeResult(
        current_cgpa=current_cgpa,
        current_credits=current_credits,
        target_cgpa=target_cgpa,
        achievable=True,
        required_grades=per_course_grades,
        uniform_grade_needed=uniform_grade,
        message=f"Need at least {uniform_grade} in all remaining courses "
                f"({remaining_credits} credits) to reach {target_cgpa} CGPA.",
    )
