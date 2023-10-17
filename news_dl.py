import json
import sqlite3
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.parser import parse
import logging
import re
import traceback
from selenium.webdriver.support.ui import WebDriverWait


from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium import webdriver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import html2text

h2t = html2text.HTML2Text()

# Set selenium driver to None
driver = None

logging.basicConfig(
    level=logging.INFO,
    encoding='utf-8',
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Function to initialize the SQLite database and create tables
def initialize_database(database_name):
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    
    # Create the RSS feed information table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rss_feeds (
        rss_feed_id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT
    )
    ''')
    
    # Create the RSS feed information table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rss_feed_id INTEGER,
        title TEXT,
        description TEXT,
        link TEXT,
        guid TEXT,
        pubdate_text DATETIME,
        pubdate DATETIME
    )
    ''')
    
    
    # Create the text content table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS text_content (
        id INTEGER PRIMARY KEY,
        url TEXT,
        content TEXT
    )
    ''')
    
    conn.commit()
    return conn, cursor

# Function to parse RSS feed date and convert it to datetime
def parse_pubdate(pubdate_text):
    try:
        pubdate = datetime.strptime(pubdate_text, '%a, %d %b %Y %H:%M:%S %z')
        return pubdate
    except ValueError:
        return None
        
# Function to fetch and process RSS feeds
def process_rss_feeds(json_file, database_name):
    conn, cursor = initialize_database(database_name)
    rss_feed_id = None
    
    with open(json_file, 'r') as file:
        feed_urls = json.load(file)
    
    for feed_url in feed_urls:
        logging.info(f"Scanning news from {feed_url}")
        feed = feedparser.parse(feed_url)
        
        # Check if the feed URL is already in the database
        cursor.execute('SELECT rss_feed_id FROM rss_feeds WHERE link = ?', (feed_url,))
        existing_entry = cursor.fetchall()
        
        if existing_entry:
            rss_feed_id = existing_entry[0][0]
            logging.info(f"RSS Feed ID: {rss_feed_id}")
        
        # Add RSS feed URL into the database
        else:
            cursor.execute('''
                    INSERT INTO rss_feeds (link)
                    VALUES (?)
                ''', (feed_url,))
        
            # Check if the feed URL is already in the database
            cursor.execute('SELECT rss_feed_id FROM rss_feeds WHERE link = ?', (feed_url,))
            existing_entry = cursor.fetchall()
        
            if existing_entry:
                rss_feed_id = existing_entry[0][0]
                logging.info(f"RSS Feed ID: {rss_feed_id}")
            
            # Add RSS feed URL into the database
            else:
                logging.error("Error adding RSS feed in table rss_feeds")
        
        for entry in feed.entries:
            guid = entry.get('guid', '')
            link = entry.link.lower()
            
            logging.info("Reading news %s" % (entry.get('description', '')))
            # Check if the entry is already in the database
            cursor.execute('SELECT 1 FROM news WHERE link = ?', (link,))
            existing_entry = cursor.fetchone()
            
            if not existing_entry:
                logging.info(f"RSS Feed : {feed_url}")
                logging.info(f"Adding link {link} to the database")
                # Entry is not in the database; fetch web page content
                try:
                    title = None
                    title = entry.title
                except:
                    logging.info("Cannot read title")
                try:
                    description = None
                    description = entry.get('description', '')
                except:
                    logging.info("Cannot read description")
                try:
                    pubdate_text = None
                    pubdate_text = entry.get('published', '')
                except:
                    logging.info("Cannot read published")
                try:
                    pubdate_datetime = None
                    pubdate_datetime = parse(pubdate_text)
                except:
                    logging.info("Cannot parse pubdate")
                
                
                # Fetch web page content
                web_page_content = fetch_web_page_content(link)
                web_page_content = convert_html_to_text(web_page_content)
                web_page_content = re.sub(r' +', ' ', web_page_content)
                web_page_content = re.sub(r'\r', '', web_page_content)
                web_page_content = re.sub(r' +\n', '\n', web_page_content)
                web_page_content = re.sub(r'\n+', '\n', web_page_content)
                web_page_content = re.sub(r'[\r\n]+', '\n', web_page_content)
                
                # Insert RSS feed information into the database
                cursor.execute('''
                    INSERT INTO news (title, description, link, guid, pubdate_text, pubdate, rss_feed_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (title, description, link, guid, pubdate_text, pubdate_datetime, rss_feed_id))
                
                logging.info("Converting HTML to text")
                page_text = convert_html_to_text(web_page_content)
                logging.info("Conversion done")
                # Insert text content into the text_content table
                cursor.execute('''
                    INSERT INTO text_content (url, content)
                    VALUES (?, ?)
                ''', (link, page_text))
                conn.commit()
            else:
                logging.info(f"Link already in DB : {link}")
    
    conn.commit()
    conn.close()

# Function to fetch web page content
def fetch_web_page_content(url):
    global driver
    #if "abcnews" in url:
    #    input(f"abcnews URL : {url}")
    page_source_str = ""
    response = requests.get(url)
    if response.status_code == 200:
        #logging.info(response.text)
        page_source_str =  response.text
    
    # Use chrome browser when the page is empty
    if page_source_str == "":
        if driver is None:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-xss-auditor")
            #chrome_options.add_argument("--verbose")
            chrome_options.add_argument("--log-level=3")  # fatal
            chrome_options.add_argument("--lang=en-GB")
            chrome_options.add_argument('--blink-settings=imagesEnabled=false')
            chrome_options.add_argument('--disable-browser-side-navigation')
            # or alternatively we can set direct preference:
            chrome_options.add_experimental_option(
                "prefs", {"profile.managed_default_content_settings.images": 2}
            )
            
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(5)
            
        try:
            logging.info(f"Loading page {url}")
            
            driver.get(url)
            
            
            logging.info(f"get url done.")
            
            page_source_str = driver.page_source
            #WebDriverWait(driver, 3).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            
            # Fait for the page page to be loaded
            #WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        except:
            var = traceback.format_exc()
            #print(var)
            page_source_str = driver.page_source
        #WebDriverWait(driver, 10).until(EC.presence_of_element_located(driver.execute_script('return document.readyState') == 'complete'))
        logging.info(f"Go to next page...")
    
    return page_source_str

# Function to convert HTML to plain text using BeautifulSoup
def convert_html_to_text(html_content):
    html_text = ""
    
    #try:
    #    html_text = h2t.handle(html_content)
    #    return html_text
    #except:
    #    pass
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        html_text = soup.get_text()
    except:
        pass
        
    try:
        if html_text == "" or html_text is None:
            html_text = html2text.html2text(html_content)
    except:
        pass
        
    if html_text == "" or html_text is None:
        logging.error("ERROR: CANNOT PROCESS HTML")

    return html_text

if __name__ == '__main__':
    logging.debug("Starting application")
    json_file = 'rss_feeds.json'
    database_name = 'rss_app.db'
    process_rss_feeds(json_file, database_name)
