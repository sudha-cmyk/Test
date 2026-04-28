"""
Selenium automation: log in, open Add Candidate, fill core fields, save, verify, quit.

Credentials: LOGIN_URL, EMAIL, PASSWORD in local_settings.py

Each run builds **unique** candidate data (uuid / random / timestamp):
  - Email: testuser_<timestamp>@mail.com (timestamp from time.time_ns())
  - Phone: random 10-digit US-style number
  - Names: optional seeds CANDIDATE_FIRST_NAME / CANDIDATE_LAST_NAME; each run appends a
    unique suffix. Set ADD_CANDIDATE_USE_RANDOM_NAME_POOL = True for random pool names + suffix.

Run:
    python add_candidate_automation.py

Uses WebDriverWait for synchronization; adds a 1–2 s pause after major clicks/inputs
so the UI can settle (see pause_after_major_action).
"""

from __future__ import annotations

import random
import sys
import time
import uuid
from dataclasses import dataclass

from selenium import webdriver
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    import local_settings as _local
except ImportError as e:
    raise SystemExit(
        "Create local_settings.py (copy from local_settings.example.py) with "
        f"LOGIN_URL, EMAIL, PASSWORD. ({e})"
    ) from e

try:
    LOGIN_URL = _local.LOGIN_URL
    EMAIL = _local.EMAIL
    PASSWORD = _local.PASSWORD
except AttributeError as e:
    raise SystemExit("local_settings.py must define LOGIN_URL, EMAIL, and PASSWORD.") from e

# Optional name seeds (each run still gets a unique suffix).
_NAME_SEED_FIRST = getattr(_local, "CANDIDATE_FIRST_NAME", "Test")
_NAME_SEED_LAST = getattr(_local, "CANDIDATE_LAST_NAME", "User")

# Built-in pools when using random name parts (still unique per run via suffix).
_FIRST_NAME_POOL = (
    "Alex",
    "Jordan",
    "Taylor",
    "Riley",
    "Casey",
    "Morgan",
    "Quinn",
    "Avery",
    "Jamie",
    "Reese",
)
_LAST_NAME_POOL = (
    "Smith",
    "Jones",
    "Brown",
    "Davis",
    "Miller",
    "Wilson",
    "Moore",
    "Taylor",
    "Anderson",
    "Thomas",
)


@dataclass(frozen=True)
class CandidateTestData:
    """One-off candidate row for a single automation run."""

    first_name: str
    last_name: str
    email: str
    phone: str


def _random_us_phone_digits() -> str:
    """10-digit NANP-style number (not guaranteed valid NPA/NXX; fine for test forms)."""
    area = random.randint(200, 999)
    prefix = random.randint(200, 999)
    line = random.randint(0, 9999)
    return f"{area}{prefix}{line:04d}"


def generate_unique_candidate_data(
    *,
    use_random_name_from_pool: bool = False,
) -> CandidateTestData:
    """
    Build unique first/last/email/phone for this run.

    Email pattern: ``testuser_<timestamp>@mail.com`` using ``time.time_ns()`` so each
    run is unique even under fast consecutive executions.

    Names: either ``<seed>_<suffix>`` or ``<random_pool_name>_<suffix>``.
    """
    suffix = uuid.uuid4().hex[:10]
    email = f"testuser_{time.time_ns()}@mail.com"

    if use_random_name_from_pool:
        first = f"{random.choice(_FIRST_NAME_POOL)}_{suffix[:8]}"
        last = f"{random.choice(_LAST_NAME_POOL)}_{suffix[:8]}"
    else:
        first = f"{_NAME_SEED_FIRST}_{suffix[:8]}"
        last = f"{_NAME_SEED_LAST}_{suffix[:8]}"

    phone = _random_us_phone_digits()
    return CandidateTestData(
        first_name=first,
        last_name=last,
        email=email,
        phone=phone,
    )

# Reuse login field locators and Chrome driver factory from this project.
from Login_Page import (
    EMAIL_XPATHS,
    PASSWORD_XPATHS,
    PROCEED_BUTTON,
    SUBMIT_XPATHS,
    _first_by_xpath,
    _first_clickable_xpath,
    build_driver,
)

# --- Locators provided for the add-candidate flow (absolute XPaths) ---
XP_ADD_CANDIDATE_BUTTON = '//*[@id="root"]/div/header/ul/li[2]/div[1]/button'
XP_FIRST_NAME = '//*[@id="main-content-wrapper-id"]/div/div[1]/div/div/div[1]/div/div[1]/ul/li[1]/div/div[1]/input'
XP_LAST_NAME = '//*[@id="main-content-wrapper-id"]/div/div[1]/div/div/div[1]/div/div[1]/ul/li[1]/div/div[2]/input'
XP_EMAIL = '//*[@id="main-content-wrapper-id"]/div/div[1]/div/div/div[1]/div/div[1]/ul/li[2]/div/input'
XP_PHONE = '//*[@id="main-content-wrapper-id"]/div/div[1]/div/div/div[1]/div/div[1]/ul/li[3]/div/div/input'
XP_CREATE_CANDIDATE = '//*[@id="main-content-wrapper-id"]/div/div[2]/div/button[1]'

DEFAULT_WAIT_SECONDS = 30
LOGIN_NAV_WAIT = 45
DASHBOARD_WAIT = 45
FORM_WAIT = 30
# Allow time for save API, toast, or client-side navigation after Create.
POST_CREATE_WAIT = 45

# Visible regions that often host success copy (Recruiterflow / React / MUI patterns).
SUCCESS_MESSAGE_CONTAINER_XPATHS = (
    "//*[@role='alert']",
    "//div[contains(@class,'Toastify__toast')]",
    "//div[contains(@class,'toast')]",
    "//*[contains(@class,'Snackbar')]",
    "//*[contains(@class,'snackbar')]",
    "//*[contains(@class,'notification')]",
    "//*[contains(@class,'MuiAlert')]",
    "//*[contains(@class,'rf-toast')]",
)
SUCCESS_TEXT_KEYWORDS = (
    "success",
    "created",
    "added",
    "saved",
    "candidate",
)


def pause_after_major_action() -> None:
    """Sleep 1–2 seconds after a click, text input, navigation, or leaving the login route."""
    time.sleep(random.uniform(1.0, 2.0))


def build_wait(driver: webdriver.Chrome, seconds: int = DEFAULT_WAIT_SECONDS) -> WebDriverWait:
    """Standard explicit wait helper."""
    return WebDriverWait(driver, seconds)


# ---------------------------------------------------------------------------
# Step 1–2: open login page and sign in
# ---------------------------------------------------------------------------
def navigate_to_login(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """Launch is implicit in build_driver; navigate to the configured login URL."""
    driver.get(LOGIN_URL)
    pause_after_major_action()
    # Wait for the React login shell when present (non-fatal if the DOM differs slightly).
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#root form")))
    except TimeoutException:
        pass


def perform_login(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """Fill email/password and submit; dismiss optional multi-login modal via explicit wait."""
    el_email, _ = _first_by_xpath(driver, EMAIL_XPATHS)
    el_email.clear()
    el_email.send_keys(EMAIL)
    pause_after_major_action()

    el_pass, _ = _first_by_xpath(driver, PASSWORD_XPATHS)
    el_pass.clear()
    el_pass.send_keys(PASSWORD)
    pause_after_major_action()

    el_submit, _ = _first_clickable_xpath(driver, SUBMIT_XPATHS)
    el_submit.click()
    pause_after_major_action()

    # Optional “Multiple logins” dialog — wait only if it appears.
    modal_wait = WebDriverWait(driver, 5)
    try:
        proceed = modal_wait.until(
            EC.element_to_be_clickable((By.XPATH, PROCEED_BUTTON))
        )
        proceed.click()
        pause_after_major_action()
    except TimeoutException:
        pass

    # Confirm we left the login route (dashboard or app home).
    WebDriverWait(driver, LOGIN_NAV_WAIT).until(
        lambda d: "/login" not in (d.current_url or "").lower()
    )
    pause_after_major_action()


# ---------------------------------------------------------------------------
# Step 3: dashboard ready
# ---------------------------------------------------------------------------
def wait_for_dashboard_ready(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """
    Treat the header “Add Candidate” control as the signal that the shell UI is ready.
    """
    wait.until(EC.element_to_be_clickable((By.XPATH, XP_ADD_CANDIDATE_BUTTON)))


# ---------------------------------------------------------------------------
# Step 4–5: open form and wait for fields
# ---------------------------------------------------------------------------
def click_add_candidate(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """Click the Add Candidate entry in the header."""
    btn = wait.until(EC.element_to_be_clickable((By.XPATH, XP_ADD_CANDIDATE_BUTTON)))
    btn.click()
    pause_after_major_action()


def wait_for_candidate_form(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """Wait until the first-name input for the add flow is present and interactable."""
    form_wait = WebDriverWait(driver, FORM_WAIT)
    form_wait.until(EC.visibility_of_element_located((By.XPATH, XP_FIRST_NAME)))


# ---------------------------------------------------------------------------
# Step 6: fill fields
# ---------------------------------------------------------------------------
def fill_candidate_form(
    driver: webdriver.Chrome, wait: WebDriverWait, data: CandidateTestData
) -> None:
    """Populate first name, last name, email, and phone from generated test data."""
    fn = wait.until(EC.element_to_be_clickable((By.XPATH, XP_FIRST_NAME)))
    fn.clear()
    fn.send_keys(data.first_name)
    pause_after_major_action()

    ln = wait.until(EC.element_to_be_clickable((By.XPATH, XP_LAST_NAME)))
    ln.clear()
    ln.send_keys(data.last_name)
    pause_after_major_action()

    em = wait.until(EC.element_to_be_clickable((By.XPATH, XP_EMAIL)))
    em.clear()
    em.send_keys(data.email)
    pause_after_major_action()

    ph = wait.until(EC.element_to_be_clickable((By.XPATH, XP_PHONE)))
    ph.clear()
    ph.send_keys(data.phone)
    pause_after_major_action()


# ---------------------------------------------------------------------------
# Step 7–8: submit and verify
# ---------------------------------------------------------------------------
def click_create_candidate(
    driver: webdriver.Chrome, wait: WebDriverWait
) -> tuple[WebElement, str]:
    """
    Click Create Candidate. Returns (create_button_element, url_before_click) for verification.
    """
    create = wait.until(EC.element_to_be_clickable((By.XPATH, XP_CREATE_CANDIDATE)))
    url_before = driver.current_url or ""
    create.click()
    pause_after_major_action()
    return create, url_before


def _visible_success_toast_or_alert(driver: webdriver.Chrome) -> bool:
    """True if a visible toast/alert/snackbar likely reports a successful save."""
    for xp in SUCCESS_MESSAGE_CONTAINER_XPATHS:
        try:
            for el in driver.find_elements(By.XPATH, xp):
                try:
                    if not el.is_displayed():
                        continue
                    text = (el.text or "").strip().lower()
                    if not text:
                        continue
                    if any(k in text for k in SUCCESS_TEXT_KEYWORDS):
                        return True
                except StaleElementReferenceException:
                    continue
        except Exception:
            continue
    # Short, specific banner text (avoid matching huge page bodies).
    try:
        for el in driver.find_elements(
            By.XPATH,
            "//*[self::div or self::span][string-length(normalize-space(.)) < 180]"
            "[contains(., 'Candidate')]"
            "[contains(., 'created') or contains(., 'Created')]",
        ):
            if el.is_displayed():
                return True
    except Exception:
        pass
    return False


def _candidate_save_signals(
    driver: webdriver.Chrome,
    first_name_el,
    create_button_el,
    url_before: str,
) -> bool:
    """Return True if any heuristic indicates the candidate was created."""
    # DOM replaced (navigation or full re-render)
    try:
        first_name_el.is_displayed()
    except StaleElementReferenceException:
        return True

    if create_button_el is not None:
        try:
            create_button_el.is_displayed()
        except StaleElementReferenceException:
            return True

    # Same node kept but form reset to empty
    try:
        if not (first_name_el.get_attribute("value") or "").strip():
            return True
    except StaleElementReferenceException:
        return True

    cur = driver.current_url or ""
    low = cur.lower()
    prev_low = (url_before or "").lower()

    if cur and cur != url_before and "/login" not in low:
        return True

    # Started on an “add” screen and the app navigated away from that route after save.
    if (
        ("/prospect/add" in prev_low or "/candidates/add" in prev_low)
        and "/prospect/add" not in low
        and "/candidates/add" not in low
        and "/login" not in low
    ):
        return True

    if _visible_success_toast_or_alert(driver):
        return True

    return False


def verify_candidate_created(
    driver: webdriver.Chrome,
    first_name_element,
    create_button_element,
    url_before: str,
) -> bool:
    """
    Poll until POST_CREATE_WAIT for staleness, cleared first name, URL change,
    or a success-style toast/message.
    """
    try:
        WebDriverWait(driver, POST_CREATE_WAIT).until(
            lambda d: _candidate_save_signals(
                d, first_name_element, create_button_element, url_before
            )
        )
        return True
    except TimeoutException:
        return False


def run() -> int:
    driver = None
    try:
        driver = build_driver()
        wait = build_wait(driver)

        # Step 1–2: Login page + credentials
        navigate_to_login(driver, wait)
        perform_login(driver, wait)

        # Step 3: Dashboard / app chrome loaded
        dash_wait = WebDriverWait(driver, DASHBOARD_WAIT)
        wait_for_dashboard_ready(driver, dash_wait)

        # Step 4–5: Add candidate + form visible
        click_add_candidate(driver, dash_wait)
        wait_for_candidate_form(driver, build_wait(driver, FORM_WAIT))

        # Unique candidate row for this run (email / phone / names never reused as-is).
        use_random_names = getattr(_local, "ADD_CANDIDATE_USE_RANDOM_NAME_POOL", False)
        candidate = generate_unique_candidate_data(
            use_random_name_from_pool=use_random_names,
        )
        print(
            "Generated candidate:",
            f"{candidate.first_name} {candidate.last_name} | {candidate.email} | {candidate.phone}",
        )

        # Step 6: Fill fields (keep reference to first name for verification)
        fill_candidate_form(driver, build_wait(driver, FORM_WAIT), candidate)
        first_el = driver.find_element(By.XPATH, XP_FIRST_NAME)

        # Step 7: Submit (keep button ref + URL for verification)
        create_el, url_before_create = click_create_candidate(
            driver, build_wait(driver, FORM_WAIT)
        )

        # Step 8: Verify when possible
        if verify_candidate_created(driver, first_el, create_el, url_before_create):
            print("Verification: form cleared or navigated after create (success signal).")
        else:
            print(
                "Verification: no success signal within the wait window. "
                "Check the UI, network, or extend SUCCESS_MESSAGE_CONTAINER_XPATHS / "
                "_candidate_save_signals() in add_candidate_automation.py.",
                file=sys.stderr,
            )

        return 0

    except TimeoutException as e:
        print(f"Timed out waiting for an element or page state: {e}", file=sys.stderr)
        try:
            driver.save_screenshot("add_candidate_automation_error.png")
            print("Screenshot: add_candidate_automation_error.png", file=sys.stderr)
        except WebDriverException:
            pass
        return 1
    except WebDriverException as e:
        print(f"WebDriver error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        try:
            driver.save_screenshot("add_candidate_automation_error.png")
        except WebDriverException:
            pass
        return 1
    finally:
        # Step 9: Always close the browser when it was started
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                pass
            print("Browser closed.")


if __name__ == "__main__":
    raise SystemExit(run())
