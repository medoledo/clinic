import os

scraper_code = """import time
import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def extract_drugs():
    print("Fetching total pages...")
    total_pages = 2270
    try:
        resp = requests.get('https://dalilaldwaa.com/medicine-list?page=1', headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        page_links = soup.select('.pagination .page-item a.page-link')
        for a in page_links:
            if a.text.isdigit():
                val = int(a.text)
                if val > total_pages:
                    total_pages = val
    except Exception as e:
        print("Failed to dynamically fetch total pages, using default 2270:", e)

    drugs = set()
    output_file = 'egyptian_drugs.txt'
    
    for page in range(1, total_pages + 1):
        try:
            resp = requests.get(f'https://dalilaldwaa.com/medicine-list?page={page}', headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"Error on page {page}: Status {resp.status_code}")
                time.sleep(1)
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select('.cm-item .col-md-7')
            if not items:
                print(f"No items found on page {page}. Stopping.")
                break
                
            for item in items:
                links = item.find_all('a')
                if links:
                    name = links[-1].get_text(strip=True)
                    if name:
                        drugs.add(name)
                        
            print(f"Page {page}/{total_pages} — {len(drugs)} drugs collected so far")
            
        except Exception as e:
            print(f"Exception on page {page}: {e}")
            
        time.sleep(1)
        
    sorted_drugs = sorted(list(drugs))
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for d in sorted_drugs:
                f.write(d + '\\n')
        print(f"Done. Total unique drugs: {len(sorted_drugs)} — saved to {output_file}")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == '__main__':
    extract_drugs()
"""

with open('scrape_drugs.py', 'w', encoding='utf-8') as f:
    f.write(scraper_code)
print("scrape_drugs.py has been created correctly.")
