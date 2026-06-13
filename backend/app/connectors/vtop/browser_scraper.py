"""Playwright-based VTOP scraper — replicates the Android app's jQuery AJAX approach.

Uses saved session cookies + Playwright to load the VTOP content page,
then executes the same jQuery $.ajax() calls the Android app uses to fetch data.
"""

import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

SESSION_FILE = Path(__file__).resolve().parent.parent.parent.parent / "vtop_session.json"


class VTOPBrowserScraper:
    """Headless Playwright scraper using the same AJAX approach as the Android app."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page: Page | None = None

    async def start(self) -> bool:
        """Launch browser, load cookies, navigate to content page."""
        if not SESSION_FILE.exists():
            logger.error("No session file. Run 'python vtop_login_browser.py' first.")
            return False

        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        cookies = session_data.get("cookies", [])
        if not cookies:
            logger.error("Session file has no cookies.")
            return False

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=False)
        context = await self._browser.new_context(ignore_https_errors=True)
        await context.add_cookies(cookies)

        self._page = await context.new_page()

        try:
            await self._page.goto(
                "https://vtopcc.vit.ac.in/vtop/content",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            if "/login" in self._page.url:
                logger.error("Session expired. Re-run vtop_login_browser.py.")
                await self.close()
                return False

            # Wait for jQuery and authorizedIDX to be available
            await self._page.wait_for_function(
                "() => typeof $ !== 'undefined' && $('#authorizedIDX').length === 1",
                timeout=15000,
            )

            logger.info("VTOP dashboard loaded with jQuery available.")
            return True

        except Exception as e:
            logger.error("Failed to load VTOP dashboard: %s", e)
            await self.close()
            return False

    async def get_semesters(self) -> dict:
        """Get available semesters. Returns dict of {name: id}."""
        result = await self._run_ajax("""
            var data = 'verifyMenu=true&authorizedID=' + $('#authorizedIDX').val() + '&_csrf=' + $('input[name="_csrf"]').val() + '&nocache=@' + new Date().getTime();
            var response = {};
            $.ajax({
                type: 'POST',
                url: 'academics/common/StudentTimeTableChn',
                data: data,
                async: false,
                success: function(res) {
                    var doc = new DOMParser().parseFromString(res, 'text/html');
                    var select = doc.getElementById('semesterSubId');
                    if (select) {
                        var options = select.getElementsByTagName('option');
                        var semesters = {};
                        for (var i = 0; i < options.length; ++i) {
                            if (options[i].value) {
                                semesters[options[i].innerText.trim()] = options[i].value;
                            }
                        }
                        response = semesters;
                    }
                }
            });
            return response;
        """)
        return result if isinstance(result, dict) else {}

    async def scrape_attendance(self, semester_id: str) -> list[dict]:
        """Scrape attendance using the same AJAX call as the Android app."""
        result = await self._run_ajax(f"""
            var data = '_csrf=' + $('input[name="_csrf"]').val() + '&semesterSubId={semester_id}&authorizedID=' + $('#authorizedIDX').val();
            var response = {{ attendance: [] }};
            $.ajax({{
                type: 'POST',
                url: 'processViewStudentAttendance',
                data: data,
                async: false,
                success: function(res) {{
                    var doc = new DOMParser().parseFromString(res, 'text/html');
                    var table = doc.getElementById('getStudentDetails');
                    if (!table) return;
                    var headings = table.getElementsByTagName('th');
                    var codeIdx, titleIdx, attendedIdx, totalIdx, percentIdx;
                    for (var i = 0; i < headings.length; ++i) {{
                        var h = headings[i].innerText.toLowerCase();
                        if (h.includes('code')) codeIdx = i;
                        else if (h.includes('title') || h.includes('name')) titleIdx = i;
                        else if (h.includes('attended')) attendedIdx = i;
                        else if (h.includes('total')) totalIdx = i;
                        else if (h.includes('percentage')) percentIdx = i;
                    }}
                    var cells = table.getElementsByTagName('td');
                    while (attendedIdx < cells.length && totalIdx < cells.length && percentIdx < cells.length) {{
                        var obj = {{}};
                        obj.course_code = codeIdx !== undefined ? cells[codeIdx].innerText.trim() : '';
                        obj.course_title = titleIdx !== undefined ? cells[titleIdx].innerText.trim() : '';
                        obj.attended = parseInt(cells[attendedIdx].innerText.trim()) || 0;
                        obj.total = parseInt(cells[totalIdx].innerText.trim()) || 0;
                        obj.percentage = parseInt(cells[percentIdx].innerText.trim()) || 0;
                        response.attendance.push(obj);
                        if (codeIdx !== undefined) codeIdx += headings.length;
                        if (titleIdx !== undefined) titleIdx += headings.length;
                        attendedIdx += headings.length;
                        totalIdx += headings.length;
                        percentIdx += headings.length;
                    }}
                }}
            }});
            return response;
        """)
        return result.get("attendance", []) if isinstance(result, dict) else []

    async def scrape_marks(self, semester_id: str) -> list[dict]:
        """Scrape marks using the same nested-table approach as the Android app.

        Returns a flat list of mark entries, each containing:
        - course_code, course_title, course_type
        - mark_title, max_mark, weightage_pct, score, weightage_mark, status
        """
        result = await self._run_ajax(f"""
            var data = 'semesterSubId={semester_id}&authorizedID=' + $('#authorizedIDX').val() + '&_csrf=' + $('input[name="_csrf"]').val();
            var response = {{ marks: [] }};
            $.ajax({{
                type: 'POST',
                url: 'examinations/doStudentMarkView',
                data: data,
                async: false,
                success: function(res) {{
                    if (res.toLowerCase().includes('no data found')) return;
                    var doc = new DOMParser().parseFromString(res, 'text/html');
                    var table = doc.getElementById('fixedTableContainer');
                    if (!table) return;

                    var rows = table.getElementsByTagName('tr');

                    // Find course-level column indices from header row
                    var headings = rows[0].getElementsByTagName('td');
                    var courseTypeIdx, slotIdx;
                    for (var i = 0; i < headings.length; ++i) {{
                        var h = headings[i].innerText.toLowerCase();
                        if (h.includes('course') && h.includes('type')) courseTypeIdx = i;
                        else if (h.includes('slot')) slotIdx = i;
                    }}

                    // Iterate course blocks
                    for (var i = 1; i < rows.length; ++i) {{
                        var courseCells = rows[i].getElementsByTagName('td');
                        if (courseCells.length < 3) continue;

                        // Extract course info from the header row of each block
                        var rawCourseType = courseCells[courseTypeIdx] ? courseCells[courseTypeIdx].innerText.trim().toLowerCase() : '';
                        var courseType = rawCourseType.includes('lab') ? 'Lab' : (rawCourseType.includes('project') ? 'Project' : 'Theory');

                        // Course code is typically in column 2, title in column 3
                        var courseCode = courseCells[2] ? courseCells[2].innerText.trim() : '';
                        var courseTitle = courseCells[3] ? courseCells[3].innerText.trim() : '';

                        // Move to the inner marks table (next row)
                        i++;
                        if (i >= rows.length) break;

                        var innerTable = rows[i].getElementsByTagName('table')[0];
                        if (!innerTable) continue;

                        var innerRows = innerTable.getElementsByTagName('tr');
                        if (innerRows.length < 2) continue;

                        // Parse inner table headers
                        var innerHeadings = innerRows[0].getElementsByTagName('td');
                        var titleI = -1, maxI = -1, weightPctI = -1, statusI = -1, scoreI = -1, weightMarkI = -1;
                        for (var j = 0; j < innerHeadings.length; ++j) {{
                            var ih = innerHeadings[j].innerText.toLowerCase().trim();
                            if (ih.includes('title')) titleI = j;
                            else if (ih.includes('max') && ih.includes('mark')) maxI = j;
                            else if (ih.includes('weightage') && ih.includes('%')) weightPctI = j;
                            else if (ih.includes('status')) statusI = j;
                            else if (ih.includes('scored')) scoreI = j;
                            else if (ih.includes('weightage') && ih.includes('mark')) weightMarkI = j;
                        }}

                        // Parse each mark row
                        for (var k = 1; k < innerRows.length; ++k) {{
                            var markCells = innerRows[k].getElementsByTagName('td');
                            if (markCells.length < 3) continue;

                            var mark = {{}};
                            mark.course_code = courseCode;
                            mark.course_title = courseTitle;
                            mark.course_type = courseType;
                            mark.mark_title = titleI >= 0 && titleI < markCells.length ? markCells[titleI].innerText.trim() : '';
                            mark.max_mark = maxI >= 0 && maxI < markCells.length ? parseFloat(markCells[maxI].innerText) || 0 : 0;
                            mark.weightage_pct = weightPctI >= 0 && weightPctI < markCells.length ? parseFloat(markCells[weightPctI].innerText) || 0 : 0;
                            mark.status = statusI >= 0 && statusI < markCells.length ? markCells[statusI].innerText.trim() : '';
                            mark.score = scoreI >= 0 && scoreI < markCells.length ? parseFloat(markCells[scoreI].innerText) || 0 : 0;
                            mark.weightage_mark = weightMarkI >= 0 && weightMarkI < markCells.length ? parseFloat(markCells[weightMarkI].innerText) || 0 : 0;

                            if (mark.mark_title) {{
                                response.marks.push(mark);
                            }}
                        }}

                        // Skip remaining inner table rows
                        i += innerRows.length;
                    }}
                }}
            }});
            return response;
        """)
        return result.get("marks", []) if isinstance(result, dict) else []

    async def scrape_cgpa(self) -> dict:
        """Scrape CGPA and total credits from Grade History page."""
        result = await self._run_ajax("""
            var data = 'verifyMenu=true&authorizedID=' + $('#authorizedIDX').val() + '&_csrf=' + $('input[name="_csrf"]').val() + '&nocache=@' + new Date().getTime();
            var response = { cgpa: 0, total_credits: 0 };
            $.ajax({
                type: 'POST',
                url: 'examinations/examGradeView/StudentGradeHistory',
                data: data,
                async: false,
                success: function(res) {
                    var doc = new DOMParser().parseFromString(res, 'text/html');
                    var tables = doc.getElementsByTagName('table');
                    for (var i = tables.length - 1; i >= 0; --i) {
                        var headings = tables[i].getElementsByTagName('tr')[0].getElementsByTagName('td');
                        if (headings[0] && headings[0].innerText.toLowerCase().includes('credits')) {
                            var creditsIndex, cgpaIndex;
                            for (var j = 0; j < headings.length; ++j) {
                                var heading = headings[j].innerText.toLowerCase();
                                if (heading.includes('earned')) creditsIndex = j + headings.length;
                                else if (heading.includes('cgpa')) cgpaIndex = j + headings.length;
                            }
                            var cells = tables[i].getElementsByTagName('td');
                            response.cgpa = parseFloat(cells[cgpaIndex].innerText) || 0;
                            response.total_credits = parseInt(cells[creditsIndex].innerText) || 0;
                            break;
                        }
                    }
                }
            });
            return response;
        """)
        return result if isinstance(result, dict) else {"cgpa": 0.0, "total_credits": 0}

    async def _run_ajax(self, js_code: str):
        """Execute JavaScript in the page context and return the result."""
        if not self._page:
            return None

        try:
            result = await self._page.evaluate(f"(function() {{ {js_code} }})()")
            return result
        except Exception as e:
            logger.error("JS evaluation failed: %s", e)
            return None

    async def close(self):
        """Close browser and Playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
