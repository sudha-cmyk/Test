"""
Selenium login for Recruiterflow at localhost.

Your build may use either:
  - data-testid (login-email, login-password, login-sign-in-button), or
  - the classic React login markup (email-input-wrapper, rf-sign-in-button).

This script tries both in order. After sign-in, if a "Multiple Logins Detected" modal
appears, the script clicks Proceed so this session can continue.

Setup:
  pip install -r requirements.txt
  Copy local_settings.example.py to local_settings.py and set LOGIN_URL, EMAIL, PASSWORD.

Run:
  python login.py
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
    raise SystemExit(
        "Create local_settings.py from local_settings.example.py and set LOGIN_URL, EMAIL, PASSWORD."
    )

WAIT_SECONDS = 30

# --- Locator lists: first match wins (data-testid first, then Recruiterflow external login UI) ---
EMAIL_LOCATORS = (
    (By.XPATH, "//*[@data-testid='login-email']"),
    (By.XPATH, "//div[contains(@class,'email-input-wrapper')]//input"),
    (By.CSS_SELECTOR, ".email-input-wrapper input"),
)

PASSWORD_LOCATORS = (
    (By.XPATH, "//*[@data-testid='login-password']"),
    (By.XPATH, "//div[contains(@class,'password-input-wrapper')]//input[@type='password']"),
    (By.CSS_SELECTOR, ".password-input-wrapper input[type='password']"),
)

SIGN_IN_LOCATORS = (
    (By.XPATH, "//*[@data-testid='login-sign-in-button']"),
    (By.XPATH, "//button[contains(@class,'rf-sign-in-button')]"),
    (By.CSS_SELECTOR, "button.rf-sign-in-button"),
)

# Optional modal after sign-in: "Multiple Logins Detected!" → click Proceed (primary button).
MULTIPLE_LOGIN_DIALOG_WAIT = 15
MULTIPLE_LOGIN_PROCEED_LOCATORS = (
    (
        By.XPATH,
        "//div[contains(@class,'confirm-modal-container')]"
        "[.//*[contains(.,'Multiple Logins Detected')]]"
        "//button[contains(@class,'primary-button')]",
    ),
    (
        By.XPATH,
        "//div[contains(@class,'confirm-modal-container')]"
        "[.//*[contains(.,'Multiple Logins')]]"
        "//button[contains(@class,'primary-button')]",
    ),
    (
        By.CSS_SELECTOR,
        ".confirm-modal-container .footer-action-button button.primary-button",
    ),
)


def build_driver():
    options = webdriver.ChromeOptions()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    return driver


def wait_for_any_visible(driver, total_timeout, locators, what):
    """Try each locator until one is visible (split time across options)."""
    if not locators:
        raise TimeoutException(f"No locators for {what}")
    per_try = max(3, total_timeout // len(locators))
    last = None
    for loc in locators:
        try:
            return WebDriverWait(driver, per_try).until(
                EC.visibility_of_element_located(loc)
            )
        except TimeoutException as e:
            last = e
            continue
    raise TimeoutException(
        f"Could not find {what}. Tried: {[str(l) for l in locators]}"
    ) from last


def wait_for_any_clickable(driver, total_timeout, locators, what):
    if not locators:
        raise TimeoutException(f"No locators for {what}")
    per_try = max(3, total_timeout // len(locators))
    last = None
    for loc in locators:
        try:
            return WebDriverWait(driver, per_try).until(
                EC.element_to_be_clickable(loc)
            )
        except TimeoutException as e:
            last = e
            continue
    raise TimeoutException(
        f"Could not find clickable {what}. Tried: {[str(l) for l in locators]}"
    ) from last


def click_proceed_if_multiple_login_modal(driver):
    """
    If Recruiterflow shows the session warning (other active logins), click Proceed.
    If the modal does not appear, continue without error.
    """
    per_try = max(4, MULTIPLE_LOGIN_DIALOG_WAIT // len(MULTIPLE_LOGIN_PROCEED_LOCATORS))
    for loc in MULTIPLE_LOGIN_PROCEED_LOCATORS:
        try:
            btn = WebDriverWait(driver, per_try).until(EC.element_to_be_clickable(loc))
            btn.click()
            print('Clicked "Proceed" on the multiple-logins dialog.')
            time.sleep(1)
            return True
        except TimeoutException:
            continue
    print("No multiple-logins dialog (normal when you only have one active session).")
    return False


def main():
    driver = build_driver()
    wait = WebDriverWait(driver, WAIT_SECONDS)

    try:
        print(f"Opening: {LOGIN_URL}")
        driver.get(LOGIN_URL)

        # React SPA: wait until the login form exists in #root
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#root form")))

        email_el = wait_for_any_visible(driver, WAIT_SECONDS, EMAIL_LOCATORS, "email field")
        email_el.clear()
        email_el.send_keys(EMAIL)
        print("Entered email.")

        password_el = wait_for_any_visible(driver, WAIT_SECONDS, PASSWORD_LOCATORS, "password field")
        password_el.clear()
        password_el.send_keys(PASSWORD)
        print("Entered password.")

        sign_in = wait_for_any_clickable(driver, WAIT_SECONDS, SIGN_IN_LOCATORS, "sign-in button")
        sign_in.click()
        print("Clicked sign in.")

        time.sleep(1.5)
        click_proceed_if_multiple_login_modal(driver)

        time.sleep(2)
        print("Current URL:", driver.current_url)

        input("Press Enter to close the browser...")
    except TimeoutException:
        path = "login_error.png"
        driver.save_screenshot(path)
        print(f"Timed out. Screenshot saved: {path}")
        raise
    finally:
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    main()
