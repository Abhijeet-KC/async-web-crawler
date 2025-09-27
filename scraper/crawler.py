import os
import json
import aiohttp
import asyncio
import logging
from markdownify import markdownify as md
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urldefrag
import re

CAPTCHA_DIR = "output/captcha_pages"
os.makedirs(CAPTCHA_DIR, exist_ok=True)
    
def normalize_url(url, base=None):
    """Normalize URL: resolve relative links, remove fragments, lowercase.""" 
    if base:
        url = urljoin(base, url)
    url, _ = urldefrag(url) 
    return url.strip().lower()

# Configuration Variables
CRAWL_DEPTH = 1
ALLOWED_DOMAIN = ["jeevee.com", "kiec.edu.np", "prettyclickcosmetics.com", "tranquilityspa.com.np"]
PAGES_PER_SEED = 5
MAX_PAGES = 20
BLOCKED_PAGES_FULL = set()  
BLOCK_PATTERNS = []  

ALLOW_INSECURE = False       
POLITE_DELAY = 1            

OUTPUT_DIR = "output/MDs"
LOG_FILE = "crawlLog.txt"
INDEX_FILE = "output/index.jsonl"

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(ch)
    logger.addHandler(fh)

# Read seeds from file
with open("seeds.txt") as f:
    seeds = [line.strip() for line in f.readlines() if line.strip()]

# Fetch functions
async def fetch(session, url, retries=2, delay=2):
    """Fetch a URL with retries on failure."""
    for attempt in range(retries + 1):
        try:
            async with session.get(url, timeout=10) as response:
                html = await response.text()
                logger.info(f"Fetched {url} (status {response.status})")
                return html, response.status
        except Exception as e:
            if attempt < retries:
                logger.warning(f"Retry {attempt+1}/{retries} for {url}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to fetch {url} after {retries+1} attempts: {e}")
                return None, str(e)

# Crawl function
visited_urls = set()
total_pages_crawled = 0
failed_captcha_urls = set()

async def save_captcha_evidence(html, url, page_obj=None):
    """Detect common captcha signs and return True if detected."""
    if not html:
        return False

    lower = html.lower()
    keywords = ["captcha", "recaptcha", "h-captcha", "are you human", "verify you", 
                "just a moment", "bot verification", "checking your browser", "cloudflare"]

    detected = any(k in lower for k in keywords)
    
    if not detected:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for img in soup.find_all("img", src=True):
                if "captcha" in img["src"].lower():
                    detected = True
                    break
        except Exception:
            pass

    if detected and url not in failed_captcha_urls:
        failed_captcha_urls.add(url)
        logger.warning(f"CAPTCHA detected at {url}")
    return detected

def is_url_allowed(url):
    """Check if a URL is allowed based on blocklists and domain."""
    if url in BLOCKED_PAGES_FULL:
        return False
    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, url):
            return False
    parsed = urlparse(url)
    return parsed.netloc in ALLOWED_DOMAIN

async def crawl_seed(seed_url, depth=0, origin_seed=None):
    global total_pages_crawled

    origin_seed = origin_seed or seed_url

    if total_pages_crawled >= MAX_PAGES or depth > CRAWL_DEPTH or seed_url in visited_urls:
        return

    visited_urls.add(normalize_url(seed_url))
    logger.info(f"Crawling (depth {depth}): {seed_url}")
    
    connector = aiohttp.TCPConnector(ssl=False) if ALLOW_INSECURE else aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        html, status = await fetch(session, seed_url)

        # Detect CAPTCHA
        if html:
            captcha = await save_captcha_evidence(html, seed_url)
            if captcha:
                timestamp = datetime.now().isoformat()
                index_entry = {
                    "url": seed_url,
                    "file": None,
                    "status": "CAPTCHA_DETECTED",
                    "timestamp": timestamp,
                    "seed_origin": origin_seed
                }
                with open(INDEX_FILE, "a") as idx:
                    idx.write(json.dumps(index_entry) + "\n")
                try:
                    os.makedirs("output", exist_ok=True)
                    with open("output/failed_urls.txt", "a", encoding="utf-8") as f:
                        f.write(f"{timestamp} | {seed_url} | CAPTCHA_DETECTED \n")
                        logger.warning(f"CAPTCHA logged to failed_urls.txt for {seed_url}")
                except Exception:
                    pass    
                return
                    
        timestamp = datetime.now().isoformat()

        if html:
            # Convert HTML to Markdown
            markdown_content = md(html)
            
            metadata = f"---\nurl: {seed_url}\ntimestamp: {timestamp}\nstatus: SUCCESS\n---\n\n"
            markdown_content = metadata + markdown_content
            
            filename = seed_url.replace("https://", "").replace("http://", "").replace("/", "_") + ".md"
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
                f.write(markdown_content)

            # Update JSON index
            index_entry = {
                "url": seed_url,
                "file": filename,
                "status": "SUCCESS",
                "timestamp": timestamp,
                "seed_origin": origin_seed
            }
            with open(INDEX_FILE, "a") as idx:
                idx.write(json.dumps(index_entry) + "\n")

            total_pages_crawled += 1

            # Find links
            soup = BeautifulSoup(html, "html.parser")
            links = [a.get("href") for a in soup.find_all("a", href=True)]
            valid_links = []
            for link in links:
                norm_link = normalize_url(link, base=seed_url)
                if norm_link not in visited_urls and is_url_allowed(norm_link):
                    valid_links.append(norm_link)
        
            for link in valid_links[:PAGES_PER_SEED]:
                await asyncio.sleep(POLITE_DELAY) 
                await crawl_seed(link, depth + 1, origin_seed=origin_seed)
                
        else:
            # Log failure
            with open(LOG_FILE, "a") as log:
                logger.error(f"{timestamp} | {seed_url} | FAILED | {status}\n")

            try:
                os.makedirs("output", exist_ok=True)
                with open("output/failed_urls.txt", "a", encoding="utf-8") as f:
                    f.write(f"{timestamp} | {seed_url} | FAILED | {status}\n")
            except Exception:
                pass

            index_entry = {
                "url": seed_url,
                "file": None,
                "status": "FAILED",
                "timestamp": timestamp,
                "seed_origin": origin_seed,
                "error": str(status)
            }
            with open(INDEX_FILE, "a", encoding="utf-8") as idx:
                idx.write(json.dumps(index_entry) + "\n")

# Running crawler
async def main():
    for seed in seeds:
        await crawl_seed(seed)
    
    logger.info(f"Total Pages Crawled: {total_pages_crawled}")
    logger.info(f"Total URLs Visited: {len(visited_urls)}")
    try:
        with open("output/failed_urls.txt", "r", encoding="utf-8") as f:
            total_failed = sum(1 for _ in f)
        logger.info(f"Total Failed URLs: {total_failed}")
    except FileNotFoundError:
        logger.info("Total Failed URLs: 0")

if __name__ == "__main__":
    asyncio.run(main())
