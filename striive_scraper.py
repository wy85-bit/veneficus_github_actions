import os
import time
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller


# ============================================================
#  DRIVER SETUP
# ============================================================
def get_driver():
    # installs the correct chromedriver automatically
    chromedriver_autoinstaller.install()

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)
    return driver


# ============================================================
#  LOGIN + NAVIGATION
# ============================================================
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def login(driver):
    wait = WebDriverWait(driver, 20)

    # Wait until the login form is rendered
    email = wait.until(EC.visibility_of_element_located((By.ID, "email")))
    pw = wait.until(EC.visibility_of_element_located((By.ID, "password")))

    email.send_keys(os.getenv("STRIIVE_EMAIL"))
    pw.send_keys(os.getenv("STRIIVE_PASSWORD"))

    # Wait for login button
    login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//form/button')))
    login_btn.click()

    # Wait for inbox to load
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "app-job-request-inbox")))
    time.sleep(1)
    

def go_to_page(driver):
    url = "https://supplier.striive.com/inbox/all?searchTerm=data"
    driver.get(url)

    # Wait for Angular to bootstrap
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "app-login"))
    )

    login(driver)
    return url


# ============================================================
#  SCRAPING HELPERS
# ============================================================
def get_demands(driver):
    results = []
    for i in range(1, 21):
        try:
            text = driver.find_element(
                By.XPATH,
                f'//section[3]//div/ul/li[{i}]'
            ).text
            results.append(text)
        except:
            continue
    return results


def get_wishes(driver):
    results = []
    for i in range(1, 21):
        try:
            text = driver.find_element(
                By.XPATH,
                f'//section[3]/div[2]/ul/li[{i}]//span/span'
            ).text
            results.append(text)
        except:
            continue
    return results


def extract_job(driver, uid, text):
    """Extract all job fields into a row dictionary."""

    return {
        "UID": uid,
        "referentie_code": driver.find_element(By.XPATH, '//*/div/div[9]/span[2]').text,
        "vacature": driver.find_element(By.XPATH, '//header//div[2]').text,
        "plaats": driver.find_element(By.XPATH, '//section[2]/div[1]/div[2]/span[2]').text,
        "uren": driver.find_element(By.XPATH, '//section[2]/div[1]/div[1]/span[2]').text,
        "text": text,
        "start": "".join(c for c in driver.find_element(By.XPATH, '//section[2]/div[2]/div[1]/span[2]').text if c.isdigit() or c == "-"),
        "eind": driver.find_element(By.XPATH, '//*/div/div[3]/span[2]').text,
        "deadline": "".join(c for c in driver.find_element(By.XPATH, '//section[2]/div[2]/div[2]/span[2]').text if c.isdigit() or c == "-"),
        "eisen": get_demands(driver),
        "wensen": get_wishes(driver),
    }


# ============================================================
#  MAIN SCRAPER
# ============================================================
def main():
    output_file = f"striive_{datetime.now().strftime('%Y-%m-%d')}.json"
    rows = []
    uid = 0

    with get_driver() as driver:
        go_to_page(driver)
        time.sleep(2)

        # First block (items 1–4)
        for j in range(1, 5):
            try:
                element = driver.find_element(By.XPATH, f'//app-job-request-list-item[{j}]')
                driver.execute_script("arguments[0].scrollIntoView();", element)
                element.click()
                time.sleep(2)

                text = extract_text(driver)
                rows.append(extract_job(driver, uid, text))
                uid += 1

            except:
                continue

        # Second block (items 5–9, repeated scrolling)
        for _ in range(9):
            for j in range(5, 10):
                try:
                    element = driver.find_element(By.XPATH, f'//app-job-request-list-item[{j}]')
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    element.click()
                    time.sleep(2)

                    text = extract_text(driver)
                    rows.append(extract_job(driver, uid, text))
                    uid += 1

                except:
                    continue

    # Save output
    df = pd.DataFrame(rows).drop_duplicates(subset=["referentie_code"])
    df.to_json(output_file, orient="index", indent=4)
    print(f"Saved JSON → {output_file}")


def extract_text(driver):
    """Handles inconsistent description field."""
    try:
        return driver.find_element(By.XPATH, '//section[4]/p').text
    except:
        return driver.find_element(By.XPATH, '//section[5]/p').text


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()
