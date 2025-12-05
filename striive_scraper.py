import os
import time
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller


# ============================================================
# Save output in repository root
# ============================================================
OUTPUT_DIR = "."


# ============================================================
# Chrome driver setup
# ============================================================
def get_driver():
    chromedriver_autoinstaller.install()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    return webdriver.Chrome(options=options)


# ============================================================
# Login sequence
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

    login_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//form/button"))
    )
    login_btn.click()

    wait.until(
        EC.presence_of_element_located((By.TAG_NAME, "app-job-request-inbox"))
    )
    time.sleep(1)


def go_to_page(driver):
    url = "https://supplier.striive.com/inbox/all"
    driver.get(url)

    WebDriverWait(driver, 25).until(
        EC.presence_of_element_located((By.TAG_NAME, "app-login"))
    )

    login(driver)
    return url


# ============================================================
# Helpers
# ============================================================
def safe_text(el):
    return el.text.strip() if el else ""


def extract_job(driver, uid):
    """Extract structured job data from the details panel."""

    def t(xpath):
        try:
            return driver.find_element(By.XPATH, xpath).text.strip()
        except:
            return ""

    return {
        "UID": uid,
        "referentie_code": t('(//span[@class="field-value"])[7]'),
        "vacature": t('//header//div/div[2]'),
        "plaats": t('(//section[2]//span[@class="field-value"])[2]'),
        "uren": t('(//section[2]//span[@class="field-value"])[1]'),
        "text": t('//section[4]/p') or t('//section[5]/p'),
        "start": "".join(c for c in t('(//section[2]//span[@class="field-value"])[3]') if c.isdigit() or c == "-"),
        "eind": t('(//span[@class="field-value"])[3]'),
        "deadline": "".join(c for c in t('(//section[2]//span[@class="field-value"])[4]') if c.isdigit() or c == "-"),
        "eisen": extract_list(driver, "(//section[3]//ul)[1]/li"),
        "wensen": extract_list(driver, "(//section[3]//ul)[2]/li//span/span"),
    }


def extract_list(driver, base_xpath):
    items = []
    for i in range(1, 30):
        try:
            txt = driver.find_element(By.XPATH, f"{base_xpath}[{i}]").text.strip()
            if txt:
                items.append(txt)
        except:
            break
    return items


# ============================================================
# Infinite scroll logic for job list
# ============================================================
def load_all_job_items(driver):
    """Scrolls until ALL jobs are loaded, returns list of elements."""

    wait = WebDriverWait(driver, 20)

    # Locate the scroll container
    scroller = wait.until(
        EC.presence_of_element_located((
            By.CSS_SELECTOR, "app-job-request-list div.p-scroller"
        ))
    )

    previous_count = -1

    while True:
        items = driver.find_elements(By.CSS_SELECTOR, "app-job-request-list-item")
        count = len(items)

        if count == previous_count:
            # No more new items loaded
            break

        previous_count = count

        # Scroll to bottom of the container
        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight;",
            scroller
        )
        time.sleep(1)

    return driver.find_elements(By.CSS_SELECTOR, "app-job-request-list-item")


# ============================================================
# Main scraper
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

        wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "app-job-request-list"))
        )

        print("📌 Loading all jobs via infinite scroll...")
        job_items = load_all_job_items(driver)

        print(f"📌 Total jobs loaded: {len(job_items)}")

        for item in job_items:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", item)
                item.click()
                time.sleep(1)

                row = extract_job(driver, uid)
                rows.append(row)
                uid += 1

            except Exception as e:
                print("Error scraping job:", e)
                continue

    # Build dataframe and remove duplicates by reference code
    df = pd.DataFrame(rows).drop_duplicates(subset=["referentie_code"])

    absfile = os.path.abspath(output_file)
    print("💾 Saving JSON to:", absfile)

    df.to_json(output_file, orient="index", indent=4)

    if os.path.exists(output_file):
        print("✅ File successfully created:", absfile)
    else:
        print("❌ ERROR: file not created:", absfile)


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    main()
