import os
import time
import json
import traceback
from typing import List, Dict

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


JSON_FILE = "./circle8.json"
TIMEOUT = 25
MAX_RETRIES_VACANCY = 3
MAX_RETRIES_REQUEST = 3


def log(msg: str) -> None:
    print(msg, flush=True)


# ----------------------------------------------------
# Stealth Chrome driver (undetected_chromedriver)
# ----------------------------------------------------
def create_driver():
    """Create a stealth Chrome driver using undetected_chromedriver.

    - Forces use of Google Chrome (installed in CI at /usr/bin/google-chrome)
    - Uses a residential proxy if PROXY env var is set
    - Runs non-headless; in CI we wrap with xvfb-run
    """
    proxy = os.getenv("PROXY", "").strip()

    options = uc.ChromeOptions()
    # Force Google Chrome instead of any system Chromium
    options.binary_location = "/usr/bin/google-chrome"

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")

    if proxy:
        # Don't print credentials
        log(f"Using residential proxy: {proxy.split('@')[-1]}")
        options.add_argument(f"--proxy-server={proxy}")

    # NOT headless here; in CI we run via xvfb-run to simulate a display
    driver = uc.Chrome(
        options=options,
        headless=False,
        use_subprocess=True,
    )

    # Stealth patches: hide webdriver etc.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1,2,3,4,5],
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['nl-NL','nl'],
                });
            """
        },
    )

    log(f"Browser version: {driver.capabilities.get('browserVersion')}")
    return driver


# ----------------------------------------------------
# Helper: URL openen + lazy-loading forceren
# ----------------------------------------------------
def safe_get(driver, url: str, wait_xpath: str = None, timeout: int = TIMEOUT, debug_label: str = "page"):
    """Navigate to a URL and optionally wait for an XPath.

    On timeout, we dump the HTML to a debug file.
    """
    log(f"-> GET {url}")
    driver.get(url)

    # Trigger JS/lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.0)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    if wait_xpath:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located((By.XPATH, wait_xpath))
            )
        except TimeoutException:
            log(f"⚠️ Timeout waiting for selector: {wait_xpath} on {url}")
            # Dump partial HTML for debugging
            fname = f"debug_{debug_label}.html"
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                log(f"Saved debug HTML: {fname}")
            except Exception as e:
                log(f"Failed to save debug HTML: {e}")
            raise


# ----------------------------------------------------
# Pagination links
# ----------------------------------------------------
def get_pagination_links(driver) -> List[str]:
    elements = driver.find_elements(
        By.XPATH,
        '//nav[contains(@class,"pagination")]//a[contains(@href,"page=")]',
    )
    if not elements:
        return [driver.current_url]
    return sorted({e.get_attribute("href") for e in elements if e.get_attribute("href")})


# ----------------------------------------------------
# Vacancy listing links
# ----------------------------------------------------
def get_vacancy_links(driver) -> List[str]:
    elements = driver.find_elements(
        By.XPATH,
        '//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]',
    )
    return list({e.get_attribute("href") for e in elements if e.get_attribute("href")})


# ----------------------------------------------------
# UID extraction
# ----------------------------------------------------
def get_uid(driver) -> str:
    els = driver.find_elements(
        By.XPATH,
        '//div[contains(@class,"jobid")]//p',
    )
    if els:
        return els[0].text.strip()

    # Fallback: generate UID from title
    title = driver.find_element(
        By.XPATH, '//h1[contains(@class,"vacancy")]'
    ).text.strip()
    return f"AUTO-{abs(hash(title)) % 10_000_000}"


# ----------------------------------------------------
# Single vacancy scraping
# ----------------------------------------------------
def scrape_one_vacancy(driver, url: str) -> Dict:
    safe_get(driver, url, debug_label="vacancy")

    title = driver.find_element(
        By.XPATH, '//h1[contains(@class,"vacancy")]'
    ).text.strip()

    UID = get_uid(driver)

    specs = driver.find_elements(
        By.XPATH,
        '//div[contains(@class,"usp-list")]//div[contains(@class,"usp-item")]',
    )
    specs_text = [s.text.strip() for s in specs]

    def get_field(idx: int) -> str:
        return specs_text[idx] if idx < len(specs_text) else ""

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

    def extract_list(label: str) -> List[str]:
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
# Scrape all pages for one search term
# ----------------------------------------------------
def scrape_search_term(driver, term: str) -> pd.DataFrame:
    log(f"\n=== Zoekterm: {term} ===")
    search_url = f"https://www.circle8.nl/zoeken?query={term.replace(' ', '%20')}"

    # First page
    safe_get(
        driver,
        search_url,
        wait_xpath='//a[contains(@class,"c-vacancy-grid-card c-vacancy-grid-card__wrapper vacancy-lister-item ")]',
        debug_label=f"search_{term.replace(' ', '_')}",
    )

    pages = get_pagination_links(driver)
    log(f"Pagina's gevonden voor '{term}': {len(pages)}")

    rows = []

    for page in pages:
        log(f"  -> Pagina: {page}")
        # Retry wrapper for network issues
        for attempt in range(1, MAX_RETRIES_REQUEST + 1):
            try:
                safe_get(
                    driver,
                    page,
                    wait_xpath='//a[contains(@class,"c-vacancy-grid-card c-vacancy-grid-card__wrapper vacancy-lister-item ")]',
                    debug_label=f"list_{term.replace(' ', '_')}_{attempt}",
                )
                break
            except TimeoutException:
                log(f"⚠️ Timeout op {page} (attempt {attempt}/{MAX_RETRIES_REQUEST})")
                if attempt == MAX_RETRIES_REQUEST:
                    log("❌ Pagina overgeslagen na meerdere pogingen.")
                    continue
        vacancies = get_vacancy_links(driver)
        log(f"     Vacatures op deze pagina: {len(vacancies)}")

        for v in vacancies:
            for attempt in range(1, MAX_RETRIES_VACANCY + 1):
                try:
                    row = scrape_one_vacancy(driver, v)
                    rows.append(row)
                    break
                except TimeoutException:
                    log(f"⚠️ Timeout bij vacature {v} (attempt {attempt}/{MAX_RETRIES_VACANCY})")
                    if attempt == MAX_RETRIES_VACANCY:
                        log(f"❌ Vacature overgeslagen: {v}")
                except WebDriverException as we:
                    log(f"⚠️ WebDriverException bij {v}: {we}")
                    if attempt == MAX_RETRIES_VACANCY:
                        log(f"❌ Vacature overgeslagen (webdriver): {v}")
                except Exception as e:
                    log(f"⚠️ Onbekende fout bij {v}: {e}")
                    traceback.print_exc()
                    if attempt == MAX_RETRIES_VACANCY:
                        log(f"❌ Vacature overgeslagen (unknown error): {v}")

    if not rows:
        debug_file = f"debug_no_vacancies_{term.replace(' ', '_')}.html"
        try:
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            log(f"⚠️ Geen vacatures gevonden voor '{term}'. HTML snapshot: {debug_file}")
        except Exception as e:
            log(f"Kon debug HTML niet wegschrijven: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("UID")
    log(f"Totaal vacatures voor '{term}': {len(df)}")
    return df


# ----------------------------------------------------
# Main
# ----------------------------------------------------
def main():
    log("Starting Circle8 scraper...")
    driver = create_driver()

    try:
        df_data = scrape_search_term(driver, "data")
        df_engineer = scrape_search_term(driver, "data engineer")
        df_ml = scrape_search_term(driver, "machine learning engineer")

        new_df = pd.concat([df_data, df_engineer, df_ml])
        new_df = new_df[~new_df.index.duplicated(keep="first")]

        log(f"\nNieuwe scrapes, unieke vacatures: {len(new_df)}")

        if os.path.exists(JSON_FILE):
            try:
                existing_df = pd.read_json(JSON_FILE, orient="index")
            except Exception:
                log("⚠️ Kon bestaande JSON niet lezen, begin opnieuw.")
                existing_df = pd.DataFrame()

            if not existing_df.empty:
                existing_df = existing_df[~existing_df.index.isin(new_df.index)]
                df = pd.concat([existing_df, new_df])
            else:
                df = new_df
        else:
            df = new_df

        df = df[~df.index.duplicated(keep="first")]
        df.to_json(JSON_FILE, orient="index", indent=4, force_ascii=False)
        log(f"✅ JSON geüpdatet: {JSON_FILE}")
        log(f"Totaal vacatures in JSON: {len(df)}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
