from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import os
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
import json

load_dotenv()

def go_to_main_page_search_term_data(driver):
    driver.get('https://www.circle8.nl/zoeken?query=data')
    time.sleep(5)
    
def go_to_main_page_search_term_data_engineer(driver):
    driver.get('https://www.circle8.nl/zoeken?query=data%20engineer')
    time.sleep(5)
    
def go_to_main_page_search_term_data_machine_learning_engineer(driver):
    driver.get('https://www.circle8.nl/zoeken?query=machine%20learning%20engineer')
    time.sleep(5)
    
def list_vacancy_links(driver):
    elements = driver.find_elements(By.XPATH, '//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]')
    links = [element.get_attribute("href") for element in elements]
    return links

def list_pagination_links(driver):
    elements = driver.find_elements(By.XPATH, '//div[@class="c-lister-pagination__wrapper"]//a')
    pagination_links = [element.get_attribute("href") for element in elements]
    return pagination_links

def wait_for_vacancies(driver):
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located(
            (By.XPATH, '//a[starts-with(@href, "/opdracht")]')
        )
    )

def scrape(driver):
    df_rows = []
    new_df = pd.DataFrame()    
    
    for page in list_pagination_links(driver):
        print(page)
        driver.get(page)
        time.sleep(2)

        for vacancy in list_vacancy_links(driver):
            driver.get(vacancy)
            time.sleep(2)

            # === UID FIX ===
            UID = None

            uid_try1 = driver.find_elements(By.XPATH, '//p[contains(@class, "jobId")]')
            if uid_try1:
                UID = uid_try1[0].text.strip()

            if UID is None:
                uid_try2 = driver.find_elements(
                    By.XPATH,
                    '//span[contains(text(), "Opdracht ID")]/following::p[1]'
                )
                if uid_try2:
                    UID = uid_try2[0].text.strip()

            if UID is None:
                title = driver.find_element(By.TAG_NAME, "h1").text.strip()
                UID = f"AUTO-{abs(hash(title + vacancy)) % 10_000_000}"
                print(f"⚠️ WARNING: UID missing — generated: {UID}")

            # === Rest van jouw scraping logica ===
            main_information_elements = driver.find_elements(
                By.XPATH,
                '//div[@class="c-vacancy-hero__usp-container"]/div/div[count(@*)=0]'
            )
            main_information = [e.text for e in main_information_elements]

            plaats = main_information[0]
            duur = main_information[1]
            uren = main_information[2]
            start = main_information[3]
            deadline = main_information[4]

            vacature_text = driver.find_elements(By.CSS_SELECTOR, 
                'body > main > div.c-vacancy-paragraph__outer-wrapper.outer-wrapper.background.primary > div > div.c-vacancy-paragraph__text-container > div.c-vacancy-paragraph__body-text.body-text > div:nth-child(1)'
            )
            vacature_text_elements = vacature_text[0].text   

            eisen_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Eisen:"]]/ul//li')
            eisen = [e.text for e in eisen_elements]

            wensen_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Wensen:"]]/ul//li')
            wensen = [e.text for e in wensen_elements]

            competenties_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Competenties:"]]/ul//li')
            competenties = [e.text for e in competenties_elements]

            title = driver.find_element(By.XPATH, '/html/body/main/section[2]/div/div/div/div/div[1]/a/h1').text
            
            row = {
                "UID": UID,
                "titel":title,
                "plaats": plaats,
                "duur": duur,
                "uren": uren, 
                "text":vacature_text_elements,
                "start": "".join(c for c in start if c.isdigit() or c == '-'),
                "deadline": "".join(c for c in deadline if c.isdigit() or c == '-'),
                "eisen": eisen,
                "wensen": wensen,
                "competenties": competenties
            }

            df_rows.append(row)
    
    if len(df_rows) > 0:
        new_df = pd.DataFrame(df_rows).set_index('UID')

    return new_df

def main():
    options = Options()
    options.add_argument("--headless=new")   # Headless voor CI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    with driver as driver:
        go_to_main_page_search_term_data(driver)
        new_df_data = scrape(driver=driver)
        go_to_main_page_search_term_data_engineer(driver=driver)
        new_df_data_engineer = scrape(driver=driver)

        new_df = pd.concat([new_df_data,new_df_data_engineer])
        df = new_df

    print(df)
    df = df.loc[~df.index.duplicated(keep='first'), :]
    with open("circle8.json", "w") as f:
        f.write(df.to_json(orient="index", indent=4))
    driver.quit()

if __name__ == "__main__":
    main()
