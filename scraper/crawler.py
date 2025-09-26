import os
import json
import aiohttp
import asyncio
from markdownify import markdownify as md
from datetime import datetime
from bs4 import BeautifulSoup

# Configuration Variables
CRAWL_DEPTH = 1
ALLOWED_DOMAIN = "kiec.edu.np"
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
visited_urls = set()
total_pages_crawled = 0

async def crawl_seed(seed_url, depth=0):
    global total_pages_crawled

    if total_pages_crawled >= MAX_PAGES or depth > CRAWL_DEPTH or seed_url in visited_urls:
        return

    visited_urls.add(seed_url)
    print(f"Crawling (depth {depth}): {seed_url}")

    async with aiohttp.ClientSession() as session:
        html, status = await fetch(session, seed_url)
        timestamp = datetime.now().isoformat()

        if html:
            # Convert HTML to Markdown
            markdown_content = md(html)
            
            # Add metadata header
            metadata = f"---\nurl: {seed_url}\ntimestamp: {timestamp}\nstatus: SUCCESS\n---\n\n"
            markdown_content = metadata + markdown_content
            
            # Generate filename from URL
            filename = seed_url.replace("https://", "").replace("http://", "").replace("/", "_") + ".md"
            
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
                "timestamp": timestamp,
                "seed_origin": seed_url if depth==0 else "from_link"
            }
            with open(INDEX_FILE, "a") as idx:
                idx.write(json.dumps(index_entry) + "\n")

            total_pages_crawled += 1

            # Find links
            links = [a.get("href") for a in BeautifulSoup(html, "html.parser").find_all("a", href=True)]
            valid_links = [link for link in links if ALLOWED_DOMAIN in link and link not in visited_urls]

            for link in valid_links[:PAGES_PER_SEED]:
                await crawl_seed(link, depth + 1)
                
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