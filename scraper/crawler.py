import os
import json
import aiohttp
import asyncio
import logging
from markdownify import markdownify as md
from datetime import datetime
from bs4 import BeautifulSoup

from urllib.parse import urlparse
CAPTCHA_DIR = "output/captcha_pages"
os.makedirs(CAPTCHA_DIR, exist_ok=True)

# optional: pyppeteer screenshot support
try:
    from pyppeteer import launch
    PUPPETEER_AVAILABLE = True
except Exception:
    PUPPETEER_AVAILABLE = False

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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Read seeds from file
with open("seeds.txt") as f:
    seeds = [line.strip() for line in f.readlines() if line.strip()]

# Fetch functions
async def fetch(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            html = await response.text()
            logger.info(f"Fetched {url} (status {response.status})")
            return html, response.status
        
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None, str(e)
    
# Crawl function
visited_urls = set()
total_pages_crawled = 0

async def save_captcha_evidence(html, url, page_obj=None):
    """Detect common captcha signs, save HTML and optional screenshot, return True if detected."""
    if not html:
        return False

    lower = html.lower()
    keywords = ["captcha", "recaptcha", "h-captcha", "are you human", "verify you", "just a moment", "bot verification", "checking your browser", "cloudflare"]

    # quick keyword check in HTML
    if any(k in lower for k in keywords):
        detected = True
    else:
        detected = False

    # also check for img src containing captcha
    if not detected:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for img in soup.find_all("img", src=True):
                if "captcha" in img["src"].lower():
                    detected = True
                    break
        except Exception:
            pass

    if not detected:
        return False, None, None

    # create safe filenames
    parsed = urlparse(url)
    base = (parsed.netloc + parsed.path).replace("/", "_").strip("_")
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    html_path = os.path.join(CAPTCHA_DIR, f"{base}_{ts}.html")
    png_path = None

    # save HTML
    with open(html_path, "w", encoding="utf-8") as h:
        h.write(html)

    # try screenshot if puppeteer is available
    if page_obj and PUPPETEER_AVAILABLE:
        try:
            png_path = os.path.join(CAPTCHA_DIR, f"{base}_{ts}.png")
            await page_obj.screenshot({'path': png_path, 'fullPage': True})
        except Exception:
            png_path = None

    logger.warning(f"CAPTCHA detected at {url} | html_saved={html_path} | screenshot={png_path}")
    return True, html_path, png_path


async def crawl_seed(seed_url, depth=0):
    global total_pages_crawled

    if total_pages_crawled >= MAX_PAGES or depth > CRAWL_DEPTH or seed_url in visited_urls:
        return

    visited_urls.add(seed_url)
    logger.info(f"Crawling (depth {depth}): {seed_url}")

    async with aiohttp.ClientSession() as session:
        html, status = await fetch(session, seed_url)

        # Detect & save CAPTCHA evidence (if present) 
        if html:
            captcha, html_path, screenshot_path = await save_captcha_evidence(html, seed_url)
            if captcha:
                timestamp = datetime.now().isoformat()
                index_entry = {
                    "url": seed_url,
                    "file": None,
                    "status": "CAPTCHA_DETECTED",
                    "timestamp": timestamp,
                    "seed_origin": seed_url if depth == 0 else "from_link",
                    "captcha_html": html_path,
                    "captcha_screenshot": screenshot_path
                }
                with open(INDEX_FILE, "a") as idx:
                    idx.write(json.dumps(index_entry) + "\n")
                return
                    
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
                logger.error(f"{timestamp} | {seed_url} | FAILED | {status}\n")

# Running crawler
async def main():
    for seed in seeds:
        await crawl_seed(seed)
        
if __name__ == "__main__":
    asyncio.run(main())