from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd
import time
import requests
from urllib.parse import urljoin
import os

# Configuration
BASE_URL = "https://re25.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm"
MAX_THREADS = 5
TOTAL_PAGES = 53  # 1325 exhibitors ÷ 25 per page
LINKS_FILE = "exhibitor_links.txt"
PROGRESS_FILE = "re25_exhibitors_progress.csv"
FINAL_FILE = "re25_exhibitors_complete.csv"

def setup_driver():
    """Configure Chrome WebDriver with optimal settings"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver

def save_links_to_file(links, filename):
    """Save links to a text file"""
    with open(filename, 'w') as f:
        for link in links:
            f.write(link + '\n')

def load_links_from_file(filename):
    """Load links from a text file if it exists"""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return [line.strip() for line in f.readlines()]
    return None

def get_existing_data(filename):
    """Load existing scraped data to resume from where we left off"""
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename)
            return set(df['Detail Page URL'].tolist()), df
        except:
            return set(), pd.DataFrame()
    return set(), pd.DataFrame()

def get_exhibitor_links(driver, page_url):
    """Extract exhibitor detail page links with improved selectors"""
    print(f"Scraping page: {page_url}")
    try:
        driver.get(page_url)
        # Wait for exhibitor elements to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".exhibitor-list, .exhibitor-item, [id*='exhibitor']"))
        )
        
        # Additional wait for dynamic content
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = []
        
        # Multiple selector strategies to find exhibitor links
        selectors = [
            'a[href*="exhibitor-details"]',
            '.exhibitor-name a',
            '.exhibitor-link',
            '[data-exhibitor-id] a'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                if href and 'exhibitor-details' in href:
                    full_url = urljoin(page_url, href)
                    if full_url not in links:
                        links.append(full_url)
        
        print(f"Found {len(links)} exhibitor links on this page")
        return links
        
    except Exception as e:
        print(f"Error scraping page {page_url}: {str(e)}")
        return []

def scrape_exhibitor_detail(driver, detail_url):
    """Scrape detailed information from individual exhibitor page"""
    try:
        driver.get(detail_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract data with multiple fallback strategies
        data = {
            'Exhibitor Name': extract_with_fallback(soup, ['h1', '.exhibitor-title', '[itemprop="name"]']),
            'Website URL': extract_website(soup),
            'Booth Location': extract_with_fallback(soup, ['.booth-number', '.booth-location', '[class*="booth"]']),
            'Contact Info': extract_contact_info(soup),
            'Detail Page URL': detail_url
        }
        
        return data
        
    except Exception as e:
        print(f"Error scraping {detail_url}: {str(e)}")
        return {
            'Exhibitor Name': 'N/A',
            'Website URL': 'N/A',
            'Booth Location': 'N/A',
            'Contact Info': 'N/A',
            'Detail Page URL': detail_url
        }

def extract_with_fallback(soup, selectors):
    """Try multiple selectors for robust data extraction"""
    for selector in selectors:
        element = soup.select_one(selector)
        if element and element.text.strip():
            return element.text.strip()
    return 'N/A'

def extract_website(soup):
    """Extract website URL with multiple strategies"""
    website_selectors = [
        'a[href*="http"]',
        '.website-link',
        '[itemprop="url"]',
        'a[target="_blank"]'
    ]
    
    for selector in website_selectors:
        element = soup.select_one(selector)
        if element and element.get('href'):
            href = element.get('href')
            # Ensure we have a full URL
            if href.startswith('http'):
                return href
            else:
                return urljoin("https://re25.mapyourshow.com", href)
    return 'N/A'

def extract_contact_info(soup):
    """Extract contact information with comprehensive approach"""
    contact_text = ''
    contact_selectors = [
        '.contact-info',
        '.contact-details',
        '[class*="contact"]',
        '.address',
        '.email'
    ]
    
    for selector in contact_selectors:
        elements = soup.select(selector)
        for element in elements:
            if element.text.strip():
                contact_text += element.text.strip() + ' | '
    
    return contact_text[:-3] if contact_text else 'N/A'

def main():
    print("Starting RE+ 2025 exhibitor scraping...")
    
    # Check if we have existing links
    all_exhibitor_links = load_links_from_file(LINKS_FILE)
    
    # If no existing links file, we need to scrape all pages for links
    if all_exhibitor_links is None:
        print("No existing links file found. Scraping all pages for exhibitor links...")
        driver = setup_driver()
        all_exhibitor_links = []
        
        # Build paginated URLs
        page_urls = []
        for page_num in range(1, TOTAL_PAGES + 1):
            page_url = f"{BASE_URL}?featured=false&page={page_num}"
            page_urls.append(page_url)
        
        # Collect all exhibitor links
        for page_url in page_urls:
            links = get_exhibitor_links(driver, page_url)
            all_exhibitor_links.extend(links)
            print(f"Total links collected: {len(all_exhibitor_links)}")
            time.sleep(1)  # Respectful delay between requests
        
        # Save links to file for future use
        save_links_to_file(all_exhibitor_links, LINKS_FILE)
        print(f"Saved {len(all_exhibitor_links)} links to {LINKS_FILE}")
        driver.quit()
    else:
        print(f"Loaded {len(all_exhibitor_links)} existing links from {LINKS_FILE}")
    
    # Check for existing progress
    scraped_urls, exhibitors_df = get_existing_data(PROGRESS_FILE)
    if len(scraped_urls) > 0:
        print(f"Found {len(scraped_urls)} already scraped exhibitors")
    
    # Filter out already scraped URLs
    urls_to_scrape = [url for url in all_exhibitor_links if url not in scraped_urls]
    print(f"{len(urls_to_scrape)} exhibitors remaining to scrape")
    
    if len(urls_to_scrape) == 0:
        print("All exhibitors have already been scraped!")
        # Check if we have a complete file, otherwise save progress as complete
        if not os.path.exists(FINAL_FILE):
            exhibitors_df.to_csv(FINAL_FILE, index=False)
            print(f"Saved complete data to {FINAL_FILE}")
        return
    
    # Setup driver for detail scraping
    driver = setup_driver()
    
    # Scrape detail pages
    for i, link in enumerate(urls_to_scrape):
        print(f"Scraping exhibitor {len(scraped_urls) + i + 1}/{len(all_exhibitor_links)}: {link}")
        data = scrape_exhibitor_detail(driver, link)
        
        # Add to our dataframe
        exhibitors_df = pd.concat([exhibitors_df, pd.DataFrame([data])], ignore_index=True)
        
        # Save progress every 10 records
        if (i + 1) % 10 == 0:
            exhibitors_df.to_csv(PROGRESS_FILE, index=False)
            print(f"Progress saved at {len(scraped_urls) + i + 1} records")
        
        time.sleep(0.5)  # Respectful delay
    
    # Final save
    exhibitors_df.to_csv(FINAL_FILE, index=False)
    print(f"Scraping complete! Saved {len(exhibitors_df)} exhibitors to {FINAL_FILE}")
    
    driver.quit()

if __name__ == "__main__":
    main()