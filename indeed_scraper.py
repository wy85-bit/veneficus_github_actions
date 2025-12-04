import json
import time
import random
import pandas as pd
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ---------------------------------------------------------
# GitHub Actions Compatible Chrome Driver
# ---------------------------------------------------------
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver


# ---------------------------------------------------------
# Scraper Logic
# ---------------------------------------------------------
def scrape(driver):
    jobs = []
    pages_scraped = 0
    pages_to_scrape = 20  # reduce for GitHub Actions stability

    while pages_scraped < pages_to_scrape:

        time.sleep(random.uniform(1, 3))

        try:
            job_cards = driver.find_elements(By.CSS_SELECTOR, ".cardOutline")
        except:
            job_cards = []

        for job_card in job_cards:
            job = {
                "title": None,
                "company_name": None,
                "company_rating": None,
                "location": None,
                "apply_link": None,
                "pay": None,
                "job_type": None,
                "description": None
            }

            driver.execute_script("arguments[0].scrollIntoView();", job_card)
            time.sleep(0.5)

            # ---- Load job details ----
            try:
                job_card.click()
            except:
                continue

            try:
                title_el = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".jobsearch-JobInfoHeader-title"))
                )
                job["title"] = title_el.text
            except:
                continue

            # Extract details
            try:
                details = driver.find_element(By.CSS_SELECTOR, ".jobsearch-RightPane")
            except:
                continue

            try:
                job["company_name"] = details.find_element(
                    By.CSS_SELECTOR,
                    "div[data-company-name='true']"
                ).text
            except:
                pass

            try:
                rating = details.find_element(
                    By.XPATH,
                    "//span[contains(@class,'css')]"
                ).text
                job["company_rating"] = rating
            except:
                pass

            try:
                job["location"] = driver.find_element(By.ID, "jobLocationText").text
            except:
                pass

            try:
                job["pay"] = driver.find_element(By.CSS_SELECTOR, "#salaryInfoAndJobType span").text
            except:
                pass

            try:
                job["description"] = driver.find_element(By.ID, "jobDescriptionText").text
            except:
                pass

            jobs.append(job)
            time.sleep(random.uniform(1, 2))

        # ---- Go to next page ----
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a[data-testid=pagination-page-next]")
            next_button.click()
        except NoSuchElementException:
            break

        pages_scraped += 1

    return jobs


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
def main():
    driver = get_driver()

    results = []

    searches = [
        "https://nl.indeed.com/jobs?q=Data&l=Nederland&fromage=3",
        "https://nl.indeed.com/jobs?q=machine+learning+engineer&fromage=3",
        "https://nl.indeed.com/jobs?q=data+analyst&fromage=3"
    ]

    for url in searches:
        print("Scraping:", url)
        driver.get(url)
        time.sleep(3)
        results.extend(scrape(driver))

    driver.quit()

    output = {
        "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "jobs": results
    }

    filename = f"indeed_{datetime.now().strftime('%Y-%m-%d')}.json"

    with open(filename, "w") as f:
        json.dump(output, f, indent=4)

    print("Saved:", filename)


if __name__ == "__main__":
    main()
