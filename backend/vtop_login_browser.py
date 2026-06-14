# VTOP Browser Login — Used by the CampusFlow sync flow.
# When the user clicks "Sync" and no valid session exists, this script
# is launched as a subprocess to open a browser for reCAPTCHA solving.
# Once login succeeds, cookies are saved to vtop_session.json and
# automatically imported into the DB by the SessionValidator.

"""VTOP Browser Login — Auto-fills credentials, you only solve reCAPTCHA.

Usage:
    python vtop_login_browser.py

Opens Chromium, clicks Student login, fills username + password.
You just solve the reCAPTCHA and click Login. Session saved automatically.

Cookie capture strategy: Intercepts the HTTP response from the login POST
directly to capture the authenticated JSESSIONID from the Set-Cookie header.
This is more reliable than reading from Playwright's cookie jar.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(override=True)

SESSION_FILE = Path(__file__).parent / "vtop_session.json"
VTOP_URL = "https://vtopcc.vit.ac.in/vtop/login"


async def main():
    username = os.getenv("VTOP_USERNAME", "")
    password = os.getenv("VTOP_PASSWORD", "")

    print("=" * 60)
    print("VTOP Browser Login (auto-fill mode)")
    print("=" * 60)
    print(f"Username: {username}")
    print()
    print("I'll click Student Login and fill your credentials.")
    print("You ONLY need to solve the reCAPTCHA and click Login.")
    print("=" * 60)

    # Captured cookies from response headers (the reliable source)
    captured_cookies: dict[str, str] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # ─── Response interceptor: capture Set-Cookie from login POST ─────
        def handle_response(response):
            """Intercept responses to capture the authenticated JSESSIONID.

            The login POST to /vtop/login returns a Set-Cookie header with
            the new authenticated JSESSIONID. This is the ONLY reliable way
            to get the post-login session cookie.
            """
            url = response.url
            method = response.request.method

            # Capture cookies from any response that sets them
            headers = response.headers
            set_cookie = headers.get("set-cookie", "")

            if set_cookie and "vtopcc.vit.ac.in" in url:
                # Parse all Set-Cookie values
                # Response headers may have multiple set-cookie entries
                # but Playwright collapses them — parse what we get
                for part in set_cookie.split(","):
                    part = part.strip()
                    if "=" in part:
                        cookie_name = part.split("=")[0].strip()
                        cookie_value = part.split("=")[1].split(";")[0].strip()
                        if cookie_name in ("JSESSIONID", "SERVERID", "cookiesession1"):
                            old = captured_cookies.get(cookie_name, "")
                            captured_cookies[cookie_name] = cookie_value
                            if cookie_name == "JSESSIONID" and old != cookie_value:
                                print(f"  [INTERCEPTED] {cookie_name} = {cookie_value[:20]}... (from {method} {url.split('?')[0]})")

        page.on("response", handle_response)

        # Step 1: Navigate to VTOP
        await page.goto(VTOP_URL, wait_until="networkidle")
        await asyncio.sleep(1)

        # Capture initial cookies via CDP (bypasses HttpOnly restriction)
        cdp = await context.new_cdp_session(page)
        cdp_result = await cdp.send("Network.getAllCookies")
        initial_all = cdp_result["cookies"]
        initial_vtop = [c for c in initial_all if "vit.ac.in" in c.get("domain", "")]
        print(f"\n=== INITIAL COOKIES via CDP (before login) ===")
        for c in initial_vtop:
            print(f"  {c['name']} = {c['value'][:20]}... | domain={c.get('domain','')} | path={c.get('path','')} | httpOnly={c.get('httpOnly')}")
        print(f"===============================================")
        initial_jsessionid = next((c['value'] for c in initial_vtop if c['name'] == 'JSESSIONID'), None)
        print(f"  Initial JSESSIONID: {initial_jsessionid[:20] if initial_jsessionid else 'NOT FOUND'}")

        print(f"  [INFO] Response interceptor captured: {list(captured_cookies.keys())}")

        # Step 2: Click Student login
        try:
            student_el = page.locator("#student").first
            if await student_el.count() > 0:
                await student_el.click()
                print("✓ Clicked Student login")
            else:
                await page.locator("a:has-text('Student')").first.click()
                print("✓ Clicked Student link")

            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
        except Exception as e:
            try:
                await page.evaluate("document.getElementById('stdForm').submit()")
                print("✓ Submitted stdForm via JS")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1)
            except Exception:
                print(f"⚠ Could not click Student login: {e}")
                print("  Please click it manually.")

        # Remember the pre-login JSESSIONID so we can detect when it changes
        pre_login_jsessionid = captured_cookies.get("JSESSIONID", "")
        print(f"  [INFO] Pre-login JSESSIONID: {pre_login_jsessionid[:20]}...")

        # Step 3: Fill username and password
        try:
            await page.locator("input[name='username']").fill(username)
            print(f"✓ Filled username: {username}")
        except Exception:
            print("⚠ Could not fill username — do it manually")

        try:
            await page.locator("input[name='password']").fill(password)
            print("✓ Filled password")
        except Exception:
            print("⚠ Could not fill password — do it manually")

        print()
        print("━" * 60)
        print("  NOW: Solve the reCAPTCHA and click the Login button.")
        print("━" * 60)

        # Step 4: Wait for login to complete
        try:
            await page.wait_for_url(
                lambda url: "/login" not in url and "/open/page" not in url and "vtop" in url,
                timeout=300000,  # 5 minutes
            )
            print("\n✓ Login successful! URL:", page.url)
        except Exception:
            print("\n⚠ Timeout waiting for URL change.")

        # Give a moment for any final Set-Cookie headers to arrive
        await asyncio.sleep(2)

        # Step 5: Get ALL cookies via CDP — this bypasses HttpOnly restriction
        cdp_result = await cdp.send("Network.getAllCookies")
        all_cookies = cdp_result["cookies"]
        final_cookies = [c for c in all_cookies if "vit.ac.in" in c.get("domain", "")]

        print(f"\n=== FINAL COOKIES via CDP (after login) ===")
        for c in final_cookies:
            print(f"  {c['name']} = {c['value'][:25]}... | domain={c.get('domain','')} | path={c.get('path','')} | httpOnly={c.get('httpOnly')}")
        print("============================================")

        final_jsessionid = next((c['value'] for c in final_cookies if c['name'] == 'JSESSIONID'), None)
        print(f"\n  Initial JSESSIONID: {initial_jsessionid[:20] if initial_jsessionid else 'MISSING'}")
        print(f"  Final   JSESSIONID: {final_jsessionid[:20] if final_jsessionid else 'MISSING'}")
        if initial_jsessionid and final_jsessionid:
            if initial_jsessionid == final_jsessionid:
                print("  → SAME session ID (VTOP authenticates existing session — expected)")
            else:
                print("  → DIFFERENT session ID (VTOP issued new session on login)")
        elif not final_jsessionid:
            print("  ⚠ JSESSIONID MISSING even from CDP!")

        # Step 6: Build cookie list from CDP cookies (guaranteed to include HttpOnly)
        cookie_list = []
        for c in final_cookies:
            cookie_list.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", "vtopcc.vit.ac.in"),
                "path": c.get("path", "/"),
            })

        # Verify JSESSIONID is present
        jsessionid = [c for c in cookie_list if c["name"] == "JSESSIONID"]
        if not jsessionid:
            print("⚠ WARNING: JSESSIONID not in cookie list! Login may have failed.")
        else:
            print(f"✓ JSESSIONID in saved cookies: {jsessionid[0]['value'][:20]}...")

        session_data = {
            "cookies": cookie_list,
            "url": page.url,
        }

        print(f"\n[LOG] Writing {len(cookie_list)} cookies to {SESSION_FILE}...")
        print(f"[LOG] Cookies: {[(c['name'], c['value'][:15]+'...') for c in cookie_list]}")
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)
        print(f"[LOG] Session file written successfully.")

        print(f"\n✓ Session saved to: {SESSION_FILE}")
        print("  The backend will pick this up automatically on next poll.")

        await asyncio.sleep(2)
        await browser.close()


if __name__ == "__main__":
    import traceback
    try:
        asyncio.run(main())
    except Exception as e:
        print("\n" + "!" * 60)
        print("FATAL ERROR:")
        print(traceback.format_exc())
        print("!" * 60)
        input("Press Enter to close...")
