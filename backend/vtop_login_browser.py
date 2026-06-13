"""VTOP Browser Login — Auto-fills credentials, you only solve reCAPTCHA.

Usage:
    python vtop_login_browser.py

Opens Chromium, clicks Student login, fills username + password.
You just solve the reCAPTCHA and click Login. Session saved automatically.
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

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # Step 1: Navigate to VTOP
        await page.goto(VTOP_URL, wait_until="networkidle")
        await asyncio.sleep(1)

        # Step 2: Click Student login
        try:
            # Click the student image/link
            student_el = page.locator("#student").first
            if await student_el.count() > 0:
                await student_el.click()
                print("✓ Clicked Student login")
            else:
                # Try text-based click
                await page.locator("a:has-text('Student')").first.click()
                print("✓ Clicked Student link")

            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
        except Exception as e:
            # Maybe the form is already in a submission state, try submitting stdForm
            try:
                await page.evaluate("document.getElementById('stdForm').submit()")
                print("✓ Submitted stdForm via JS")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1)
            except Exception:
                print(f"⚠ Could not click Student login: {e}")
                print("  Please click it manually.")

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
                lambda url: "/login" not in url and "vtop" in url,
                timeout=300000,  # 5 minutes
            )
            print("\n✓ Login successful!")
        except Exception:
            print("\n⚠ Timeout. Saving cookies anyway...")

        # Step 5: Save cookies
        cookies = await context.cookies()
        session_data = {
            "cookies": cookies,
            "url": page.url,
        }

        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        print(f"✓ Session saved ({len(cookies)} cookies) to: {SESSION_FILE}")
        print("  The connector will reuse this automatically.")
        print("  Session lasts ~8-12 hours.")

        await asyncio.sleep(2)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
