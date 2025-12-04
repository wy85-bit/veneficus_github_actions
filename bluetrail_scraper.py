import time
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

OUTPUT_FILE = f"bluetrail_{datetime.now().strftime('%Y-%m-%d')}.json"


# ----------------------------------------
# Driver setup (100% compatible with GitHub Actions)
# ----------------------------------------
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver


# ----------------------------------------
# Helpers
# ----------------------------------------
def go_to_page(driver, page_nr):
    url = f"https://www.bluetrail.nl/opdrachten/page/{page_nr+1}/?srch=data"
    driver.get(url)
    time.sleep(2)
    return url


def go_to_page_search_term_machine_learning(driver):
    url = "https://www.bluetrail.nl/opdrachten/?s=machine+learning"
    driver.get(url)
    time.sleep(2)
    return url


def list_vacancy_links(driver):
    time.sleep(2)
    cards = driver.find_elements(By.CSS_SELECTOR, "a.u-job-card")
    return [c.get_attribute("href") for c in cards]


def safe_xpath(driver, xpath, default=""):
    try:
        return driver.find_element(By.XPATH, xpath).text.strip()
    except:
        return default


def safe_list(driver, xpath):
    try:
        return [el.text for el in driver.find_elements(By.XPATH, xpath)]
    except:
        return []


# ----------------------------------------
# Core scraping logic
# ----------------------------------------
def scrape_pages(driver, url):
    print("Scraping:", url)
    driver.get(url)
    time.sleep(3)

    vacancy_links = list_vacancy_links(driver)
    results = []

    for link in vacancy_links:
        driver.get(link)
        time.sleep(2)

        title = safe_xpath(driver, "//h1/span")

        # Expand "show more"
        try:
            btn = driver.find_element(By.XPATH, "//a[contains(@class,'show-more')]")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        except:
            pass

        UID = safe_xpath(driver, "(//p/span)[2]")
        plaats = safe_xpath(driver, "(//p/span)[3]")
        start = safe_xpath(driver, "(//p/span)[4]")
        uren = safe_xpath(driver, "(//p/span)[7]")
        deadline = safe_xpath(driver, "(//p/span)[9]")
        duur = safe_xpath(driver, "//*[@id='content']//span[3]")
        eind = safe_xpath(driver, "(//*[@id='text-4']//span)[5]")

        vacature_text = safe_xpath(driver, "//div[h3]")

        eisen = safe_list(driver, "//article//ul[1]/li")
        wensen = safe_list(driver, "//article//ul[2]/li")
        competenties = safe_list(driver, "//article//ul[3]/li")

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

        results.append(row)
        time.sleep(1)

    return results


# ----------------------------------------
# Main workflow
# ----------------------------------------
def main():
    print("Starting BlueTrail scraper...")

    driver = get_driver()
    all_rows = []

    # Pages with search term 'data'
    for i in range(5):
        page_url = go_to_page(driver, i)
        all_rows.extend(scrape_pages(driver, page_url))

    # Machine learning page
    ml_url = go_to_page_search_term_machine_learning(driver)
    all_rows.extend(scrape_pages(driver, ml_url))

    driver.quit()

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates("UID").set_index("UID")

    df = df[
        ["Referentie-nr", "titel", "plaats", "uren", "text",
         "start", "eind", "duur", "deadline", "eisen", "wensen", "competenties"]
    ]

    df.to_json(OUTPUT_FILE, orient="index", indent=4)
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
