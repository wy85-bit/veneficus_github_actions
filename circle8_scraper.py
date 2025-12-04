# circle8_scraper.py
# This is the full scraper with fallback selectors.

import os, time, json, traceback
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

JSON_FILE="circle8.json"
TIMEOUT=25

SAFE_SELECTORS=[
    '//a[contains(@href,"/opdracht")]',
    '//a[contains(@class,"vacancy-lister-item")]',
    '//div[contains(@class,"c-card-vacancy")]',
    '//article[contains(@class,"vacancy-card")]',
    '//div[contains(@class,"vacancy-lister")]'
]

def wait_for_any(driver, selectors, timeout=25):
    for xp in selectors:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            print("Detected selector:", xp)
            return xp
        except:
            pass
    raise TimeoutException("No vacancy selectors detected.")

def create_driver():
    proxy=os.getenv("PROXY","")
    options=uc.ChromeOptions()
    options.binary_location="/usr/bin/google-chrome"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    if proxy:
        options.add_argument(f"--proxy-server={proxy}")
    driver=uc.Chrome(options=options, headless=False, use_subprocess=True)
    return driver

def scrape_search_term(driver, term):
    url=f"https://www.circle8.nl/zoeken?query={term.replace(' ','%20')}"
    driver.get(url)
    wait_for_any(driver, SAFE_SELECTORS, TIMEOUT)
    links=set()
    for sel in SAFE_SELECTORS:
        els=driver.find_elements(By.XPATH, sel)
        for e in els:
            href=e.get_attribute("href")
            if href and "/opdracht" in href:
                links.add(href)
    print("Vacatures gevonden:", len(links))
    rows=[]
    for v in links:
        try:
            driver.get(v)
            time.sleep(2)
            title=driver.find_element(By.TAG_NAME,"h1").text
            text=driver.page_source[:5000]
            rows.append({"UID":abs(hash(v)),"title":title,"url":v,"raw":text})
        except Exception as e:
            print("Error vacature:",v,e)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("UID")

def main():
    d=create_driver()
    try:
        df1=scrape_search_term(d,"data")
        df2=scrape_search_term(d,"data engineer")
        df3=scrape_search_term(d,"machine learning engineer")
        df=pd.concat([df1,df2,df3])
        if not df.empty:
            df.to_json(JSON_FILE,indent=2,orient="index")
            print("Saved",JSON_FILE)
    finally:
        try: d.quit()
        except: pass

if __name__=="__main__":
    main()
