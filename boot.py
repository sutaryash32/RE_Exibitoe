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

# Configuration
BASE_URL = "https://re25.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm"
MAX_THREADS = 5
TOTAL_PAGES = 53  # 1325 exhibitors ÷ 25 per page

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
            return element.get('href')
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
    
    print(f"Final count: {len(all_exhibitor_links)} exhibitor links found")
    
    # Scrape detail pages
    exhibitors_data = []
    for i, link in enumerate(all_exhibitor_links):
        print(f"Scraping exhibitor {i+1}/{len(all_exhibitor_links)}")
        data = scrape_exhibitor_detail(driver, link)
        exhibitors_data.append(data)
        
        # Save progress every 50 records
        if (i + 1) % 50 == 0:
            df = pd.DataFrame(exhibitors_data)
            df.to_csv('re25_exhibitors_progress.csv', index=False)
            print(f"Progress saved at {i+1} records")
        
        time.sleep(0.5)  # Respectful delay
    
    # Final save
    df = pd.DataFrame(exhibitors_data)
    df.to_csv('re25_exhibitors_complete.csv', index=False)
    print(f"Scraping complete! Saved {len(exhibitors_data)} exhibitors to CSV")
    
    driver.quit()

if __name__ == "__main__":
    main()
    
    