from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time
import pandas as pd
import json
import os

def get(url, driver):
    driver.get(url)
    time.sleep(1)

def go_to(driver, term):
    get(f"https://www.circle8.nl/zoeken?query={term}", driver)

def list_vacancy_links(driver):
    elements = driver.find_elements(By.XPATH, '//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]')
    return [e.get_attribute("href") for e in elements]

def list_pagination_links(driver):
    elements = driver.find_elements(By.XPATH, '//div[@class="c-lister-pagination__wrapper"]//a')
    return [e.get_attribute("href") for e in elements]

def scrape(driver):
    rows = []

    pages = list_pagination_links(driver)
    if not pages:
        pages = [driver.current_url]

    for page in pages:
        get(page, driver)

        vacancies = list_vacancy_links(driver)
        for vacancy in vacancies:
            get(vacancy, driver)

            UID = driver.find_element(By.XPATH, '//p[@class="c-vacancy-hero__jobId detail"]').text

            main_info = [
                e.text for e in driver.find_elements(
                    By.XPATH,
                    '//div[@class="c-vacancy-hero__usp-container"]/div/div[count(@*)=0]'
                )
            ]
            plaats, duur, uren, start, deadline = main_info[:5]

            vacature_text = driver.find_element(
                By.CSS_SELECTOR,
                'div.c-vacancy-paragraph__body-text.body-text > div:nth-child(1)'
            ).text

            eisen = [e.text for e in driver.find_elements(By.XPATH, '//div[h3[text()="Eisen:"]]/ul//li')]
            wensen = [e.text for e in driver.find_elements(By.XPATH, '//div[h3[text()="Wensen:"]]/ul//li')]
            competenties = [e.text for e in driver.find_elements(By.XPATH, '//div[h3[text()="Competenties:"]]/ul//li')]

            title = driver.find_element(By.XPATH, '//h1').text

            rows.append({
                "UID": UID,
                "titel": title,
                "plaats": plaats,
                "duur": duur,
                "uren": uren,
                "text": vacature_text,
                "start": "".join(c for c in start if c.isdigit() or c == '-'),
                "deadline": "".join(c for c in deadline if c.isdigit() or c == '-'),
                "eisen": eisen,
                "wensen": wensen,
                "competenties": competenties
            })

    df = pd.DataFrame(rows).set_index("UID")
    return df

def main():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    with driver:
        go_to(driver, "data")
        df_data = scrape(driver)

        go_to(driver, "data engineer")
        df_data_engineer = scrape(driver)

        go_to(driver, "machine learning engineer")
        df_ml_engineer = scrape(driver)

    # Combine datasets
    df = pd.concat([df_data, df_data_engineer, df_ml_engineer])

    # Duplicates verwijderen
    df = df[~df.index.duplicated(keep="first")]

    # JSON opslaan
    df.to_json("circle8.json", orient="index", indent=4)

    print("JSON opgeslagen als circle8.json")

if __name__ == "__main__":
    main()
