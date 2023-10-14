import json
import sqlite3
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.parser import parse
import logging


logging.basicConfig(
    level=logging.INFO,
    encoding='utf-8',
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logging.debug("Starting application")

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
                    title = entry.title
                except:
                    logging.info("Cannot read title")
                try:
                    description = entry.get('description', '')
                except:
                    logging.info("Cannot read description")
                try:
                    pubdate_text = entry.get('published', '')
                except:
                    logging.info("Cannot read published")
                try:
                    pubdate_datetime = parse(pubdate_text)
                except:
                    logging.info("Cannot parse pubdate")
                
                
                
                # Fetch web page content
                web_page_content = fetch_web_page_content(link)
                
                # Insert RSS feed information into the database
                cursor.execute('''
                    INSERT INTO news (title, description, link, guid, pubdate_text, pubdate, rss_feed_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (title, description, link, guid, pubdate_text, pubdate_datetime, rss_feed_id))
                
                # Insert text content into the text_content table
                cursor.execute('''
                    INSERT INTO text_content (url, content)
                    VALUES (?, ?)
                ''', (link, convert_html_to_text(web_page_content)))
            else:
                logging.info(f"Link already in DB : {link}")
    
    conn.commit()
    conn.close()

# Function to fetch web page content
def fetch_web_page_content(url):
    #if "abcnews" in url:
    #    input(f"abcnews URL : {url}")
    response = requests.get(url)
    if response.status_code == 200:
        #logging.info(response.text)
        return response.text
    else:
        #input(f"Cannot fetch URL content from : {url}")
        return ''

# Function to convert HTML to plain text using BeautifulSoup
def convert_html_to_text(html_content):
    html_text = ""
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
    json_file = 'rss_feeds.json'
    database_name = 'rss_app.db'
    process_rss_feeds(json_file, database_name)
