"""
Log in to Recruiterflow, open Add candidate, and fill the candidate form.

Run (with the app up and venv active):

    python add_candidate_automation.py

Uses the same login settings as login_recruiterflow.py (local_settings.py).
Candidate field values also live in local_settings.py.

The UI often hides "Add candidate" inside a menu, so this script first tries to
click a visible link to /prospect/add (or /candidates/add). If none is found, it
opens /prospect/add directly (same page the menu item goes to).
"""

import sys
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from login_recruiterflow import (
    WAIT_SECONDS,
    LoginFailedError,
    build_driver,
    get_base_url,
    perform_login,
)

# New-table users land on /candidates; the add form can take a while to load and the
# splash loader (#rf-initial-page-loader) must disappear before inputs exist in the DOM.
ADD_FORM_WAIT = 60
ROOT_READY_WAIT = 90

try:
    from local_settings import (
        CANDIDATE_EDUCATION_DEGREE,
        CANDIDATE_EDUCATION_SCHOOL,
        CANDIDATE_EMAIL,
        CANDIDATE_EXPERIENCE_COMPANY,
        CANDIDATE_EXPERIENCE_TITLE,
        CANDIDATE_FIRST_NAME,
        CANDIDATE_LAST_NAME,
        CANDIDATE_LOCATION,
        CANDIDATE_PHONE,
    )
except ImportError as e:
    raise SystemExit(
        "Missing candidate fields in local_settings.py. "
        "Copy them from local_settings.example.py into local_settings.py. "
        f"Original error: {e}"
    ) from e

# --- Add candidate form: XPath locators (Recruiterflow prospect / add-candidate form) ---
# Each line is the XPath string; below we wrap them as (By.XPATH, ...) for Selenium.
FIRST_NAME_XPATH = "//input[@id='rf-application-form-first-name']"
# Same field via its wrapper (useful if id changes): //div[contains(@class,'email-input-wrapper')]//input[contains(@class,'full-first-name-input')]
#//*[@id="main-content-wrapper-id"]/div/div[1]/div/div/div[1]/div/div[1]/ul/li[1]/div/div[1]/input
LAST_NAME_XPATH = "//input[@id='rf-application-form-last-name']"
# Wrapper variant: //div[contains(@class,'password-login-container')]//input[@id='rf-application-form-last-name']

EMAIL_XPATH = "//input[@id='rf-application-form-email']"

# First tel input named user-phone (intl-tel); index [1] if the page has several.
PHONE_XPATH_FIRST = "(//input[@name='user-phone' and @type='tel'])[1]"

LOCATION_XPATH = (
    "//input[contains(@class,'location-search-input')]"
    "[not(contains(@style,'display: none'))]"
)
# Parent wrapper: //div[contains(@class,'location-input-wrapper')]//input[contains(@class,'location-search-input')]

EXPERIENCE_COMPANY_XPATH = "//input[@id='rf-application-form-company']"
EXPERIENCE_TITLE_XPATH = "//input[@id='rf-application-form-title']"
# Experience block: //div[contains(@class,'experience-input-wrapper')]//input[@id='rf-application-form-company']

EDUCATION_SCHOOL_XPATH = "//input[@id='rf-application-form-school']"
EDUCATION_DEGREE_XPATH = "//input[@id='rf-application-form-degree']"
# Education block: //div[contains(@class,'education-input-wrapper')]//input[@id='rf-application-form-school']

# Locator tuples used by WebDriverWait / find_element
FIRST_NAME = (By.XPATH, FIRST_NAME_XPATH)
LAST_NAME = (By.XPATH, LAST_NAME_XPATH)
EMAIL = (By.XPATH, EMAIL_XPATH)
PHONE = (By.XPATH, PHONE_XPATH_FIRST)
LOCATION = (By.XPATH, LOCATION_XPATH)
EXPERIENCE_COMPANY = (By.XPATH, EXPERIENCE_COMPANY_XPATH)
EXPERIENCE_TITLE = (By.XPATH, EXPERIENCE_TITLE_XPATH)
EDUCATION_SCHOOL = (By.XPATH, EDUCATION_SCHOOL_XPATH)
EDUCATION_DEGREE = (By.XPATH, EDUCATION_DEGREE_XPATH)


def _select_all_key():
    """Cmd+A on macOS, Ctrl+A elsewhere (matches browser select-all)."""
    return Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL


def scroll_and_focus(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.15)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)
    time.sleep(0.1)


def react_fill_text_input(driver, element, text):
    """
    Fill a React-controlled <input> so the UI state updates (clear/send_keys alone often fails).
    Uses the native value setter + input/change events.
    """
    scroll_and_focus(driver, element)
    driver.execute_script(
        """
        const el = arguments[0];
        const val = arguments[1];
        const proto = el instanceof HTMLTextAreaElement
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype;
        const desc = Object.getOwnPropertyDescriptor(proto, 'value');
        if (desc && desc.set) {
            desc.set.call(el, val);
        } else {
            el.value = val;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        str(text),
    )


def fill_phone_field(driver, element, phone):
    """Phone uses intl-tel-input when present; otherwise same as React input."""
    scroll_and_focus(driver, element)
    raw = str(phone).strip()
    if raw.startswith("+"):
        e164 = raw
    elif len(raw) == 10 and raw.isdigit():
        e164 = "+1" + raw
    else:
        e164 = "+" + raw.lstrip("+")

    driver.execute_script(
        """
        const el = arguments[0];
        const e164 = arguments[1];
        el.focus();
        if (window.intlTelInputGlobals) {
            const iti = window.intlTelInputGlobals.getInstance(el);
            if (iti) {
                iti.setNumber(e164);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
        const proto = window.HTMLInputElement.prototype;
        const desc = Object.getOwnPropertyDescriptor(proto, 'value');
        const national = e164.replace(/^\\+1/, '');
        if (desc && desc.set) desc.set.call(el, national);
        else el.value = national;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        e164,
    )


def wait_for_root_app(driver, timeout=ROOT_READY_WAIT):
    """Wait until React has mounted something under #root."""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(
            "const r=document.getElementById('root'); return !!(r && r.children && r.children.length);"
        )
    )


def dismiss_rf_splash_loader(driver):
    """Hide the full-page loader if it is still covering the app (safe for local automation)."""
    driver.execute_script(
        """
        var el = document.getElementById('rf-initial-page-loader');
        if (el) { el.style.display = 'none'; el.style.visibility = 'hidden'; }
        try { window.postMessage('recruiterflow-react-loaded', '*'); } catch (e) {}
        """
    )


def wait_for_add_form(driver, timeout=ADD_FORM_WAIT):
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located(FIRST_NAME))


def try_click_add_candidate_link(driver):
    """Click a visible Add-candidate link if one exists (same targets as the header menu)."""
    for xp in (
        "//a[contains(@href,'/prospect/add')]",
        "//a[contains(@href,'/candidates/add')]",
    ):
        for el in driver.find_elements(By.XPATH, xp):
            try:
                if el.is_displayed() and el.is_enabled():
                    el.click()
                    print("Clicked an 'Add candidate' link in the UI.")
                    return True
            except Exception:
                continue
    return False


def try_click_add_candidate_menu_text(driver):
    """Try visible menu rows / buttons labeled Add candidate (quick-add menu)."""
    xpaths = (
        "//a[normalize-space()='Add candidate']",
        "//span[normalize-space()='Add candidate']/ancestor::a",
        "//span[normalize-space()='Add candidate']/ancestor::button",
        "//button[contains(normalize-space(.),'Add candidate')]",
        "//*[@role='menuitem'][contains(.,'Add candidate')]",
    )
    for xp in xpaths:
        for el in driver.find_elements(By.XPATH, xp):
            try:
                if el.is_displayed() and el.is_enabled():
                    el.click()
                    print("Clicked an 'Add candidate' control in the page.")
                    return True
            except Exception:
                continue
    return False


def open_add_candidate_form(driver, wait):
    """Ensure the add-candidate form is open (click link or go to URL)."""
    wait_for_root_app(driver)
    time.sleep(1)
    dismiss_rf_splash_loader(driver)

    if try_click_add_candidate_link(driver):
        wait_for_root_app(driver, timeout=45)
        dismiss_rf_splash_loader(driver)
        wait_for_add_form(driver)
        return

    base = get_base_url().rstrip("/")
    # If you already use the new candidates grid, try its add URL first.
    on_new_table = "/candidates" in (driver.current_url or "")
    paths = (
        ("/candidates/add", "/prospect/add") if on_new_table else ("/prospect/add", "/candidates/add")
    )

    last_err = None
    for path in paths:
        url = base + path
        print(f"Opening add-candidate page: {url}")
        driver.get(url)
        wait_for_root_app(driver, timeout=45)
        time.sleep(1.5)
        dismiss_rf_splash_loader(driver)
        try:
            wait_for_add_form(driver, timeout=ADD_FORM_WAIT)
            print("Add-candidate form is ready.")
            return
        except TimeoutException as e:
            last_err = e
            continue

    # Last resort: stay on grid and try to open Add candidate from the UI text / menu.
    print("Trying Add candidate from visible controls…")
    driver.get(base + "/candidates")
    wait_for_root_app(driver, timeout=45)
    dismiss_rf_splash_loader(driver)
    time.sleep(1)
    if try_click_add_candidate_menu_text(driver) or try_click_add_candidate_link(driver):
        wait_for_root_app(driver, timeout=45)
        dismiss_rf_splash_loader(driver)
        try:
            wait_for_add_form(driver, timeout=ADD_FORM_WAIT)
            return
        except TimeoutException as e:
            last_err = e

    raise TimeoutException(
        "Could not find the first-name field after opening the add-candidate flow. "
        f"Expected XPath: {FIRST_NAME_XPATH!r}. "
        "Update FIRST_NAME_XPATH in add_candidate_automation.py if the DOM changed. "
        f"Last URL: {driver.current_url!r}"
    ) from last_err


def fill_location(driver, wait, text):
    """
    Location is often a search box with suggestions — real keystrokes work best for the dropdown.
    """
    el = wait.until(EC.element_to_be_clickable(LOCATION))
    scroll_and_focus(driver, el)
    el.send_keys(_select_all_key(), "a")
    el.send_keys(Keys.BACKSPACE)
    el.send_keys(str(text))
    time.sleep(1.2)
    try:
        el.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
    except Exception:
        pass


def fill_candidate_form(driver, wait):
    """
    Fill each field using XPath locators above; values come from local_settings.py
    (CANDIDATE_FIRST_NAME, CANDIDATE_LAST_NAME, …).
    """
    fn = wait.until(EC.element_to_be_clickable(FIRST_NAME))
    react_fill_text_input(driver, fn, CANDIDATE_FIRST_NAME)
    print("Filled first name.")
    time.sleep(0.25)

    react_fill_text_input(driver, driver.find_element(*LAST_NAME), CANDIDATE_LAST_NAME)
    print("Filled last name.")
    time.sleep(0.25)

    react_fill_text_input(driver, driver.find_element(*EMAIL), CANDIDATE_EMAIL)
    print("Filled email.")
    time.sleep(0.25)

    fill_phone_field(driver, wait.until(EC.element_to_be_clickable(PHONE)), CANDIDATE_PHONE)
    print("Filled phone.")
    time.sleep(0.25)

    fill_location(driver, wait, CANDIDATE_LOCATION)
    print("Filled location.")
    time.sleep(0.25)

    react_fill_text_input(driver, wait.until(EC.element_to_be_clickable(EXPERIENCE_COMPANY)), CANDIDATE_EXPERIENCE_COMPANY)
    if CANDIDATE_EXPERIENCE_TITLE:
        react_fill_text_input(driver, driver.find_element(*EXPERIENCE_TITLE), CANDIDATE_EXPERIENCE_TITLE)
    print("Filled experience (company / title fields).")
    time.sleep(0.25)

    react_fill_text_input(driver, wait.until(EC.element_to_be_clickable(EDUCATION_SCHOOL)), CANDIDATE_EDUCATION_SCHOOL)
    if CANDIDATE_EDUCATION_DEGREE:
        react_fill_text_input(driver, driver.find_element(*EDUCATION_DEGREE), CANDIDATE_EDUCATION_DEGREE)
    print("Filled education (school / degree fields).")


def main():
    driver = build_driver()
    wait = WebDriverWait(driver, WAIT_SECONDS)

    try:
        perform_login(driver, wait)
        open_add_candidate_form(driver, wait)
        fill_candidate_form(driver, wait)
        print("Candidate form filled (review in the browser before saving).")
        input("Press Enter in this terminal to close the browser...")
    except LoginFailedError as e:
        path = "login_failed.png"
        driver.save_screenshot(path)
        print(f"{e}\nScreenshot saved: {path}")
        raise
    except TimeoutException:
        path = "add_candidate_error.png"
        driver.save_screenshot(path)
        print(
            f"Timed out. Screenshot saved: {path}\n"
            "If fields moved, inspect the page and update locators in add_candidate_automation.py."
        )
        raise
    finally:
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    main()
