A Python-based scraper to extract **business contact details** (emails, phone numbers, source URLs) from US healthcare technology websites.  
The scraper normalizes and validates extracted data, then saves clean outputs into structured CSV/Excel files for outreach campaigns.  

---

 Features
- Scrapes **names, emails, phone numbers, websites** from targeted health tech websites  
-  Supports static and dynamic content (`requests`, `BeautifulSoup`, `Selenium`)  
-  Cleans and validates emails (RFC compliance) and phone numbers (E.164 format)  
-  Consolidates results into **Excel with one sheet per site**  
-  Customizable to any industry or niche beyond healthcare  

---
 Project Structure
.
├── scraper.py # Main scraper script
├── requirements.txt # Dependencies
├── data/
│ ├── raw/ # Raw scraped files
│ └── processed/ # Clean, validated outputs
├── results/
│ ├── contacts_all.xlsx # Final consolidated contacts
│ └── contacts_us_health.csv
└── README.md # Project documentation


 Installation
   Clone this repo and install dependencies:

    git clone https://github.com/josephodera/website-contact-scraper.git
    cd website-contact-scraper
pip install -r requirements.txt
**Usage**
  Run the scraper on a set of websites:

  python scraper.py --input sites_list.csv --output results/contacts_all.xlsx
  input: CSV with target websites (one per row)

 output: Path to save consolidated results

**Technologies Used**
   Python 3.x

   Requests / BeautifulSoup4

   Selenium (for JavaScript-heavy pages)

   Pandas / OpenPyXL (Excel automation)

   Regex (email & phone validation)

