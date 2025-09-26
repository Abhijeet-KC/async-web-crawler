import os
import json
import aiohttp
import asyncio
from markdownify import markdownify as md
from datetime import datetime

# Configuration Variables
CRAWL_DEPTH = 1
ALLOWED_DOMAIN = "jeevee.com"
PAGES_PER_SEED = 5
MAX_PAGES = 20
BLOCKED_PAGES_FULL = set()
BLOCK_PATTERNS = []

OUTPUT_DIR = "output/MDs"
LOG_FILE = "crawlLog.txt"
INDEX_FILE = "output/index.jsonl"

# Read seeds from file
with open("seeds.txt") as f:
    seeds = [line.strip() for line in f.readlines() if line.strip()]

# Fetch functions
async def fetch(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            html = await response.text()
            print(f"Fetched {url} with status {response.status}") 
            return html, response.status
        
    except Exception as e:
        print(f"Failed to fetch {url}: {e}") 
        return None, str(e)
    
# Crawl function
async def crawl_seed(seed_url):
    print(f"Start crawling {seed_url}")
    async with aiohttp.ClientSession() as session:
        html, status = await fetch(session, seed_url)
        timestamp = datetime.now().isoformat()
        
        if html:
            # Convert HTML to Markdown
            markdown_content = md(html)
            
            # Generate filename from URL
            filename = seed_url.replace("https://", "").replace("/", "_") + ".md"
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Log success
            with open(LOG_FILE, "a") as log:
                log.write(f"{timestamp} | {seed_url} | SUCCESS\n")

            # Update JSON index
            index_entry = {
                "url": seed_url,
                "file": filename,
                "status": "SUCCESS",
                "timestamp": timestamp
            }
            with open(INDEX_FILE, "a") as idx:
                idx.write(json.dumps(index_entry) + "\n")
                
        else:
            # Log failure
            with open(LOG_FILE, "a") as log:
                log.write(f"{timestamp} | {seed_url} | FAILED | {status}\n")

# Running crawler
async def main():
    for seed in seeds:
        await crawl_seed(seed)
        
if __name__ == "__main__":
    asyncio.run(main())