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
#  OUTPUT DIRECTORY (ALWAYS EXISTS)
# ============================================================
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
#  DRIVER SETUP
# ============================================================
def get_driver():
    """Configures a Chrome driver compatible with GitHub Actions."""
    chromedriver_autoinstaller.install()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    return driver


# ============================================================
#  LOGIN PROCESS
# ============================================================
def login(driver):
    wait = WebDriverWait(driver, 30)

    # Wait until login form is rendered by Angular
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

    # Wait for job inbox to appear
    wait.until(
        EC.presence_of_element_located((By.TAG_NAME, "app-job-request-inbox"))
    )
    time.sleep(1)


def go_to_page(driver):
    url = "https://supplier.striive.com/inbox/all?searchTerm=data"
    driver.get(url)

    # Wait until the Angular login component loads
    WebDriverWait(driver, 25).until(
        EC.presence_of_element_located((By.TAG_NAME, "app-login"))
    )

    login(driver)
    return url


# ============================================================
#  SCRAPING HELPERS
# ============================================================
def safe_get_text(driver, xpath):
    """Return text if found, otherwise empty string."""
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
    """Dynamic description location handling."""
    return (
        safe_get_text(driver, "//section[4]/p")
        or safe_get_text(driver, "//section[5]/p")
    )


def extract_job(driver, uid):
    """Collects all structured job data fields."""
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
        wait = WebDriverWait(driver, 15)

        # Wait for the job list
        wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "app-job-request-list"))
        )

        # Scrape visible list items
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

        # Scroll & scrape next lists
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

    # Convert to DataFrame
    df = pd.DataFrame(rows).drop_duplicates(subset=["referentie_code"])

    # DEBUG: Show save path
    print("Saving JSON to:", os.path.abspath(output_file))

    # Write file
    df.to_json(output_file, orient="index", indent=4)

    # Confirm file existence
    if os.path.exists(output_file):
        print("✔ FILE EXISTS:", os.path.abspath(output_file))
    else:
        print("❌ ERROR: File not created:", os.path.abspath(output_file))


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()
