import os
import time
import pandas as pd
from datetime import datetime

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC

# Auto-install correct ChromeDriver
import chromedriver_autoinstaller


# ============================================================
#  FILE OUTPUT (root folder)
# ============================================================
OUTPUT_DIR = "."  # save directly to repo root


# ============================================================
#  DRIVER SETUP
# ============================================================
def get_driver():
    """Creates a GitHub-Actions-compatible Chrome driver."""
    chromedriver_autoinstaller.install()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    return webdriver.Chrome(options=options)


# ============================================================
#  LOGIN PROCESS
# ============================================================
def login(driver):
    wait = WebDriverWait(driver, 30)

    email_input = wait.until(
        EC.visibility_of_element_located((By.ID, "email"))
    )
    password_input = wait.until(
        EC.visibility_of_element_located((By.ID, "password"))
    )

    email_input.send_keys(os.getenv("STRIIVE_EMAIL"))
    password_input.send_keys(os.getenv("STRIIVE_PASSWORD"))

    login_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//form/button"))
    )
    login_button.click()

    # Wait until job inbox loads
    wait.until(
        EC.presence_of_element_located((By.TAG_NAME, "app-job-request-inbox"))
    )
    time.sleep(1)


def go_to_page(driver):
    url = "https://supplier.striive.com/inbox/all?searchTerm=data"
    driver.get(url)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "app-login"))
    )

    login(driver)
    return url


# ============================================================
#  SCRAPING HELPERS
# ============================================================
def safe_get_text(driver, xpath):
    """Returns element text or '' if not found."""
    try:
        return driver.find_element(By.XPATH, xpath).text
    except:
        return ""


def get_demands(driver):
    items = []
    for i in range(1, 25):
        txt = safe_get_text(driver, f"(//section[3]//ul)[1]/li[{i}]")
        if txt:
            items.append(txt)
    return items


def get_wishes(driver):
    items = []
    for i in range(1, 25):
        txt = safe_get_text(driver, f"(//section[3]//ul)[2]/li[{i}]//span/span")
        if txt:
            items.append(txt)
    return items


def extract_text(driver):
    return (
        safe_get_text(driver, "//section[4]/p")
        or safe_get_text(driver, "//section[5]/p")
    )


def extract_job(driver, uid):
    """Extracts structured job data."""
    return {
        "UID": uid,
        "referentie_code": safe_get_text(driver, '(//span[@class="field-value"])[7]'),
        "vacature": safe_get_text(driver, '//header//div/div[2]'),
        "plaats": safe_get_text(driver, '(//section[2]//span[@class="field-value"])[2]'),
        "uren": safe_get_text(driver, '(//section[2]//span[@class="field-value"])[1]'),
        "text": extract_text(driver),
        "start": "".join(c for c in safe_get_text(driver, '(//section[2]//span[@class="field-value"])[3]') if c.isdigit() or c == "-"),
        "eind": safe_get_text(driver, '(//span[@class="field-value"])[3]'),
        "deadline": "".join(c for c in safe_get_text(driver, '(//section[2]//span[@class="field-value"])[4]') if c.isdigit() or c == "-"),
        "eisen": get_demands(driver),
        "wensen": get_wishes(driver),
    }


# ============================================================
#  MAIN SCRAPER
# ============================================================
def main():
    output_file = os.path.join(
        OUTPUT_DIR,
        f"striive_{datetime.now().strftime('%Y-%m-%d')}.json"
    )

    rows = []
    uid = 0

    with get_driver() as driver:
        go_to_page(driver)
        wait = WebDriverWait(driver, 20)

        # Wait for list
        wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "app-job-request-list"))
        )

        # Scrape first 4 visible jobs
        for idx in range(1, 5):
            try:
                item = driver.find_element(By.XPATH, f"(//app-job-request-list-item)[{idx}]")
                driver.execute_script("arguments[0].scrollIntoView();", item)
                item.click()
                time.sleep(1)

                rows.append(extract_job(driver, uid))
                uid += 1
            except:
                continue

        # Scroll to next pages and scrape
        for _ in range(10):
            for idx in range(5, 10):
                try:
                    item = driver.find_element(By.XPATH, f"(//app-job-request-list-item)[{idx}]")
                    driver.execute_script("arguments[0].scrollIntoView();", item)
                    item.click()
                    time.sleep(1)

                    rows.append(extract_job(driver, uid))
                    uid += 1
                except:
                    continue

    # Build dataframe & ensure uniqueness
    df = pd.DataFrame(rows).drop_duplicates(subset=["referentie_code"])

    # Log file path
    abs_path = os.path.abspath(output_file)
    print(f"Saving JSON to: {abs_path}")

    # Save JSON
    df.to_json(output_file, orient="index", indent=4)

    # Check if file exists
    if os.path.exists(output_file):
        print("✔ File successfully created:", abs_path)
    else:
        print("❌ ERROR: File was NOT created:", abs_path)


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()
