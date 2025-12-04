# %%
import pandas as pd
import time
import undetected_chromedriver as uc
from datetime import datetime
from dotenv import load_dotenv
from selenium.webdriver.common.by import By

#%%
JSON_FILE = r'C:\Users\WinnieYapVeneficus\OneDrive - Veneficus B.V\yaw\Projecten\VacatureOverzicht\BlueTrail\bluetrail_{}.json'.format(datetime.now().strftime('%Y-%m-%d'))

load_dotenv()
# %%
def go_to_page(driver, page_nr):
    driver.get('https://www.bluetrail.nl/opdrachten/page/{}/?srch=data'.format(page_nr+1))
    driver.set_window_size(1920, 1080)
    driver.maximize_window()
    return 'https://www.bluetrail.nl/opdrachten/page/{}/?srch=data'.format(page_nr+1)


def go_to_page_search_term_machine_learning(driver, page_nr):
    driver.get('https://www.bluetrail.nl/opdrachten/?s=machine+learning')
    return 'https://www.bluetrail.nl/opdrachten/?s=machine+learning'

# %%
def list_vacancy_links(driver):
    elements = driver.find_elements(By.CLASS_NAME, "u-job-card")
    links = [element.get_attribute("href") for element in elements]
    return links

def scrape_pages(driver, page):
            print(page)
            driver.get(page)
            time.sleep(5)
            list_rows = []
            for vacancy in list_vacancy_links(driver):
                    driver.get(vacancy)
                    time.sleep(2)

                    title = driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[2]/div/div/div/div[1]/div/div/div[1]/div[2]/h1/span').text

                    try:           
                        show_more_button = driver.find_element(By.XPATH, "/html/body/div[2]/div[2]/div[3]/div/div/div[1]/article/div/a")
                        driver.execute_script("arguments[0].scrollIntoView();", show_more_button)
                        driver.execute_script("scrollBy(0,-100)")
                        show_more_button.click()
                    except:
                        pass
                    UID = driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[2]/div/div/div/div/div[2]/p/span[2]').text
                    plaats = driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[2]/div/div/div/div/div[2]/p/span[3]').text

                    duur = driver.find_element(By.XPATH, '//*[@id="content"]/div[2]/div/div/div/div[1]/div/div/div[1]/div[3]/span[3]').text
                    uren = driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[2]/div/div/div/div/div[2]/p/span[7]').text
                    start = driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[2]/div/div/div/div/div[2]/p/span[4]').text
                    
                    eind = driver.find_element(By.XPATH, '//*[@id="text-4"]/div/div/div[2]/p/span[5]').text
                    deadline = driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[2]/div/div/div/div/div[2]/p/span[9]').text
                    
                    vacature_text=driver.find_element(By.XPATH, '//div[h3]')
                    vacature_text_elements = vacature_text.text
                    try:
                        vacature_text_elements = vacature_text_elements + driver.find_element(By.XPATH, '//div[h3[text()="Functieomschrijving"]]').text
                    except:
                         pass
                    try:
                        vacature_text_elements = vacature_text_elements + driver.find_element(By.XPATH, '//div[h3[text()="Functieomschrijving"]]/ul').text
                    except:
                        vacature_text_elements  = vacature_text_elements
                    
                    eisen_elements = driver.find_elements(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[1]/article/div/div[4]/div/div/ul[1]/li')
                    # eisen _elements = driver.find_elements(By.XPATH, '//div[h3[text()="Eisen:"]]/ul//li')
                    eisen = [element.text for element in eisen_elements]

                    wensen_elements = driver.find_elements(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[1]/article/div/div[4]/div/div/ul[2]/li')
                    wensen = [element.text for element in wensen_elements]

                    competenties_elements = driver.find_elements(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[1]/article/div/div[4]/div/div/ul[3]/li')
                    competenties = [element.text for element in competenties_elements]
                    if competenties == []:
                        try:
                            competenties.append(driver.find_element(By.XPATH, '/html/body/div[2]/div[2]/div[3]/div/div/div[1]/article/div/div[4]/div/div/span').text)
                        except:
                            competenties=competenties

                    row = {
                        "UID": UID,
                        "Referentie-nr": UID,
                        "titel": title,
                        "plaats": plaats,
                        "uren": uren, 
                        "text":vacature_text_elements,
                        "start": start,
                        "eind": eind,
                        "duur": duur,
                        "deadline": deadline,
                        "eisen": eisen,
                        "wensen": wensen,
                        "competenties": competenties
                    }
                    list_rows.append(row)
                    time.sleep(5)
            return list_rows

# %%
def main():
    path_to_json_file = JSON_FILE
    with uc.Chrome(headless=False, use_subprocess=False) as driver:
        data_search_term_data_total = []
        machine_learning_search_term_data_total = []
        for i in range(5):
            go_to_page(driver,i)
            page = go_to_page(driver,i)
            data_search_term_data = scrape_pages(driver, page)
            data_search_term_data_total.append(data_search_term_data)
        for i in range(2):
            page_search_term_machine_learning = go_to_page_search_term_machine_learning(driver,i)
            driver.get(page_search_term_machine_learning)
            time.sleep(5)
            machine_learning_search_term_data = scrape_pages(driver, page_search_term_machine_learning)
            machine_learning_search_term_data_total.append(machine_learning_search_term_data)

    data_search_term_data_total.append(machine_learning_search_term_data_total)
    new_df = pd.DataFrame()
    for j in range(len(data_search_term_data_total)):
        new_df = pd.concat([new_df, pd.DataFrame(data_search_term_data_total[j])])
    
    new_df.set_index('UID')
    
    print(new_df)
    df = new_df.drop_duplicates('UID').set_index('UID')
    df=df.loc[:,['Referentie-nr',
                 'titel',
                 'plaats',
                 'uren',
                 'text',
                 'start',
                 'eind', 
                 'duur',     
                 'deadline',         
                 'eisen',
                 'wensen',  
                 'competenties']]
    
    df.to_json(path_to_json_file, orient="index", indent=4)

    
if __name__ == "__main__":
        import multiprocessing
        multiprocessing.freeze_support()
        main()

