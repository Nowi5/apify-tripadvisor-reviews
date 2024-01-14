from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions

def get_driver():
    try:
        chrome_options = ChromeOptions()
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"Error initializing the Chrome driver: {e}")

driver = get_driver()
driver.quit()