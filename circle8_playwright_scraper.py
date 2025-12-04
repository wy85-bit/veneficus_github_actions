import os
import time
import hashlib
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

JSON_FILE = "./circle8.json"
ASSIGNMENTS_URL = "https://www.circle8.nl/opdrachten/dynamic-vacatures"


def uid_from_url(url: str) -> str:
    return "UID-" + hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def apply_stealth(page):
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['nl-NL','nl'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
        window.chrome = { runtime: {} };
    """)


def collect_all_vacancy_urls(page) -> list[str]:
    """Haalt alle 'Bekijk opdracht'-links van de opdrachtenpagina."""
    print(f"[+] Open opdrachtenpagina: {ASSIGNMENTS_URL}")
    page.goto(ASSIGNMENTS_URL, wait_until="networkidle", timeout=30000)

    # Scroll een paar keer voor de zekerheid
    for _ in range(8):
        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(300)

    # Alle links met tekst 'Bekijk opdracht'
    buttons = page.locator("a:has-text('Bekijk opdracht')")
    count = buttons.count()
    print(f"[+] Aantal 'Bekijk opdracht'-links gevonden: {count}")

    urls = set()
    for i in range(count):
        href = buttons.nth(i).get_attribute("href")
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.circle8.nl" + href
        if "/opdracht" in href:
            urls.add(href)

    urls = sorted(urls)
    print(f"[+] Unieke vacature-URLs: {len(urls)}")
    for u in urls:
        print("    -", u)

    return urls


def scrape_vacancy(page, url: str) -> dict:
    print(f"    [*] Scrape vacature: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1000)
    page.mouse.wheel(0, 1500)
    page.wait_for_timeout(500)

    try:
        title = page.locator("h1").first.inner_text().strip()
    except PlaywrightTimeoutError:
        title = ""

    try:
        main_text = page.locator("main").inner_text().strip()
    except PlaywrightTimeoutError:
        main_text = page.content()[:4000]

    uid = uid_from_url(url)

    return {
        "UID": uid,
        "titel": title,
        "text": main_text,
        "url": url,
    }


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()
        apply_stealth(page)

        urls = collect_all_vacancy_urls(page)

        if not urls:
            print("[!] Geen enkele vacature-URL gevonden. circle8.json wordt niet aangepast.")
            browser.close()
            return

        rows = []
        for url in urls:
            try:
                row = scrape_vacancy(page, url)
                rows.append(row)
            except Exception as e:
                print(f"    [!] Fout bij vacature {url}: {e}")

        if not rows:
            print("[!] Geen vacatures succesvol gescraped. circle8.json wordt niet aangepast.")
            browser.close()
            return

        new_df = pd.DataFrame(rows).set_index("UID")
        print(f"[+] Nieuwe scrapes (uniek): {len(new_df)}")

        # Merge met bestaande JSON
        if os.path.exists(JSON_FILE):
            try:
                old_df = pd.read_json(JSON_FILE, orient="index")
                print(f"[+] Bestaande JSON geladen met {len(old_df)} rijen.")
            except Exception:
                print("[!] Kon bestaande JSON niet lezen, start opnieuw.")
                old_df = pd.DataFrame()

            if not old_df.empty:
                # oude rijen behouden die nog niet in new_df zitten
                to_keep = old_df[~old_df.index.isin(new_df.index)]
                final_df = pd.concat([to_keep, new_df])
            else:
                final_df = new_df
        else:
            final_df = new_df

        final_df = final_df[~final_df.index.duplicated(keep="first")]
        final_df.to_json(JSON_FILE, orient="index", indent=2, force_ascii=False)
        print(f"[✅] circle8.json bijgewerkt met {len(final_df)} records.")

        browser.close()


if __name__ == "__main__":
    main()
