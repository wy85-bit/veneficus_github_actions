import os
import time
import json
import pandas as pd
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

JSON_FILE = "./circle8.json"
TIMEOUT = 25

# ==== LOAD PROXY FROM ENV ====
PROXY = os.getenv("PROXY")  # <-- GitHub Secret


# ----------------------------------------------------
# Stealth Chrome driver (undetected_chromedriver)
# ----------------------------------------------------
def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # === RESIDENTIAL PROXY ===
    if PROXY:
        print("Using residential proxy:", PROXY.split('@')[-1])
        options.add_argument(f"--proxy-server={PROXY}")

    # not headless (we use xvfb in CI)
    driver = uc.Chrome(
        options=options,
        headless=False,
        use_subprocess=True
    )

    # stealth patches
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['nl-NL','nl']
            });
            window.chrome = { runtime: {} };
        """
    })

    return driver



# ----------------------------------------------------
# Helper: URL openen + lazy-loading forceren
# ----------------------------------------------------
def safe_get(driver, url, wait_xpath=None):
    driver.get(url)

    # Forceer JS/rendering
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.0)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    if wait_xpath:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_all_elements_located((By.XPATH, wait_xpath))
        )


# ----------------------------------------------------
# Pagination links ophalen
# ----------------------------------------------------
def get_pagination_links(driver):
    elements = driver.find_elements(
        By.XPATH,
        '//nav[contains(@class,"pagination")]//a[contains(@href,"page=")]',
    )
    if not elements:
        return [driver.current_url]
    return sorted({e.get_attribute("href") for e in elements})


# ----------------------------------------------------
# Vacature-links op een listing pagina
# ----------------------------------------------------
def get_vacancy_links(driver):
    safe_get(driver, driver.current_url)
    elements = driver.find_elements(
        By.XPATH,
        '//a[contains(@class,"c-card-vacancy__link") and contains(@href,"/opdracht")]',
    )
    return list({e.get_attribute("href") for e in elements})


# ----------------------------------------------------
# UID extraheren met fallback
# ----------------------------------------------------
def get_uid(driver):
    els = driver.find_elements(
        By.XPATH,
        '//div[contains(@class,"jobid")]//p',
    )
    if els:
        return els[0].text.strip()

    # Fallback: genereer UID op basis van titel
    title = driver.find_element(
        By.XPATH, '//h1[contains(@class,"vacancy")]'
    ).text.strip()
    return f"AUTO-{abs(hash(title)) % 10_000_000}"


# ----------------------------------------------------
# Eén vacaturepagina scrapen
# ----------------------------------------------------
def scrape_one_vacancy(driver, url):
    safe_get(driver, url)

    title = driver.find_element(
        By.XPATH, '//h1[contains(@class,"vacancy")]'
    ).text.strip()

    UID = get_uid(driver)

    specs = driver.find_elements(
        By.XPATH,
        '//div[contains(@class,"usp-list")]//div[contains(@class,"usp-item")]',
    )
    specs = [s.text.strip() for s in specs]

    def get_field(idx):
        return specs[idx] if idx < len(specs) else ""

    plaats = get_field(0)
    duur = get_field(1)
    uren = get_field(2)
    start = get_field(3)
    deadline = get_field(4)

    text_block = driver.find_elements(
        By.XPATH,
        '//section[contains(@class,"vacancy-content")]//div[contains(@class,"text-editor")]',
    )
    text = text_block[0].text if text_block else ""

    def extract_list(label):
        xpath = f'//h3[contains(text(),"{label}")]/following::ul[1]/li'
        return [
            el.text.strip()
            for el in driver.find_elements(By.XPATH, xpath)
        ]

    eisen = extract_list("Eisen")
    wensen = extract_list("Wensen")
    competenties = extract_list("Competenties")

    return {
        "UID": UID,
        "titel": title,
        "plaats": plaats,
        "duur": duur,
        "uren": uren,
        "start": "".join(c for c in start if c.isdigit() or c == "-"),
        "deadline": "".join(c for c in deadline if c.isdigit() or c == "-"),
        "text": text,
        "eisen": eisen,
        "wensen": wensen,
        "competenties": competenties,
        "url": url,
    }


# ----------------------------------------------------
# Alle vacatures voor één zoekterm scrapen
# ----------------------------------------------------
def scrape_search_term(driver, term: str) -> pd.DataFrame:
    print(f"\n=== Zoekterm: {term} ===")
    search_url = f"https://www.circle8.nl/zoeken?query={term.replace(' ', '%20')}"
    safe_get(
        driver,
        search_url,
        wait_xpath='//a[contains(@class,"c-card-vacancy__link")]',
    )

    pages = get_pagination_links(driver)
    print(f"Pagina's gevonden: {len(pages)}")

    rows = []

    for page in pages:
        print(f"  -> Pagina: {page}")
        safe_get(
            driver,
            page,
            wait_xpath='//a[contains(@class,"c-card-vacancy__link")]',
        )
        vacancies = get_vacancy_links(driver)
        print(f"     Vacatures op deze pagina: {len(vacancies)}")

        for v in vacancies:
            try:
                row = scrape_one_vacancy(driver, v)
                rows.append(row)
            except Exception as e:
                print(f"⚠️ Fout bij vacature {v}: {e}")

    if not rows:
        # Debug snapshot als er niks gevonden is
        debug_file = f"debug_{term.replace(' ', '_')}.html"
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"⚠️ Geen vacatures gevonden voor '{term}'. HTML snapshot: {debug_file}")
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("UID")
    print(f"Totaal vacatures voor '{term}': {len(df)}")
    return df


# ----------------------------------------------------
# Main
# ----------------------------------------------------
def main():
    print("Starting scraper...")
    driver = create_driver()

    try:
        df_data = scrape_search_term(driver, "data")
        df_engineer = scrape_search_term(driver, "data engineer")
        df_ml = scrape_search_term(driver, "machine learning engineer")

        df = pd.concat([df_data, df_engineer, df_ml])
        df = df[~df.index.duplicated(keep="first")]

        print("\nScraped:", len(df), "vacatures")

        if os.path.exists(JSON_FILE):
            old = pd.read_json(JSON_FILE, orient="index")
            old = old[~old.index.isin(df.index)]
            df = pd.concat([old, df])

        df.to_json(JSON_FILE, indent=4, orient="index", force_ascii=False)
        print("Saved:", JSON_FILE)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
