"""Property-based test for HTML parsing logic.

Feature: embedded-vtop-login, Property 8: HTML parsing produces complete structured records

Validates: Requirements 6.2
"""

from hypothesis import given, settings
from hypothesis.strategies import composite, integers, lists, text

from bs4 import BeautifulSoup

from app.connectors.vtop.scrapers import parse_attendance


@composite
def attendance_html_table(draw):
    """Generate valid VTOP attendance HTML tables with N data rows.

    Each row has: S.No, Code, Title, Type, Attended, Total, Percentage
    matching the structure expected by parse_attendance.
    """
    n_rows = draw(integers(min_value=1, max_value=10))
    rows = []
    for i in range(n_rows):
        code = draw(text(alphabet="ABCDEFGHIJKLMNOP0123456789", min_size=6, max_size=8))
        title = draw(text(alphabet="abcdefghijklmnop ", min_size=5, max_size=30))
        attended = draw(integers(min_value=0, max_value=100))
        total = draw(integers(min_value=attended, max_value=100))
        percentage = round((attended / max(total, 1)) * 100, 2)
        rows.append(
            f"<tr><td>{i + 1}</td><td>{code}</td><td>{title}</td>"
            f"<td>TH</td><td>{attended}</td><td>{total}</td>"
            f"<td>{percentage}%</td></tr>"
        )

    header = (
        "<tr><th>S.No</th><th>Code</th><th>Title</th>"
        "<th>Type</th><th>Attended</th><th>Total</th><th>Percentage</th></tr>"
    )
    table_html = (
        f'<html><body><table id="attendanceTable">'
        f'{header}{"".join(rows)}</table></body></html>'
    )
    return table_html, n_rows, rows


@settings(max_examples=100)
@given(data=attendance_html_table())
def test_parse_attendance_produces_correct_count_and_fields(data):
    """For any valid VTOP attendance HTML table containing N data rows,
    the attendance parser SHALL produce exactly N records, each containing
    non-empty course_code, course_title, numeric attended, numeric total,
    and numeric percentage fields.

    **Validates: Requirements 6.2**
    """
    html, expected_count, _ = data
    soup = BeautifulSoup(html, "html.parser")
    records = parse_attendance(soup)

    # Must produce exactly N records
    assert len(records) == expected_count, (
        f"Expected {expected_count} records, got {len(records)}"
    )

    for rec in records:
        # course_code must be present and non-empty
        assert "course_code" in rec and rec["course_code"], (
            f"Record missing or empty course_code: {rec}"
        )

        # course_title must be present and non-empty
        assert "course_title" in rec and rec["course_title"], (
            f"Record missing or empty course_title: {rec}"
        )

        # attended must be present and numeric (int)
        assert "attended" in rec and isinstance(rec["attended"], int), (
            f"Record missing or non-int attended: {rec}"
        )

        # total must be present and numeric (int)
        assert "total" in rec and isinstance(rec["total"], int), (
            f"Record missing or non-int total: {rec}"
        )

        # percentage must be present and numeric (float)
        assert "percentage" in rec and isinstance(rec["percentage"], float), (
            f"Record missing or non-float percentage: {rec}"
        )
