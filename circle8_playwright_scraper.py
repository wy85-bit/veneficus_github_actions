import json
import os
import time
import hashlib
import pandas as pd

from playwright.sync_api import sync_playwright

JSON_FILE = "./circle8.json"

SEARCH_TERMS = [
    "data",
    "data engineer",
    "machine learning engineer"
]

VACANCY_SELECTORS = [
    "a[href*='/opdracht']",
    ".vacancy-lister-item",
    ".c-card-vacancy",
    ".vacancy-card",
    ".vacancy-lister"
]


def fingerprint_stealth(page):
    """Stealth patches – Playwright equivalent of undetected-chromedriver."""
    scripts = [
        # navigator.webdriver = false
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",

        # Fake plugins
        "Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]})",

        # Fake languages
        "Object.defineProperty(navigator, 'languages', {get: () => ['nl-NL','nl']})",

        # Add chrome object
        "window.chrome = {runtime: {}}"
    ]

    for script in scripts:
        page.add_init_script(script)


def hash_uid(url: str):
    """Hash URL to a stable UID."""
    return "UID-" + hashlib.md5(url.encode()).hexdigest()[:12]


def extract_vacancies(page):
    """Extract all vacancy URLs from search results."""
    links = set()

    for selector in VACANCY_SELECTORS:
        elements = page.query_selector_all(selector)
        for el in elements:
            href = el.get_attribute("href")
            if href and "/opdracht/" in href:
                if href.startswith("/"):
                    href = "https://www.circle8.nl" + href
                links.add(href)

    return sorted(list(links))


def scrape_vacancy(page, url):
    """Scrape a single vacancy page."""
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(1)

    title = page.locator("h1").first.inner_text()

    body_text = page.locator("main").inner_text()

    uid = hash_uid(url)

    return {
        "UID": uid,
        "titel": title,
        "content": body_text,
        "url": url
    }


def scrape_search_term(page, term):
    """Scrape one search term."""
    search_url = f"https://www.circle8.nl/zoeken?query={term.replace(' ', '%20')}"

    page.goto(search_url, wait_until="domcontentloaded")
    time.sleep(2)

    all_links = extract_vacancies(page)

    print(f"[{term}] Found {len(all_links)} vacancies.")

    rows = []
    for link in all_links:
        try:
            row = scrape_vacancy(page, link)
            rows.append(row)
        except Exception as e:
            print(f"Error scraping {link}: {e}")

    if rows:
        df = pd.DataFrame(rows).set_index("UID")
    else:
        df = pd.DataFrame()

    return df


def main():
    proxy = os.getenv("PROXY")

    with sync_playwright() as p:

        browser_args = [
            "--disable-blink-features=AutomationControlled",
        ]

        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }

        if proxy:
            context_options["proxy"] = {"server": proxy}
            print("Using proxy:", proxy)

        browser = p.chromium.launch(headless=True, args=browser_args)
        context = browser.new_context(**context_options)

        page = context.new_page()
        fingerprint_stealth(page)

        all_dfs = []

        for term in SEARCH_TERMS:
            df = scrape_search_term(page, term)
            all_dfs.append(df)

        new_df = pd.concat(all_dfs)
        new_df = new_df[~new_df.index.duplicated()]

        if os.path.exists(JSON_FILE):
            old = pd.read_json(JSON_FILE, orient="index")
            old = old[~old.index.isin(new_df.index)]
            final_df = pd.concat([old, new_df])
        else:
            final_df = new_df

        final_df.to_json(JSON_FILE, indent=2, orient="index")
        print("Saved:", JSON_FILE)

        browser.close()


if __name__ == "__main__":
    main()
