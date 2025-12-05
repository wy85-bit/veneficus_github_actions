import json
import time
import random
import traceback
from datetime import datetime
import os

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ---------------------------------------------------------
# Configure Selenium with WebShare.io Proxy
# ---------------------------------------------------------
def get_driver():
    proxy = os.getenv("PROXY_URL")   # from GitHub Secrets
        
    options = Options()
    options.add_argument("--headless=new")  
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Proxy for Webshare
    if proxy:
        options.add_argument(f"--proxy-server={proxy}")
        print("🔌 Using proxy:", proxy)

    # Anti-detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    # Hide Selenium fingerprint
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


# ---------------------------------------------------------
# Debug HTML writer
# ---------------------------------------------------------
def save_debug(driver, name):
    try:
        with open(f"{name}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"📝 Saved debug HTML: {name}.html")
    except Exception as e:
        print("⚠️ Failed to write debug HTML:", str(e))


# ---------------------------------------------------------
# Scrape Indeed job cards
# ---------------------------------------------------------
def scrape(driver):
    jobs = []
    pages_scraped = 0
    pages_to_scrape = 5

    while pages_scraped < pages_to_scrape:
        time.sleep(random.uniform(3, 6))

        job_cards = driver.find_elements(By.CSS_SELECTOR, ".cardOutline")
        save_debug(driver, f"debug_page_{pages_scraped}")

        if not job_cards:
            print("⚠ No job cards found on this page.")
            return jobs

        for job_card in job_cards:
            job = {}

            try:
                driver.execute_script("arguments[0].scrollIntoView();", job_card)
                job_card.click()
            except:
                continue

            # Title
            try:
                title_el = WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".jobsearch-JobInfoHeader-title")
                    )
                )
                job["title"] = title_el.text
            except:
                continue

            # Job details container
            try:
                details = driver.find_element(By.CSS_SELECTOR, ".jobsearch-RightPane")
            except:
                continue

            # Extract fields
            try: job["company"] = details.find_element(
                    By.CSS_SELECTOR, "div[data-company-name='true']"
                ).text
            except: pass

            try: job["location"] = driver.find_element(By.ID, "jobLocationText").text
            except: pass

            try: job["pay"] = driver.find_element(
                    By.CSS_SELECTOR, "#salaryInfoAndJobType span"
                ).text
            except: pass

            try: job["description"] = details.find_element(
                    By.ID, "jobDescriptionText"
                ).text
            except: pass

            jobs.append(job)
            time.sleep(random.uniform(1, 2))

        # Next page
        try:
            next_btn = driver.find_element(
                By.CSS_SELECTOR, "a[data-testid='pagination-page-next']"
            )
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

    urls = [
        "https://nl.indeed.com/jobs?q=Data&fromage=3",
        "https://nl.indeed.com/jobs?q=machine+learning&fromage=3",
        "https://nl.indeed.com/jobs?q=data+analyst&fromage=3",
    ]

    all_jobs = []

    try:
        for i, url in enumerate(urls):
            print("🔎 Scraping:", url)
            driver.get(url)
            time.sleep(5)
            save_debug(driver, f"debug_loaded_{i}")

            jobs = scrape(driver)
            all_jobs.extend(jobs)

    except Exception as e:
        save_debug(driver, "debug_crash")
        print("❌ Error:", e)
        print(traceback.format_exc())
        raise

    finally:
        driver.quit()

    # Save JSON
    filename = f"indeed_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"jobs": all_jobs}, f, indent=4)

    print("📁 Saved:", filename)


if __name__ == "__main__":
    main()
