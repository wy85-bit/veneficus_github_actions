import json
import time
import random
import traceback
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ---------------------------------------------------------
# Anti-bot Chrome (GitHub Actions compatible)
# ---------------------------------------------------------
def get_driver():
    options = Options()

    # Best headless mode to avoid detection
    options.add_argument("--headless=new")

    # Anti-bot
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1920,1080")

    # Required in GitHub Actions
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    # Remove webdriver fingerprint
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


# ---------------------------------------------------------
# Write debug HTML ALWAYS
# ---------------------------------------------------------
import os

def save_debug(driver, name):
    path = os.path.join(os.getcwd(), f"{name}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"📝 Debug saved at {path}")


# ---------------------------------------------------------
# Scrape jobcards
# ---------------------------------------------------------
def scrape(driver):
    jobs = []
    pages_scraped = 0
    pages_to_scrape = 8

    while pages_scraped < pages_to_scrape:
        time.sleep(random.uniform(2, 5))

        job_cards = driver.find_elements(By.CSS_SELECTOR, ".cardOutline")
        save_debug(driver, f"debug_page_{pages_scraped}")  # always save

        if not job_cards:
            print("⚠ Geen jobcards gevonden → pagina geblokkeerd of layout anders")
            return jobs

        for job_card in job_cards:
            job = {}

            try:
                driver.execute_script("arguments[0].scrollIntoView();", job_card)
                job_card.click()
            except:
                continue

            try:
                title = WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".jobsearch-JobInfoHeader-title"))
                )
                job["title"] = title.text
            except:
                continue

            try:
                details = driver.find_element(By.CSS_SELECTOR, ".jobsearch-RightPane")
            except:
                continue

            try: job["company"] = details.find_element(By.CSS_SELECTOR, "div[data-company-name='true']").text
            except: pass

            try: job["location"] = driver.find_element(By.ID, "jobLocationText").text
            except: pass

            try: job["pay"] = driver.find_element(By.CSS_SELECTOR, "#salaryInfoAndJobType span").text
            except: pass

            try: job["description"] = details.find_element(By.ID, "jobDescriptionText").text
            except: pass

            jobs.append(job)

        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "a[data-testid='pagination-page-next']")
            next_btn.click()
        except NoSuchElementException:
            break

        pages_scraped += 1

    return jobs


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
def main():
    driver = get_driver()

    search_urls = [
        "https://nl.indeed.com/jobs?q=Data&l=Nederland&fromage=3",
        "https://nl.indeed.com/jobs?q=machine+learning+engineer&fromage=3",
        "https://nl.indeed.com/jobs?q=data+analyst&fromage=3",
    ]

    all_jobs = []

    try:
        for idx, url in enumerate(search_urls):
            print("🔎 Scraping:", url)
            driver.get(url)
            time.sleep(5)

            save_debug(driver, f"debug_loaded_{idx}")

            jobs = scrape(driver)
            all_jobs.extend(jobs)

        driver.quit()

    except Exception as e:
        print("❌ ERROR:", e)
        print(traceback.format_exc())
        save_debug(driver, "debug_crash")
        raise

    # Write JSON
    filename = f"indeed_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"jobs": all_jobs}, f, indent=4)

    print("📁 Saved:", filename)
