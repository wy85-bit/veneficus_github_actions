import time
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


load_dotenv()

MAGNIT_EMAIL = os.getenv("MAGNIT_EMAIL")
MAGNIT_PASSWORD = os.getenv("MAGNIT_PASSWORD")

OUTPUT_FILE = f"magnit_global_{datetime.now().strftime('%Y-%m-%d')}.json"


# ----------------------------------------
# Driver setup (compatible with GitHub Actions)
# ----------------------------------------
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver


# ----------------------------------------
# Core scraping logic
# ----------------------------------------
def go_to_main_page(driver):
    driver.get("https://portal.magnitglobal.com/supplier/jobrequests/new")
    time.sleep(4)


def scrape(driver, results):
    for i in range(1, 50):
        try:
            row_xpath = f'//*[@id="jobrequestTable"]/div/div/datatable-body/datatable-scroller/div/datatable-row-wrapper[{i}]'
            row_element = driver.find_element(By.XPATH, row_xpath)
            driver.execute_script("arguments[0].scrollIntoView();", row_element)
            row_element.click()
            time.sleep(2)

            # Extract fields
            UID = driver.find_element(By.XPATH, f'{row_xpath}/datatable-body-row/div/datatable-body-cell[1]/div/span').text
            title = driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[2]/h3').text

            start_date = "".join([
                driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[2]/div/div[2]/app-period/div/div[2]/div[1]/div[1]').text,
                driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[2]/div/div[2]/app-period/div/div[2]/div[1]/div[2]').text,
                driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[2]/div/div[2]/app-period/div/div[2]/div[1]/div[3]').text
            ])

            end_date = "".join([
                driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[2]/div/div[2]/app-period/div/div[2]/div[2]/div[1]').text,
                driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[2]/div/div[2]/app-period/div/div[2]/div[2]/div[2]').text,
                driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[2]/div/div[2]/app-period/div/div[2]/div[2]/div[3]').text
            ])

            hours = driver.find_element(By.XPATH, '//app-icon-label/div/div[2]/div[2]/span').text
            deadline_application = driver.find_element(By.XPATH, '(//app-icon-label/div/div[2]/div[2]/span)[2]').text
            experience = driver.find_element(By.XPATH, '(//app-icon-label/div/div[2]/div[2]/span)[4]').text
            max_hourly_pay = driver.find_element(By.XPATH, '(//app-icon-label/div/div[2]/div[2]/span)[3]').text
            location = driver.find_element(By.XPATH, '(//app-icon-label/div/div[2]/div[2]/span)[1]').text

            vacancy_text = driver.find_element(By.XPATH, '//*[@id="list-nieuw-item-1"]/div[3]/div[1]/pre').text

            results.append({
                "UID": UID,
                "titel": title,
                "start datum": start_date,
                "eind datum": end_date,
                "deadline aanvraag": deadline_application,
                "locatie": location,
                "uren per week": hours,
                "ervaring in jaren": experience,
                "max uur tarief": max_hourly_pay,
                "vacature tekst": vacancy_text
            })

        except:
            continue

    return results


# ----------------------------------------
# Main
# ----------------------------------------
def main():
    driver = get_driver()

    go_to_main_page(driver)

    # Login
    driver.find_element(By.ID, 'signInName').send_keys(MAGNIT_EMAIL)
    driver.find_element(By.XPATH, '//input[@type="password"]').send_keys(MAGNIT_PASSWORD)
    driver.find_element(By.ID, 'continue').click()
    time.sleep(8)

    # Click through to jobs
    driver.find_element(By.XPATH, "//app-user-button/a").click()
    time.sleep(1)
    driver.find_element(By.XPATH, "//app-user-identity[1]/a").click()
    time.sleep(5)

    driver.find_element(By.XPATH, "//app-job-requests-dashboard-widget//a").click()
    time.sleep(8)

    results = scrape(driver, [])

    # Switch to second section
    driver.find_element(By.XPATH, "//app-user-button/a").click()
    time.sleep(1)
    driver.find_element(By.XPATH, "//app-user-identity[2]/a").click()
    time.sleep(5)
    driver.find_element(By.XPATH, "//app-job-requests-dashboard-widget//a[1]").click()
    time.sleep(5)

    results = scrape(driver, results)

    driver.quit()

    df = pd.DataFrame(results).drop_duplicates("UID").set_index("UID")
    df.to_json(OUTPUT_FILE, indent=4)

    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
