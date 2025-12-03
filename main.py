from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def test_example():
    options = Options()
    options.add_argument("--headless=new")   # Headless voor CI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.get("https://www.example.com")
    assert "Example Domain" in driver.title

    driver.quit()

if __name__ == "__main__":
    test_example()
