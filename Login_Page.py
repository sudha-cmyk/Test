"""
Simple login: open Chrome, go to Recruiterflow on localhost, sign in, optional
"Multiple logins" Proceed, then close the browser.

Tries your data-testid XPaths first; on localhost the login form is usually
class-based (email-input-wrapper, rf-sign-in-button), so fallbacks are included.

Uses local_settings.py: LOGIN_URL, EMAIL, PASSWORD.

Run:
  python simple_login.py
"""

import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

try:
    from local_settings import EMAIL, LOGIN_URL, PASSWORD
except ImportError:
    raise SystemExit("Create local_settings.py with LOGIN_URL, EMAIL, PASSWORD.")

# data-testid first, then class-based (localhost Recruiterflow usually needs the second set).
EMAIL_XPATHS = [
    "//input[@data-testid='login-email']",
    "//div[contains(@class,'email-input-wrapper')]//input",
]
PASSWORD_XPATHS = [
    "//input[@data-testid='login-password']",
    "//div[contains(@class,'password-input-wrapper')]//input[@type='password']",
]
SUBMIT_XPATHS = [
    "//button[@data-testid='login-sign-in-button']",
    "//button[contains(@class,'rf-sign-in-button')]",
]

# "Multiple logins" modal (Recruiterflow) — only if it appears
PROCEED_BUTTON = (
    "//div[contains(@class,'confirm-modal-container')]"
    "[.//*[contains(.,'Multiple Logins Detected') or contains(.,'Multiple Logins')]]"
    "//button[contains(@class,'primary-button')]"
)

WAIT_SEC = 30
PER_TRY = 6  # seconds to try each XPath
MULTI_LOGIN_WAIT = 15


def _first_by_xpath(driver, xpaths, visible=True):
    """
    Return (element, used_xpath) for the first locator that works.
    """
    last = None
    for xp in xpaths:
        try:
            w = WebDriverWait(driver, PER_TRY)
            cond = (
                EC.visibility_of_element_located((By.XPATH, xp))
                if visible
                else EC.presence_of_element_located((By.XPATH, xp))
            )
            el = w.until(cond)
            return el, xp
        except TimeoutException as e:
            last = e
            continue
    raise TimeoutException("None of the tried XPaths matched: " + str(xpaths)) from last


def _first_clickable_xpath(driver, xpaths):
    last = None
    for xp in xpaths:
        try:
            el = WebDriverWait(driver, PER_TRY).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            return el, xp
        except TimeoutException as e:
            last = e
            continue
    raise TimeoutException("None of the tried XPaths matched: " + str(xpaths)) from last


def build_driver():
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=webdriver.ChromeOptions())
    driver.maximize_window()
    return driver


def try_click_multiple_login_proceed(driver):
    try:
        btn = WebDriverWait(driver, MULTI_LOGIN_WAIT).until(
            EC.element_to_be_clickable((By.XPATH, PROCEED_BUTTON))
        )
        btn.click()
        print('Clicked "Proceed" (multiple logins).')
        time.sleep(1)
    except TimeoutException:
        pass


def main():
    driver = build_driver()

    try:
        print("Opening", LOGIN_URL)
        driver.get(LOGIN_URL)

        # React app: form mounts under #root
        try:
            WebDriverWait(driver, WAIT_SEC).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#root form"))
            )
        except TimeoutException:
            pass

        el_email, _xp = _first_by_xpath(driver, EMAIL_XPATHS)
        print("Email field found:", _xp[:70] + ("…" if len(_xp) > 70 else ""))
        el_email.clear()
        el_email.send_keys(EMAIL)

        el_pass, _xp2 = _first_by_xpath(driver, PASSWORD_XPATHS)
        el_pass.clear()
        el_pass.send_keys(PASSWORD)

        el_submit, _xp3 = _first_clickable_xpath(driver, SUBMIT_XPATHS)
        el_submit.click()
        print("Sign-in clicked. Button was:", _xp3[:70] + ("…" if len(_xp3) > 70 else ""))

        time.sleep(1.5)
        try_click_multiple_login_proceed(driver)

        time.sleep(1)
        print("Current URL:", driver.current_url)
        print("Done.")
    except TimeoutException as e:
        try:
            driver.save_screenshot("simple_login_error.png")
        except Exception:
            pass
        print(
            "Timed out — is the app running? Is Recruiterflow on",
            LOGIN_URL,
            "? (Also try: email/password may use class-based fields, not data-testid.)",
        )
        raise e
    finally:
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    main()
