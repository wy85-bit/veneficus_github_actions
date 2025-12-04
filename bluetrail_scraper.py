import os
import time
import pandas as pd
import undetected_chromedriver as uc
from datetime import datetime
from selenium.webdriver.common.by import By
from dotenv import load_dotenv

# Load GitHub Actions secrets as environment variables
load_dotenv()

OUTPUT_FILE = f"bluetrail_{datetime.now().strftime('%Y-%m-%d')}.json"


def go_to_page(driver, page_nr):
    url = f'https://www.bluetrail.nl/opdrachten/page/{page_nr + 1}/?srch=data'
    driver.get(url)
    return url


def go_to_page_search_term_machine_learning(driver):
    url = 'https://www.bluetrail.nl/opdrachten/?s=machine+learning'
    driver.get(url)
    return url


def list_vacancy_links(driver):
    time.sleep(2)
    elements = driver.find_elements(By.CSS_SELECTOR, "a.u-job-card")
    return [element.get_attribute("href") for element in elements]


def scrape_pages(driver, page_url):
    print("Scraping:", page_url)
    driver.get(page_url)
    time.sleep(4)

    rows = []
    links = list_vacancy_links(driver)

    for vacancy in links:
        driver.get(vacancy)
        time.sleep(2)

        try:
            title = driver.find_element(By.CSS_SELECTOR, "h1 span").text
        except:
            title = ""

        # Try expanding "show more"
        try:
            show_more_button = driver.find_element(By.XPATH, "//article//a[contains(@class, 'show-more')]")
            driver.execute_script("arguments[0].click();", show_more_button)
            time.sleep(1)
        except:
            pass

        # Extracting fields (with fallback)
        def safe_xpath(xpath):
            try:
                return driver.find_element(By.XPATH, xpath).text
            except:
                return ""

        UID = safe_xpath("(//p/span)[2]")
        plaats = safe_xpath("(//p/span)[3]")
        start = safe_xpath("(//p/span)[4]")
        uren = safe_xpath("(//p/span)[7]")
        deadline = safe_xpath("(//p/span)[9]")
        duur = safe_xpath("//*[@id='content']//span[3]")
        eind = safe_xpath("(//*[@id='text-4']//span)[5]")

        # Full text scraping
        try:
            vacature_text = driver.find_element(By.XPATH, "//div[h3]").text
        except:
            vacature_text = ""

        # Lists
        def list_elements(xpath):
            try:
                return [e.text for e in driver.find_elements(By.XPATH, xpath)]
            except:
                return []

        eisen = list_elements("//article/div//ul[1]/li")
        wensen = list_elements("//article/div//ul[2]/li")
        competenties = list_elements("//article/div//ul[3]/li")

        row = {
            "UID": UID,
            "Referentie-nr": UID,
            "titel": title,
            "plaats": plaats,
            "uren": uren,
            "text": vacature_text,
            "start": start,
            "eind": eind,
            "duur": duur,
            "deadline": deadline,
            "eisen": eisen,
            "wensen": wensen,
            "competenties": competenties
        }

        rows.append(row)
        time.sleep(1)

    return rows


def main():
    print("Starting BlueTrail scraper...")

    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(options=options)

    all_data = []

    # First: pages with search term "data"
    for i in range(5):
        page_url = go_to_page(driver, i)
        all_data.extend(scrape_pages(driver, page_url))

    # Second: machine learning page
    ml_url = go_to_page_search_term_machine_learning(driver)
    all_data.extend(scrape_pages(driver, ml_url))

    driver.quit()

    # Create dataframe
    df = pd.DataFrame(all_data)
    df = df.drop_duplicates("UID").set_index("UID")

    df = df[
        ["Referentie-nr", "titel", "plaats", "uren", "text",
         "start", "eind", "duur", "deadline", "eisen", "wensen", "competenties"]
    ]

    df.to_json(OUTPUT_FILE, orient="index", indent=4)
    print("Saved JSON:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
