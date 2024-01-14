from urllib.parse import urljoin

import requests
import time
import re
import json
import os
import subprocess
import configparser
import uuid
import socket
from bs4 import BeautifulSoup

import time
from python_anticaptcha import AnticaptchaClient, NoCaptchaTaskProxylessTask

from apify import Actor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# To run this Actor locally, you need to have the Selenium Chromedriver installed.
# https://www.selenium.dev/documentation/webdriver/getting_started/install_drivers/
# When running on the Apify platform, it is already included in the Actor's Docker image.

# Parameters

LOOP_MAX = 40
SCROLL_INCREMENT = 600  # This value might need adjusting depending on the website

STORAGE_PATH = "storage"
PATHS = {
    'storage': STORAGE_PATH,
    'captures': os.path.join(STORAGE_PATH, "captures"),
    'mitmdump': os.path.join(STORAGE_PATH, "mitmdump"),
    'stdout_log_file' : '',
    'stderr_log_file' : '',
    'captured_file': '',
    'error_file': ''
}

async def main():
    async with Actor:      
        
        actor_input = await Actor.get_input() or {}
        urls = actor_input.get('urls', 'https://www.tripadvisor.com/ShowUserReviews-g1-d8729116-r933887478-Malaysia_Airlines-World.html')

        if not urls:
            Actor.log.info('No URLs specified in actor input, exiting...')
            await Actor.exit()
        
        # Enqueue the starting URLs in the default request queue
        default_queue = await Actor.open_request_queue()
        for urlo in urls:
            url = urlo.get('url')
            Actor.log.info(f'Enqueuing {url} ...')
            await default_queue.add_request({ 'url': url})
        
        while request := await default_queue.fetch_next_request():
            url = request['url']
            Actor.log.info(f'Processing {url} ...')

            unique_id = str(uuid.uuid4())
            Actor.log.info("Using unique id: "+str(unique_id))

            paths = update_paths(unique_id)
            # Start the MITM proxy
            proxy_port = find_open_port()
            Actor.log.info("Using proxy port: "+str(proxy_port))
            mitm_process = start_mitmproxy(unique_id, proxy_port)

            # Load website
            driver = get_driver(proxy_port)
            await process_website(driver, url) 
                    
            driver.quit()
            stop_mitmproxy(mitm_process)
            await process_capture(unique_id)
            clean_files()
        
        Actor.log.info(f'Processing done ...')
        clean_files()

def ensure_directory_exists(directory: str):
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def update_paths(unique_id: str):

    PATHS['stdout_log_file']    = os.path.join(PATHS['mitmdump'], f'mitmdump_stdout_{unique_id}.log')
    PATHS['stderr_log_file']    = os.path.join(PATHS['mitmdump'], f'mitmdump_stderr_{unique_id}.log')
    PATHS['captured_file']      = os.path.join(PATHS['captures'], f"captured_requests_{unique_id}.txt")
    PATHS['error_file']         = os.path.join(PATHS['captures'], f"errors_{unique_id}.txt")

    # List of directory paths to ensure exist
    directories_to_ensure = [
        PATHS['storage'],
        PATHS['captures'],
        PATHS['mitmdump'],
    ]

    # Ensure directories exist
    for directory in directories_to_ensure:
        ensure_directory_exists(directory)

    return PATHS

async def process_website(driver, url):     

    driver.get(url)
    time.sleep(3)
    keep_going = True

    actor_input = await Actor.get_input() or {}
    max_pages = actor_input.get('max_pages', 3)
    pages_processed = 0

    while keep_going and pages_processed < max_pages:
        process_page(driver)
        pages_processed += 1

        # Check for next page
        if pages_processed < max_pages:  # Only look for next page if the max limit hasn't been reached
            try:
                scroll_to_bottom(driver)
                next_button = driver.find_element(By.CSS_SELECTOR, 'a.nav.next')
                next_button.click()

                # Wait for the text "Updating list..." to be invisible
                wait = WebDriverWait(driver, 10)  # 10 is the timeout in seconds
                wait.until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(text(), 'Updating list...')]")))

            except NoSuchElementException:
                time.sleep(30)
                Actor.log.info("Next page button not found.")
                keep_going = False
        else:
            Actor.log.info("Reached the maximum number of pages to process.")
            keep_going = False

    return



def process_page(driver):  

    url = driver.current_url
    title = driver.title
    check_captcha(driver)
    try:
        # wait to load the page
        element_present = EC.presence_of_element_located((By.ID, 'taplc_location_reviews_list_sur_0'))
        WebDriverWait(driver, 10).until(element_present)
        time.sleep(2)
    except TimeoutException:
        Actor.log.error("The expected element did not appear in the specified time! Closing the driver...")
        time.sleep(30)
        return       

    scroll_to_bottom(driver)

    item_elements = driver.find_elements(By.CSS_SELECTOR, 'div[id^="review_"]')
    item_wrappers = [item.get_attribute('outerHTML') for item in item_elements]

    # Get the count of items and log them
    item_count = len(item_wrappers)
    Actor.log.info(f'Webscraper located {item_count} items.')

    # Loop through and process each div (which is now the HTML content of each item)
    for item_html in item_wrappers:
        item_data = extract_item_data(item_html)
        if item_data is not None:
            Actor.push_data(item_data)

def extract_item_data(item_html):
    data = {}
    soup = BeautifulSoup(item_html, 'html.parser')

    # Extracting the review ID
    review_id_tag = soup.find(attrs={"data-reviewid": True})
    data['review_id'] = review_id_tag['data-reviewid'] if review_id_tag else 'Review ID Not Found'

    # Extracting the title
    title_tag = soup.find('span', class_='noQuotes')
    data['title'] = title_tag.text if title_tag else 'Title Not Found'

    # Extracting the link behind the title
    link_tag = soup.find('a', id=lambda x: x and x.startswith('rn'))
    data['link'] = 'https://www.tripadvisor.com' + link_tag['href'] if link_tag else 'Link Not Found'

    # Extracting the text
    text_tag = soup.find('p', class_='partial_entry')
    data['text'] = text_tag.text if text_tag else 'Text Not Found'

    # Extracting the date
    date_tag = soup.find('span', class_='ratingDate')
    data['date'] = date_tag['title'] if date_tag else 'Date Not Found'

    # Extracting rating-list items and ratings
    ratings = {}
    for li in soup.select('.rating-list .recommend-answer'):
        description = li.find('div', class_='recommend-description')
        rating = li.find('div', class_='ui_bubble_rating')
        if description and rating:
            description_key = description.text.replace(' ', '_')
            ratings[description_key] = rating['class'][1]

    # Extracting overall rating
    overall_rating_tag = soup.find('span', class_='ui_bubble_rating')
    data['rating'] = overall_rating_tag['class'][1] if overall_rating_tag else 'Overall Rating Not Found'

    return data

def scroll_to_bottom(driver):
    loop_count = 0
    loop_max = LOOP_MAX
    while True:
        current_position = driver.execute_script("return window.pageYOffset;")
        driver.execute_script(f"window.scrollTo(0, {current_position + SCROLL_INCREMENT});")
        time.sleep(1)
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        # Check if we've reached the bottom of the page
        if current_position == driver.execute_script("return window.pageYOffset;"):
            break

        if loop_count >= loop_max:
            break

        loop_count += 1

def check_captcha(driver):
    # TODO: Check for captcha specific for this website Tripadvisor
    # Check fo catpcha
    captcha = driver.find_elements(By.CSS_SELECTOR, '.captcha-container')
    if captcha:
        msg = "Captcha detected! Exiting..."
        Actor.log.error(f"An error occurred: {msg}")

def get_driver(proxy_port = 8080):
    # Launch a new Selenium Chrome WebDriver
    Actor.log.info('Launching Chrome WebDriver...')
    service = Service(ChromeDriverManager().install())
    chrome_options = ChromeOptions()
    #    if Actor.config.headless:
    #        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    PROXY = "localhost:" + str(proxy_port)
    chrome_options.add_argument(f"--proxy-server={PROXY}")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver

async def process_capture(unique_id):
    # No need to process captured file for this scraper
    # captured_file_path = PATHS['captured_file']    
    return

async def process_items(data, dataset):
    if not isinstance(data, dict):
        Actor.log.warning("Expected data to be a dictionary but received a %s", type(data))
        return
    
    try:
        # Check the status_code in the JSON data
        status_code = data.get('status_code')
        if status_code != 200:
            Actor.log.warning("Error in capture with status code: %s", status_code)
            Actor.log.debug(data)
            return

        await dataset.push_data(data.get('data'))
    except Exception as e:
        Actor.log.warning("Error while processing items: %s", str(e))

def find_open_port(start_port=8080):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            socket_result = s.connect_ex(('localhost', port))
            if socket_result == 0:  # port is already in use
                port += 1
            else:
                return port

def start_mitmproxy(unique_id, port = 8080):
    # Ensure data folder exists or create it
    data_folder = PATHS['storage']
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)   

    # Set path to the mitmdump script inside the data folder
    dump_script_path = os.path.join("src", "save_requests.py")

    # Define paths for stdout and stderr logs
    stdout_log_path = PATHS['stdout_log_file']
    stderr_log_path = PATHS['stderr_log_file']

    # Start mitmdump with the specified port
    with open(stdout_log_path, 'w') as stdout_file, open(stderr_log_path, 'w') as stderr_file:
        cmd = f'mitmdump --quiet -p {port} -s {dump_script_path} {unique_id} > {stdout_log_path} 2> {stderr_log_path}'
        process = subprocess.Popen(cmd, shell=True)

    time.sleep(3)

    # Check the stderr log for errors
    with open(stderr_log_path, 'r') as stderr_file:
        error_output = stderr_file.read()
        if "Address already in use" in error_output:
            raise Exception("Another process is already using the required port. Make sure mitmproxy isn't already running.")
        elif "Error" in error_output:
            raise Exception(f"Error starting mitmproxy: {error_output}")

    return process

def stop_mitmproxy(process):
    try:
        # Send a SIGTERM signal to the process
        process.terminate()
        # Wait for up to 5 seconds for the process to terminate
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # If the process doesn't terminate within the timeout, forcibly kill it
        process.kill()
    Actor.log.info("Mitmproxy stopped.")

def is_valid_json(s):
    try:
        json.loads(s)
        return True
    except ValueError:
        return False
    
def clean_files():
    Actor.log.info("Cleaning up files...")
    delete_files(PATHS['stdout_log_file'], PATHS['stderr_log_file'], PATHS['captured_file'], PATHS['error_file'])

def delete_files(*file_paths):
    """Delete files specified by their paths."""
    for path in file_paths:
        try:
            os.remove(path)
            #Actor.log.info(f"Successfully deleted {path}")
        except FileNotFoundError:
            Actor.log.warning(f"{path} not found.")
        except Exception as e:
            Actor.log.warning(f"Error deleting {path}: {e}")