import csv
import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin, urlparse
import random
import time
import warnings
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import pandas as pd

# Suppress SSL warnings (only for fallback)
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)

# Set the working directory
path = r'C:\Users\ADMIN\python projects\website_contacts_scraper'
os.chdir(path)

# Input CSV file
input_file = 'US_health_tech_sites.csv'

# List of user agents for rotation
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36'
]

# Patterns
email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
phone_pattern = r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'

def validate_email(email):
    """Validate email with stricter checks."""
    if not re.match(email_pattern, email):
        return False
    local, domain = email.rsplit('@', 1)
    if (len(local) > 64 or len(domain) > 255 or  # RFC 5321 limits
        '..' in local or '..' in domain or
        domain.startswith('.') or domain.endswith('.') or
        not any(c.isalnum() for c in domain) or  # Domain must have letters/numbers
        any(c in '<>[]:;|' for c in email)):  # Avoid special chars
        return False
    return True

def validate_phone(phone):
    """Validate US phone number with stricter checks."""
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return False
    if len(digits) == 10 and all(c.isdigit() for c in digits):
        return True
    elif len(digits) == 11 and digits.startswith('1') and all(c.isdigit() for c in digits[1:]):
        return True
    return False

def clean_phone(match):
    """Clean phone number to standard format if valid."""
    digits = re.sub(r'\D', '', match)
    if len(digits) == 10:
        return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'
    elif len(digits) == 11 and digits.startswith('1'):
        return f'+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}'
    return None

def setup_driver():
    """Set up Selenium WebDriver with options and validate ChromeDriver."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode (no GUI)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
    driver_path = r'C:\Webdriver\chromedriver.exe'
    
    if not os.path.isfile(driver_path):
        raise FileNotFoundError(f"ChromeDriver not found at {driver_path}. Please download it from "
                               "https://chromedriver.chromium.org/downloads and place it in the specified directory. "
                               "Ensure it matches your Chrome version (check via chrome://settings/help).")
    
    service = Service(executable_path=driver_path)
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        raise RuntimeError(f"Failed to initialize ChromeDriver: {e}. Verify compatibility with your Chrome version.") from e

def extract_contacts_from_page(url, site_name, headers, verify_ssl=True, driver=None):
    """Extract emails and phones from a given URL using Selenium or requests."""
    contacts = []
    try:
        if driver:
            # Use Selenium for JS-rendered pages
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
        else:
            # Use requests for static content
            response = requests.get(url, headers=headers, timeout=10, verify=verify_ssl)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

        # Extract emails
        emails = set()
        for a in soup.find_all('a', href=re.compile(r'^mailto:')):
            email = a['href'].replace('mailto:', '').split('?')[0]
            if validate_email(email):
                emails.add(email)
        text_content = ' '.join(soup.stripped_strings)
        found_emails = re.findall(email_pattern, text_content)
        for email in found_emails:
            if validate_email(email):
                emails.add(email)

        for email in emails:
            contacts.append({
                'contact_type': 'email',
                'contact_value': email,
                'source_url': url
            })

        # Extract phones
        phones = set()
        found_phones = re.findall(phone_pattern, text_content)
        for match in found_phones:
            full_match = ''.join([m for m in match if m])
            cleaned = clean_phone(full_match)
            if cleaned and validate_phone(cleaned):
                phones.add(cleaned)

        for phone in phones:
            contacts.append({
                'contact_type': 'phone',
                'contact_value': phone,
                'source_url': url
            })

        # Collect internal links for crawling
        internal_links = set()
        parsed_url = urlparse(url)
        base_domain = parsed_url.netloc
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href)
            parsed_full = urlparse(full_url)
            if parsed_full.netloc == base_domain and parsed_full.scheme in ('http', 'https'):
                if not any(full_url.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif']):
                    internal_links.add(full_url)

        return contacts, internal_links

    except requests.exceptions.SSLError as ssl_err:
        print(f"SSL error for {url}: {ssl_err}. Retrying without SSL verification...")
        if verify_ssl and not driver:
            return extract_contacts_from_page(url, site_name, headers, verify_ssl=False)
        return [], set()
    except requests.exceptions.HTTPError as http_err:
        if '415' in str(http_err) and not driver:
            print(f"HTTP 415 error for {url}. Retrying with adjusted headers...")
            new_headers = headers.copy()
            new_headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            new_headers['Content-Type'] = 'text/html'
            new_headers['Accept-Encoding'] = 'gzip, deflate, br'
            new_headers['Accept-Language'] = 'en-US,en;q=0.5'
            try:
                response = requests.get(url, headers=new_headers, timeout=10, verify=verify_ssl)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                # Extraction logic (abbreviated)
                emails = set()
                for a in soup.find_all('a', href=re.compile(r'^mailto:')):
                    email = a['href'].replace('mailto:', '').split('?')[0]
                    if validate_email(email):
                        emails.add(email)
                text_content = ' '.join(soup.stripped_strings)
                found_emails = re.findall(email_pattern, text_content)
                for email in found_emails:
                    if validate_email(email):
                        emails.add(email)

                for email in emails:
                    contacts.append({
                        'contact_type': 'email',
                        'contact_value': email,
                        'source_url': url
                    })

                phones = set()
                found_phones = re.findall(phone_pattern, text_content)
                for match in found_phones:
                    full_match = ''.join([m for m in match if m])
                    cleaned = clean_phone(full_match)
                    if cleaned and validate_phone(cleaned):
                        phones.add(cleaned)

                for phone in phones:
                    contacts.append({
                        'contact_type': 'phone',
                        'contact_value': phone,
                        'source_url': url
                    })

                internal_links = set()
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    full_url = urljoin(url, href)
                    parsed_full = urlparse(full_url)
                    if parsed_full.netloc == base_domain and parsed_full.scheme in ('http', 'https'):
                        if not any(full_url.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif']):
                            internal_links.add(full_url)

                return contacts, internal_links
            except Exception as e:
                print(f"Retry failed for {url}: {e}")
                return [], set()
        else:
            print(f"HTTP error for {url}: {http_err}")
            return [], set()
    except (requests.RequestException, WebDriverException) as e:
        print(f"Error fetching {url}: {e}")
        return [], set()
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return [], set()

def crawl_site(start_url, site_name, max_links=20, max_depth=2):
    """Crawl a site starting from start_url, up to max_links or max_depth."""
    visited = set()
    to_visit = [(start_url, 0)]  # (url, depth)
    all_contacts = []
    driver = setup_driver()
    headers = {
        'User-Agent': random.choice(user_agents),
        'Referer': 'https://www.google.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.5'
    }

    try:
        while to_visit and len(visited) < max_links:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue

            visited.add(url)
            print(f"  Crawling: {url} (depth {depth})")
            contacts, internal_links = extract_contacts_from_page(url, site_name, headers, driver=driver)
            all_contacts.extend(contacts)

            # Add new internal links to visit, prioritizing contact-related pages
            for link in internal_links:
                if link not in visited and depth + 1 <= max_depth:
                    if any(keyword in link.lower() for keyword in ['contact', 'team', 'staff', 'leadership', 'about']):
                        to_visit.insert(0, (link, depth + 1))  # Prioritize relevant pages
                    else:
                        to_visit.append((link, depth + 1))

            # Rotate user-agent for next request
            headers['User-Agent'] = random.choice(user_agents)

            # Small delay to avoid overwhelming servers
            time.sleep(random.uniform(0.5, 1.5))
    finally:
        driver.quit()  # Ensure driver is closed

    return list({(c['contact_type'], c['contact_value']): c for c in all_contacts}.values())  # Deduplicate

# Read input CSV
sites = []
with open(input_file, 'r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sites.append(row)

# Create a single Excel file with multiple sheets
output_file = 'contacts_all.xlsx'
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    for i, site in enumerate(sites):
        site_name = site['site'].strip().replace(' ', '_').replace('(', '').replace(')', '').replace('.', '_')
        contact_page = site['contact_page'].strip()
        print(f"Scraping {site['site']}: {contact_page}")

        # Crawl site starting from contact page
        contacts = crawl_site(contact_page, site['site'], max_links=20, max_depth=2)

        # Convert contacts to DataFrame and save to a sheet
        if contacts:
            df = pd.DataFrame(contacts)
            sheet_name = site_name[:31]  # Excel sheet names max 31 chars
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"Saved {len(contacts)} unique contact records for {site['site']} to sheet '{sheet_name}'")
        else:
            print(f"No contacts found for {site['site']} (possible block or no extractable data)")

        # Add delay between sites
        if i < len(sites) - 1:
            delay = random.uniform(1, 3)
            print(f"Sleeping for {delay:.2f} seconds...")
            time.sleep(delay)

print("Scraping completed.")
