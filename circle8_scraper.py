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


# ============================================
#  Global timeout in CI (GitHub Actions)
# ============================================

GLOBAL_TIMEOUT = 30


# ============================================
#  Helper: Scroll-based lazy-loading fix
# ============================================

def safe_get(driver, url, wait_xpath=None, timeout=GLOBAL_TIMEOUT):
    """Navigate to page + force lazy-loading JS render."""
    driver.get(url)

    # Scroll to bottom to trigger dynamic loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.2)

    # Scroll back to top to stabilize DOM
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.8)

    if wait_xpath:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located((By.XPATH, wait_xpath))
            )
        except Exception:
            print(f"❌ Timeout waiting for: {wait_xpath}")
            print("🔍 URL:", url)
            print("🧾 Page source (first 2000 chars):")
            print(driver.page_source[:2000])
            raise


# ============================================
#  Pagination
# ============================================

def list_pagination_links(driver):
    """Find pagination links or fallback to current page."""
    # Try official container
    elements = driver.find_elements(By.XPATH, '//div[@class="c-lister-pagination__wrapper"]//a')

    links = [e.get_attribute("href") for e in elements if e.get_attribute("href")]

    # Fallback: generic ?page=
    if not links:
        elements = driver.find_elements(By.XPATH, '//a[contains(@href, "page=")]')
        links = [e.get_attribute("href") for e in elements if e.get_attribute("href")]

    if not links:
        return [driver.current_url]  # Only one page

    # return unique sorted links
    return sorted(set(links))


# ============================================
#  Vacancy links
# ============================================

def list_vacancy_links(driver):
    """Get all vacancy links on current page."""
    # Robust selector for all Circle8 designs
    safe_get(driver, driver.current_url, wait_xpath='//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]')
    elements = driver.find_elements(By.XPATH, '//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]')
    return list({e.get_attribute("href") for e in elements if e.get_attribute("href")})


# ============================================
#  Scrape Single Vacancy
# ============================================

def scrape_single_vacancy(driver, vacancy_url):
    safe_get(driver, vacancy_url, wait_xpath='//h1')

    # UID with fallbacks
    UID = None

    # Old design
    uid_try1 = driver.find_elements(By.XPATH, '//p[contains(@class, "jobId")]')
    if uid_try1:
        UID = uid_try1[0].text.strip()

    # New design
    if UID is None:
        uid_try2 = driver.find_elements(
            By.XPATH, '//span[contains(text(), "Opdracht ID")]/following::p[1]'
        )
        if uid_try2:
            UID = uid_try2[0].text.strip()

    # Ultimate fallback
    title_txt = driver.find_element(By.TAG_NAME, "h1").text.strip()
    if UID is None:
        UID = f"AUTO-{abs(hash(title_txt + vacancy_url)) % 1_000_000_000}"
        print(f"⚠️ UID missing — generated: {UID}")

    # Main info
    main_info_elements = driver.find_elements(
        By.XPATH, '//div[@class="c-vacancy-hero__usp-container"]/div/div[count(@*)=0]'
    )
    main_info = [e.text.strip() for e in main_info_elements]

    def get_or_empty(lst, idx):
        return lst[idx] if idx < len(lst) else ""

    plaats = get_or_empty(main_info, 0)
    duur = get_or_empty(main_info, 1)
    uren = get_or_empty(main_info, 2)
    start = get_or_empty(main_info, 3)
    deadline = get_or_empty(main_info, 4)

    # Job text
    text_block = driver.find_elements(
        By.CSS_SELECTOR,
        'div.c-vacancy-paragraph__body-text.body-text > div:nth-child(1)'
    )
    text = text_block[0].text if text_block else ""

    # Lists
    eisen = [e.text.strip() for e in driver.find_elements(By.XPATH, '//div[h3[text()="Eisen:"]]/ul/li')]
    wensen = [e.text.strip() for e in driver.find_elements(By.XPATH, '//div[h3[text()="Wensen:"]]/ul/li')]
    competenties = [e.text.strip() for e in driver.find_elements(By.XPATH, '//div[h3[text()="Competenties:"]]/ul/li')]

    return {
        "UID": UID,
        "titel": title_txt,
        "plaats": plaats,
        "duur": duur,
        "uren": uren,
        "start": "".join(c for c in start if c.isdigit() or c == '-'),
        "deadline": "".join(c for c in deadline if c.isdigit() or c == '-'),
        "text": text,
        "eisen": eisen,
        "wensen": wensen,
        "competenties": competenties,
        "url": vacancy_url,
    }


# ============================================
#  Scrape whole search term
# ============================================

def scrape_search_term(driver, term):
    print(f"\n=== Scraping term: {term} ===")

    search_url = f"https://www.circle8.nl/zoeken?query={term.replace(' ', '%20')}"
    safe_get(driver, search_url, wait_xpath='//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]')

    pages = list_pagination_links(driver)
    print(f"Pages found: {len(pages)}")

    rows = []

    for page in pages:
        print(f" -> Page: {page}")
        safe_get(driver, page, wait_xpath='//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]')
        vacancies = list_vacancy_links(driver)
        print(f"    Vacancies: {len(vacancies)}")

        for link in vacancies:
            try:
                row = scrape_single_vacancy(driver, link)
                rows.append(row)
            except Exception as e:
                print(f"⚠️ Error scraping {link}: {e}")

    if rows:
        df = pd.DataFrame(rows).set_index("UID")
    else:
        df = pd.DataFrame(columns=[
            "titel", "plaats", "duur", "uren", "start", "deadline",
            "text", "eisen", "wensen", "competenties", "url"
        ])
        df.index.name = "UID"

    print(f"Total vacancies for '{term}': {len(df)}")
    return df


# ============================================
#  Main
# ============================================

def main():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        df1 = scrape_search_term(driver, "data")
        df2 = scrape_search_term(driver, "data engineer")
        df3 = scrape_search_term(driver, "machine learning engineer")

        df = pd.concat([df1, df2, df3])
        df = df[~df.index.duplicated(keep="first")]

        print("\n=== FINAL RESULT ===")
        print("Unique vacancies:", len(df))
        print(df.head())

        if len(df) > 0:
            with open("circle8.json", "w", encoding="utf-8") as f:
                f.write(df.to_json(orient="index", indent=4, force_ascii=False))
            print("✅ Saved: circle8.json")
        else:
            print("⚠️ No vacancies found, JSON not written.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
