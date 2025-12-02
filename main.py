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

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--disable-extensions')
options.add_argument('--start-maximized')
# Memory optimization
options.add_argument('--disk-cache-size=1')
options.add_argument('--media-cache-size=1')
options.add_argument('--incognito')
options.add_argument('--remote-debugging-port=9222')
options.add_argument('--aggressive-cache-discard')

service = Service('/usr/local/bin/chromedriver')
    
driver = webdriver.Chrome(service=service, options=options)
driver.get('google.com')

driver.quit()
