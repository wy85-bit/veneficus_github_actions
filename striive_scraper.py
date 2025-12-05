import os
import time
from datetime import datetime
import pandas as pd

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Auto-install matching ChromeDriver
import chromedriver_autoinstaller


# ============================================================
# DRIVER SETUP
# ============================================================
def get_driver():
    """
    Creates a stable, GitHub-Actions-compatible Chrome driver.
    Automatically installs the right ChromeDriver version.
    """
    chromedriver_autoinstaller.install()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    return webdriver.Chrome(options=options)


# ============================================================
# LOGIN + NAVIGATION
# ============================================================
def login(driver):
    """Log into Striive with robust Angular-ready waits."""
    wait = WebDriverWait(driver, 30)

    email = wait.until(EC.visibility_of_element_located((By.ID, "email")))
    pw = wait.until(EC.visibility_of_element_located((By.ID, "password")))

    email.send_keys(os.getenv("STRIIVE_EMAIL"))
    pw.send_keys(os.getenv("STRIIVE_PASSWORD"))

    button = wait.until(EC.element_to_be_clickable((By.XPATH, "//form/button")))
    button.click()

    # Wait until the job inbox is visible
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "app-job-request-inbox")))
    time.sleep(1)


def go_to_page(driver):
    url = "https://supplier.striive.com/inbox/all?searchTerm=data"
    driver.get(url)

    # Wait until Angular login component loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "app-login"))
    )

    login(driver)
    return url


# ============================================================
# SCRAPING HELPERS
# ============================================================
def safe_get_text(driver, xpath):
    """Return text of an element or '' if not found."""
    try:
        return driver.find_element(By.XPATH, xpath).text
    except:
        return ""


def get_demands(driver):
    items = []
    for i in range(1, 21):
        try:
            txt = safe_get_text(driver, f'(//section[3]//ul)[1]/li[{i}]')
            if txt:
