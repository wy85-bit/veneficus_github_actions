# %%
JSON_FILE = r'C:\Users\WinnieYapVeneficus\OneDrive - Veneficus B.V\yaw\Projecten\VacatureOverzicht\Circle8\circle8.json'

# %%
import undetected_chromedriver as uc
import time
import pandas as pd
import os
from dotenv import load_dotenv
from selenium.webdriver.common.by import By

load_dotenv()

# %%
def go_to_main_page_search_term_data(driver):
    driver.get('https://www.circle8.nl/zoeken?query=data')
    driver.set_window_size(1920, 1080)
    driver.maximize_window()

#%%
def go_to_main_page_search_term_data_engineer(driver):
    driver.get('https://www.circle8.nl/zoeken?query=data%20engineer')
    driver.set_window_size(1920, 1080)
    driver.maximize_window()

#%%
def go_to_main_page_search_term_data_machine_learning_engineer(driver):
    driver.get('https://www.circle8.nl/zoeken?query=machine%20learning%20engineer')
    driver.set_window_size(1920, 1080)
    driver.maximize_window()
# %%
def list_vacancy_links(driver):
    elements = driver.find_elements(By.XPATH, '//div[@class="c-vacancy-list"]//a[starts-with(@href, "/opdracht")]')
    links = [element.get_attribute("href") for element in elements]
    return links

# %%
def list_pagination_links(driver):
    elements = driver.find_elements(By.XPATH, '//div[@class="c-lister-pagination__wrapper"]//a')
    pagination_links = [element.get_attribute("href") for element in elements]
    return pagination_links
#%%
def scrape(driver):
    df_rows = []
    new_df = pd.DataFrame()    
    for page in list_pagination_links(driver):
            print(page)
            driver.get(page)
            time.sleep(2)
            for vacancy in list_vacancy_links(driver):
                driver.get(vacancy)
                time.sleep(2)

                UID = driver.find_element(By.XPATH, '//p[@class="c-vacancy-hero__jobId detail"]').text

                main_information_elements = driver.find_elements(By.XPATH, '//div[@class="c-vacancy-hero__usp-container"]/div/div[count(@*)=0]')
                main_information = [element.text for element in main_information_elements]

                plaats = main_information[0]
                duur = main_information[1]
                uren = main_information[2]
                start = main_information[3]
                deadline = main_information[4]

                vacature_text= driver.find_elements(By.CSS_SELECTOR, 'body > main > div.c-vacancy-paragraph__outer-wrapper.outer-wrapper.background.primary > div > div.c-vacancy-paragraph__text-container > div.c-vacancy-paragraph__body-text.body-text > div:nth-child(1)')
                vacature_text_elements = vacature_text[0].text   
                
                eisen_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Eisen:"]]/ul//li')
                eisen = [element.text for element in eisen_elements]

                wensen_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Wensen:"]]/ul//li')
                wensen = [element.text for element in wensen_elements]

                try:
                    if wensen == []:
                        wensen_elements = driver.find_elements(By.XPATH, '/html/body/main/div[1]/div/div[1]/div[2]/div[3]/ul[2]')
                        wensen = [element.text for element in wensen_elements][0].split('\n')
                except:
                    pass
                
                competenties_elements = driver.find_elements(By.XPATH, '//div[h3[text()="Competenties:"]]/ul//li')
                competenties = [element.text for element in competenties_elements]
                if competenties == []:
                    try:
                         competenties = driver.find_elements(By.XPATH, '//div[h3[text()="Competenties:"]]')[0].text.split('\n')
                    except:
                        pass
                title = driver.find_element(By.XPATH, '/html/body/main/section[2]/div/div/div/div/div[1]/a/h1').text
                row = {
                    "UID": UID,
                    "titel":title,
                    "plaats": plaats,
                    "duur": duur,
                    "uren": uren, 
                    "text":vacature_text_elements,
                    "start": "".join(c for c in start if c.isdigit() or c == '-'),
                    "deadline": "".join(c for c in deadline if c.isdigit() or c == '-'),
                    "eisen": eisen,
                    "wensen": wensen,
                    "competenties": competenties
                }
                df_rows.append(row)
    
    if len(df_rows)>1:
        new_df = pd.DataFrame(df_rows).set_index('UID')

    # MERGE + UPDATE
    return new_df

# %%
def main():
    path_to_json_file = JSON_FILE

    with uc.Chrome(headless=True, use_subprocess=False) as driver:
        go_to_main_page_search_term_data(driver=driver)
        new_df_data = scrape(driver=driver)
        go_to_main_page_search_term_data_engineer(driver=driver)
        new_df_data_engineer = scrape(driver=driver)
        go_to_main_page_search_term_data_machine_learning_engineer(driver=driver)
        new_df_machine_learning_engineer = scrape(driver=driver)
        new_df = pd.concat([new_df_data,new_df_data_engineer,new_df_machine_learning_engineer])
       
    # MERGE + UPDATE
    if os.path.exists(path_to_json_file):
        existing_df = pd.read_json(path_to_json_file, orient="index") # Index is UID
        existing_df_to_keep = existing_df[~existing_df.index.isin(new_df.index)]
        df = pd.concat([existing_df_to_keep, new_df])
    else:
        df = new_df

    print(df)
    df = df.loc[~df.index.duplicated(keep='first'), :]
    df.to_json(path_to_json_file, orient="index", indent=5)

    if len(df) > 0:
            with open("circle8.json", "w", encoding="utf-8") as f:
                f.write(df.to_json(orient="index", indent=4, force_ascii=False))
            print("\n✅ circle8.json geschreven / geüpdatet")
    ]else:
            print("\n⚠️ Geen vacatures gevonden — circle8.json niet weggeschreven (of leeg).")

if __name__ == "__main__":
        import multiprocessing
        multiprocessing.freeze_support()
        main()

# %%

