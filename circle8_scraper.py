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


# ------------------------------
# Helpers
# ------------------------------

def wait_for_any(driver, by, value, timeout=15):
    """Wacht tot er tenminste één element is dat aan de locator voldoet."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((by, value))
    )


def safe_get(driver, url, wait_xpath=None, timeout=15):
    """Naar URL gaan + desnoods ergens op wachten + klein beetje extra tijd."""
    driver.get(url)
    # kleine scroll om lazy-loading te triggeren in headless
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    if wait_xpath:
        wait_for_any(driver, By.XPATH, wait_xpath, timeout=timeout)


# ------------------------------
# Pagina- en vacaturelinks
# ------------------------------

def list_pagination_links(driver):
    """Zoek pagination links; als er geen zijn, geef huidige pagina terug."""
    # Probeer originele pagination
    elements = driver.find_elements(By.XPATH, '//div[@class="c-lister-pagination__wrapper"]//a')
    links = [e.get_attribute("href") for e in elements if e.get_attribute("href")]

    # Fallback: generieker zoeken op page= in href
    if not links:
        elements = driver.find_elements(By.XPATH, '//a[contains(@href, "page=")]')
        links = [e.get_attribute("href") for e in elements if e.get_attribute("href")]

    # Als nog steeds niets: alleen huidige pagina gebruiken
    if not links:
        return [driver.current_url]

    # Uniek + gesorteerd
    return sorted(set(links))


def list_vacancy_links(driver):
    """Alle vacaturelinks op de huidige pagina."""
    # Wachten tot er minstens één vacaturelink is
    wait_for_any(driver, By.XPATH, '//a[contains(@href, "/opdracht")]', timeout=15)
    elements = driver.find_elements(By.XPATH, '//a[contains(@href, "/opdracht")]')
    links = {e.get_attribute("href") for e in elements if e.get_attribute("href")}
    return list(links)


# ------------------------------
# Scrape 1 vacature
# ------------------------------

def scrape_single_vacancy(driver, vacancy_url):
    """Details van één vacature ophalen, returnt dict met data."""
    safe_get(driver, vacancy_url, wait_xpath='//h1')

    # === UID met fallbacks ===
    UID = None

    # oud ontwerp
    uid_try1 = driver.find_elements(By.XPATH, '//p[contains(@class, "jobId")]')
    if uid_try1:
        UID = uid_try1[0].text.strip()

    # nieuw ontwerp: label "Opdracht ID" gevolgd door <p>
    if UID is None:
        uid_try2 = driver.find_elements(
            By.XPATH, '//span[contains(text(), "Opdracht ID")]/following::p[1]'
        )
        if uid_try2:
            UID = uid_try2[0].text.strip()

    # als alles faalt -> zelf UID genereren
    title_el = driver.find_element(By.TAG_NAME, "h1")
    title = title_el.text.strip()
    if UID is None:
        UID = f"AUTO-{abs(hash(title + vacancy_url)) % 10_000_000}"
        print(f"⚠️ UID missing — generated: {UID}")

    # hoofdinfo (plaats, duur, uren, start, deadline)
    main_information_elements = driver.find_elements(
        By.XPATH,
        '//div[@class="c-vacancy-hero__usp-container"]/div/div[count(@*)=0]'
    )
    main_information = [e.text.strip() for e in main_information_elements]

    # defensief: niet crashen als er minder velden zijn
    def get_or_empty(lst, idx):
        return lst[idx] if idx < len(lst) else ""

    plaats = get_or_empty(main_information, 0)
    duur = get_or_empty(main_information, 1)
    uren = get_or_empty(main_information, 2)
    start = get_or_empty(main_information, 3)
    deadline = get_or_empty(main_information, 4)

    # tekst van vacature
    tekst_els = driver.find_elements(
        By.CSS_SELECTOR,
        'div.c-vacancy-paragraph__body-text.body-text > div:nth-child(1)'
    )
    text = tekst_els[0].text if tekst_els else ""

    # eisen / wensen / competenties
    eisen_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Eisen:"]]/ul//li')
    eisen = [e.text.strip() for e in eisen_elements]

    wensen_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Wensen:"]]/ul//li')
    wensen = [w.text.strip() for w in wensen_elements]

    competenties_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Competenties:"]]/ul//li')
    competenties = [c.text.strip() for c in competenties_elements]

    row = {
        "UID": UID,
        "titel": title,
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

    return row


# ------------------------------
# Scrape een hele zoekterm
# ------------------------------

def scrape_search_term(driver, term):
    """Scrapet alle pagina's en vacatures voor één zoekterm."""
    print(f"\n=== Scraping zoekterm: {term} ===")

    search_url = f"https://www.circle8.nl/zoeken?query={term.replace(' ', '%20')}"
    safe_get(driver, search_url, wait_xpath='//a[contains(@href, "/opdracht")]')

    pages = list_pagination_links(driver)
    print(f"Pagina's gevonden voor '{term}': {len(pages)}")

    df_rows = []

    for page in pages:
        print(f"  -> Pagina: {page}")
        safe_get(driver, page, wait_xpath='//a[contains(@href, "/opdracht")]')
        vacancies = list_vacancy_links(driver)
        print(f"     Vacatures op deze pagina: {len(vacancies)}")

        for vacancy_url in vacancies:
            try:
                row = scrape_single_vacancy(driver, vacancy_url)
                df_rows.append(row)
            except Exception as e:
                print(f"⚠️ Fout bij vacancy {vacancy_url}: {e}")

    if df_rows:
        df = pd.DataFrame(df_rows).set_index("UID")
    else:
        df = pd.DataFrame(columns=[
            "titel", "plaats", "duur", "uren", "start", "deadline",
            "text", "eisen", "wensen", "competenties", "url"
        ])
        df.index.name = "UID"

    print(f"Totaal vacatures voor '{term}': {len(df)}")
    return df


# ------------------------------
# Main
# ------------------------------

def main():
    options = Options()
    options.add_argument("--headless=new")   # headless voor CI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        df_data = scrape_search_term(driver, "data")
        df_data_engineer = scrape_search_term(driver, "data engineer")
        df_ml_engineer = scrape_search_term(driver, "machine learning engineer")

        # alles combineren + dubbelen verwijderen op UID
        df = pd.concat([df_data, df_data_engineer, df_ml_engineer])
        df = df[~df.index.duplicated(keep="first")]

        print("\n=== Overzicht eindresultaat ===")
        print("Totaal unieke vacatures:", len(df))
        print(df.head())

        # alleen wegschrijven als er iets is
        if len(df) > 0:
            with open("circle8.json", "w", encoding="utf-8") as f:
                f.write(df.to_json(orient="index", indent=4, force_ascii=False))
            print("\n✅ circle8.json geschreven / geüpdatet")
        else:
            print("\n⚠️ Geen vacatures gevonden — circle8.json niet weggeschreven (of leeg).")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
