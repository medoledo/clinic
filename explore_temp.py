import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
try:
    resp = requests.get('https://dalilaldwaa.com/medicine-list', headers=headers)
    print(f"Status Code: {resp.status_code}")
    with open('explore_page.html', 'w', encoding='utf-8') as f:
        f.write(resp.text)
    print("Done writing to explore_page.html")
except Exception as e:
    print(f"Error: {e}")
