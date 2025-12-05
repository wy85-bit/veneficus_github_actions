import json
import time
import random
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# DEBUG: sla volledige pagina op zodat we kunnen zien wat Indeed teruggeeft
def save_debug_page(driver, label="debug"):
    html = driver.page_source
    with open(f"{label}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"🔍 Saved {label}.html for inspection")

    
# ---------------------------------------------------------
# Create Chrome with Anti-Bot Bypass (GitHub Actions SAFE)
# ---------------------------------------------------------
def get_driver():
    options = Options()

    # Normal headless mode triggers bot detection → use new headless mode
    options.add_argument("--headless=new")

    # Anti-bot fingerprints
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Realistic viewport
    options.add_argument("--window-size=1920,1080")

    # Required in GitHub Actions
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    # Remove Selenium fingerprints
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


# ---------------------------------------------------------
# Scrape results for 1 search query
# ---------------------------------------------------------
def scrape(driver):
    jobs = []
    pages_scraped = 0
    pages_to_scrape = 10  # safe limit for GitHub Actions

    while pages_scraped < pages_to_scrape:

        time.sleep(random.uniform(2, 5))

        job_cards = driver.find_elements(By.CSS_SELECTOR, ".cardOutline")

        if not job_cards:
            print("⚠ No job cards on this page → saving debug page...")
            html = driver.page_source
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            return jobs

        for job_card in job_cards:
            job = {
                "title": None,
                "company": None,
                "rating": None,
                "location": None,
                "pay": None,
                "description": None,
                "types": [],
            }

            driver.execute_script("arguments[0].scrollIntoView();", job_card)
            time.sleep(0.5)

            try:
                job_card.click()
            except:
                continue

            # ---- Title ----
            try:
                title_el = WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".jobsearch-JobInfoHeader-title")
                    )
                )
                job["title"] = title_el.text.strip()
            except:
                continue

            # ---- Details container ----
            try:
                details = driver.find_element(By.CSS_SELECTOR, ".jobsearch-RightPane")
            except:
                continue

            # ---- Company name ----
            try:
                job["company"] = details.find_element(
                    By.CSS_SELECTOR, "div[data-company-name='true']"
                ).text
            except:
                pass

            # ---- Rating ----
            try:
                job["rating"] = details.find_element(
                    By.XPATH, "//span[contains(@class,'css')]"
                ).text
            except:
                pass

            # ---- Location ----
            try:
                job["location"] = driver.find_element(By.ID, "jobLocationText").text
            except:
                pass

            # ---- Pay ----
            try:
                job["pay"] = driver.find_element(
                    By.CSS_SELECTOR, "#salaryInfoAndJobType span"
                ).text
            except:
                pass

            # ---- Description ----
            try:
                job["description"] = details.find_element(
                    By.ID, "jobDescriptionText"
                ).text
            except:
                pass

            # ---- Job types ----
            for i in range(1, 5):
                try:
                    t = driver.find_element(
                        By.XPATH,
                        f'//*[@id="jobDetailsSection"]/div/div[1]/div[2]/div[2]/div/div/ul/li[{i}]/button/div/div/div/span'
                    ).text
                    job["types"].append(t)
                except:
                    break

            jobs.append(job)

            time.sleep(random.uniform(1, 2))

        # ---- Next page ----
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

    search_urls = {
        "data": "https://nl.indeed.com/jobs?q=Data&l=Nederland&fromage=3",
        "machine_learning": "https://nl.indeed.com/jobs?q=machine+learning+engineer&fromage=3",
        "data_analyst": "https://nl.indeed.com/jobs?q=data+analyst&fromage=3",
    }

    all_jobs = []

    for name, url in search_urls.items():
        print(f"🔎 Scraping: {name} → {url}")
        driver.get(url)
        time.sleep(4)
        save_debug_page(driver, "loaded_page")
        jobs = scrape(driver)
        all_jobs.extend(jobs)

    driver.quit()

    output = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "jobs": all_jobs,
    }

    filename = f"indeed_{datetime.now().strftime('%Y-%m-%d')}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print("📁 Saved:", filename)


if __name__ == "__main__":
    main()
