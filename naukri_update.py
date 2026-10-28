"""
Refreshes a Naukri profile so it shows as "recently updated" to recruiters.

What it does each run:
  1. Logs in with NAUKRI_EMAIL / NAUKRI_PASSWORD.
  2. Toggles a trailing "." on the Resume Headline and saves (a real edit Naukri counts).
  3. If a resume file exists (RESUME_PATH, default resume.pdf), re-uploads it too.

On any failure it saves failure.png so you can see what the page looked like.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

EMAIL = os.environ["NAUKRI_EMAIL"]
PASSWORD = os.environ["NAUKRI_PASSWORD"]
RESUME = Path(os.environ.get("RESUME_PATH", "resume.pdf"))

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def login(page):
    page.goto(LOGIN_URL, wait_until="networkidle")
    # Fallbacks in case Naukri renamed the ids.
    page.locator("#usernameField, input[placeholder*='Email' i], input[type=email]").first.fill(EMAIL)
    page.locator("#passwordField, input[type=password]").first.fill(PASSWORD)
    page.locator("button[type=submit]").first.click()
    try:
        page.wait_for_url("**/mnjuser/**", timeout=30_000)
    except PWTimeout:
        raise RuntimeError(
            "Login did not reach the dashboard. Usually an OTP / captcha check "
            "or wrong credentials - see failure.png."
        )
    print("Logged in")


def toggle_headline(page):
    page.goto(PROFILE_URL, wait_until="domcontentloaded")
    page.locator(".resumeHeadline .edit").first.click()

    box = page.locator("#resumeHeadlineTxt")
    box.wait_for(timeout=15_000)
    text = box.input_value().rstrip()
    new_text = text[:-1] if text.endswith(".") else text + "."
    box.fill(new_text)

    page.get_by_role("button", name="Save").first.click()
    page.wait_for_timeout(3_000)
    print("Resume headline updated")


def upload_resume(page):
    if not RESUME.exists():
        print(f"No {RESUME} in repo - skipping resume upload")
        return
    page.goto(PROFILE_URL, wait_until="domcontentloaded")
    page.set_input_files("#attachCV", str(RESUME))
    page.wait_for_timeout(5_000)
    print("Resume re-uploaded")


def main():
    with sync_playwright() as p:
        # Hides the "controlled by automation" flag that bot-checks look for.
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="en-IN")
        page.set_default_timeout(20_000)
        try:
            login(page)
            toggle_headline(page)
            upload_resume(page)
        except Exception as e:
            page.screenshot(path="failure.png", full_page=True)
            Path("failure.html").write_text(page.content(), encoding="utf-8")
            print(f"FAILED at {page.url} (title: {page.title()!r}): {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()