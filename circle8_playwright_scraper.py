import os
import time
import hashlib
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

JSON_FILE = "./circle8.json"

SEARCH_TERMS = [
    "data",
    "data engineer",
    "machine learning engineer",
]

BASE_SEARCH_URL = "https://www.circle8.nl/zoeken?query={query}"


def uid_from_url(url: str) -> str:
    return "UID-" + hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def apply_stealth(page):
    # Kleine stealth patches
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['nl-NL','nl'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
        window.chrome = { runtime: {} };
    """)


def collect_vacancy_links_on_page(page) -> set[str]:
    """Zoek alle /opdracht/ links op de huidige zoekresultatenpagina."""
    links = set()
    anchors = page.locator("a[href*='/opdracht/']")
    count = anchors.count()
    print(f"  [-] Aantal <a href*='/opdracht/'> op deze pagina: {count}")

    for i in range(count):
        href = anchors.nth(i).get_attribute("href")
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.circle8.nl" + href
        if "/opdracht/" in href:
            links.add(href)
    return links


def collect_pagination_links(page, current_url: str) -> set[str]:
    """Zoek alle paginalinks (1, 2, 3 ...) en geef volledige URLs terug."""
    page_links = set()

    anchors = page.locator("a[href*='?query=']")
    for i in range(anchors.count()):
        href = anchors.nth(i).get_attribute("href") or ""
        if "page=" in href:
            if href.startswith("/"):
                href = "https://www.circle8.nl" + href
            page_links.add(href)

    # Als er geen expliciete page= links zijn, ga dan alleen van de eerste pagina uit
    if not page_links:
        print("  [-] Geen paginalinks gevonden, alleen deze pagina.")
    else:
        print(f"  [-] Paginalinks gevonden: {page_links}")

    # Zorg dat de huidige pagina zelf ook in de set zit
    page_links.add(current_url)
    return page_links


def scrape_vacancy(page, url: str) -> dict:
    print(f"    [*] Scrape vacature: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    # Kleine extra wacht + scroll om alles zichtbaar te maken
    page.wait_for_timeout(1000)
    page.mouse.wheel(0, 2000)
    page.wait_for_timeout(500)

    try:
        title = page.locator("h1").first.inner_text().strip()
    except PlaywrightTimeoutError:
        title = ""

    main_text = ""
    try:
        main_text = page.locator("main").inner_text().strip()
    except PlaywrightTimeoutError:
        main_text = page.content()[:4000]  # fallback: ruwe HTML-tekst

    uid = uid_from_url(url)

    return {
        "UID": uid,
        "titel": title,
        "text": main_text,
        "url": url,
    }


def scrape_search_term(context, term: str) -> pd.DataFrame:
    print(f"\n=== Zoekterm: {term} ===")
    page = context.new_page()
    apply_stealth(page)

    first_url = BASE_SEARCH_URL.format(query=term.replace(" ", "%20"))
    print(f"[+] Open zoekpagina: {first_url}")
    page.goto(first_url, wait_until="networkidle", timeout=30000)

    # Scroll een paar keer om lazy loading te triggeren
    for _ in range(6):
        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(400)

    # Debug: toon even aantal gevonden opdrachten (tekstueel)
    try:
        summary = page.get_by_text("Resultaten:", exact=False).first.inner_text()
        print(f"  [-] Samenvatting op pagina: {summary}")
    except Exception:
        print("  [-] Kon 'Resultaten:' tekst niet vinden (is niet fataal).")

    # Verzamel alle paginalinks
    page_links = collect_pagination_links(page, first_url)

    all_vacancy_urls: set[str] = set()

    # Loop over alle paginalinks
    for p_url in sorted(page_links):
        print(f"[+] Bezoek resultatenpagina: {p_url}")
        page.goto(p_url, wait_until="networkidle", timeout=30000)
        for _ in range(4):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(300)

        page.wait_for_timeout(500)
        urls = collect_vacancy_links_on_page(page)
        print(f"  [-] Vacaturelinks op deze pagina: {len(urls)}")
        all_vacancy_urls.update(urls)

    print(f"[+] Totaal unieke vacature-URLs voor '{term}': {len(all_vacancy_urls)}")

    rows = []
    for url in sorted(all_vacancy_urls):
        try:
            row = scrape_vacancy(page, url)
            rows.append(row)
        except Exception as e:
            print(f"    [!] Fout bij vacature {url}: {e}")

    page.close()

    if not rows:
        print(f"[!] Geen vacatures gevonden voor term '{term}'.")
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("UID")
    print(f"[+] DataFrame rows voor '{term}': {len(df)}")
    return df


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )

        all_dfs = []

        for term in SEARCH_TERMS:
            df = scrape_search_term(context, term)
            all_dfs.append(df)

        # Combineer alle zoektermen
        new_df = pd.concat(all_dfs) if any(not d.empty for d in all_dfs) else pd.DataFrame()
        if new_df.empty:
            print("\n[!] Geen enkele vacature gevonden voor alle zoektermen.")
        else:
            new_df = new_df[~new_df.index.duplicated(keep="first")]
            print(f"\n[+] Totaal unieke nieuwe vacatures: {len(new_df)}")

        # Merge met bestaande JSON
        if os.path.exists(JSON_FILE) and not new_df.empty:
            try:
                old = pd.read_json(JSON_FILE, orient="index")
                print(f"[+] Bestaande JSON geladen met {len(old)} rijen.")
            except Exception:
                print("[!] Kon bestaande JSON niet goed lezen, start opnieuw.")
                old = pd.DataFrame()

            if not old.empty:
                old_to_keep = old[~old.index.isin(new_df.index)]
                final_df = pd.concat([old_to_keep, new_df])
            else:
                final_df = new_df
        else:
            final_df = new_df

        if final_df.empty:
            print("\n[!] Geen data om weg te schrijven naar circle8.json.")
        else:
            final_df = final_df[~final_df.index.duplicated(keep="first")]
            final_df.to_json(JSON_FILE, orient="index", indent=2, force_ascii=False)
            print(f"\n[✅] circle8.json bijgewerkt met {len(final_df)} records.")

        browser.close()


if __name__ == "__main__":
    main()
