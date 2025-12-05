import undetected_chromedriver as uc
import time
import pandas as pd
from datetime import datetime
import os
from selenium.webdriver.common.by import By


OUTPUT_FILE = f'striive_{datetime.now().strftime("%Y-%m-%d")}.json'


def login(driver):
    time.sleep(2)

    email = driver.find_element(By.ID, 'email')
    email.send_keys(os.getenv("STRIIVE_EMAIL"))

    pw = driver.find_element(By.ID, 'password')
    pw.send_keys(os.getenv("STRIIVE_PASSWORD"))

    button = driver.find_element(By.XPATH, '/html/body/app-root/app-landing/div/app-login/div/div[1]/form/button')
    button.click()
    time.sleep(2)


def go_to_page(driver):
    url = 'https://supplier.striive.com/inbox/all?searchTerm=data'
    driver.get(url)
    driver.set_window_size(1920, 1080)
    login(driver)
    return url


def get_demands(driver):
    demands_list = []
    for r in range(20):
        try:
            demands_list.append(driver.find_element(
                By.XPATH,
                f'//app-job-request-details//section[3]//div/ul/li[{r}]'
            ).text)
        except:
            continue
    return demands_list


def get_wishes(driver):
    wishes_list = []
    for r in range(20):
        try:
            wishes_list.append(driver.find_element(
                By.XPATH,
                f'//app-job-request-details//section[3]/div[2]/ul/li[{r}]/app-skill-chip/p-chip/div/span/span'
            ).text)
        except:
            continue
    return wishes_list


def main():
    rows = []
    counter = 0

    with uc.Chrome(headless=True) as driver:
        page = go_to_page(driver)
        time.sleep(2)

        # FIRST BLOCK
        for j in range(1, 5):
            try:
                element = driver.find_element(
                    By.XPATH,
                    f'//app-job-request-list-item[{j}]'
                )
                driver.execute_script("arguments[0].scrollIntoView();", element)
                element.click()
                time.sleep(2)

                try:
                    text = driver.find_element(By.XPATH, '//section[4]/p').text
                except:
                    text = driver.find_element(By.XPATH, '//section[5]/p').text

                row = extract_row(driver, counter, text)
                rows.append(row)
                counter += 1

            except:
                continue

        # SECOND BLOCK
        for i in range(9):
            for j in range(5, 10):
                try:
                    element = driver.find_element(
                        By.XPATH,
                        f'//app-job-request-list-item[{j}]'
                    )
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    element.click()
                    time.sleep(2)

                    try:
                        text = driver.find_element(By.XPATH, '//section[5]/p').text
                    except:
                        text = driver.find_element(By.XPATH, '//section[4]/p').text

                    row = extract_row(driver, counter, text)
                    rows.append(row)
                    counter += 1

                except:
                    continue

    df = pd.DataFrame(rows).drop_duplicates(subset=["referentie_code"])
    df.to_json(OUTPUT_FILE, orient="index", indent=4)
    print(f"JSON saved to: {OUTPUT_FILE}")


def extract_row(driver, uid, text):
    return {
        "UID": uid,
        "referentie_code": driver.find_element(By.XPATH, '//*/div/div[9]/span[2]').text,
        "vacature": driver.find_element(By.XPATH, '//header//div[2]').text,
        "plaats": driver.find_element(By.XPATH, '//section[2]/div[1]/div[2]/span[2]').text,
        "uren": driver.find_element(By.XPATH, '//section[2]/div[1]/div[1]/span[2]').text,
        "text": text,
        "start": "".join(c for c in driver.find_element(By.XPATH, '//section[2]/div[2]/div[1]/span[2]').text if c.isdigit() or c == '-'),
        "eind": driver.find_element(By.XPATH, '//*/div/div[3]/span[2]').text,
        "deadline": "".join(c for c in driver.find_element(By.XPATH, '//section[2]/div[2]/div[2]/span[2]').text if c.isdigit() or c == '-'),
        "eisen": get_demands(driver),
        "wensen": get_wishes(driver),
    }


if __name__ == "__main__":
    main()
