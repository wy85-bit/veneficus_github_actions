from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import undetected_chromedriver as uc


def go_to_main_page_search_term_data(driver):
    driver.get('https://www.circle8.nl/zoeken?query=data')

def main():
    with uc.Chrome(headless=True, use_subprocess=False) as driver:
        go_to_main_page_search_term_data(driver=driver)

print(driver.title)
with open('./GitHub_Action_Results.txt', 'w') as f:
    f.write(f"This was written with a GitHub action {driver.title}")
    print('test')

if __name__ == "__main__":
        import multiprocessing
        multiprocessing.freeze_support()
        main()


