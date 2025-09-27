import os
import json
import aiohttp
import asyncio
import logging
import re
import random
import hashlib
import urllib.robotparser
from urllib.parse import urlparse, urljoin, urldefrag
from datetime import datetime
from markdownify import markdownify as md
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# Configuration Variables
CRAWL_DEPTH = 1
ALLOWED_DOMAIN = ["jeevee.com", "kiec.edu.np", "prettyclickcosmetics.com", "tranquilityspa.com.np"]
PAGES_PER_SEED = 5
MAX_PAGES = 20
BLOCKED_PAGES_FULL = set()  
BLOCK_PATTERNS = []  

ALLOW_INSECURE = False  # SSL verification
POLITE_DELAY = 1        # Seconds between requests to same domain
ROBOTS_CACHE = {}       # Cache for robots.txt parsers
DOMAIN_LAST_CRAWL = {}  # For per-domain rate limiting

OUTPUT_DIR = "output/MDs"
HTML_DIR = "output/html"
SCREENSHOT_DIR = "output/screenshots"
LOG_FILE = "crawlLog.txt"
INDEX_FILE = "output/index.jsonl"

# Async lock for file writes
file_lock = asyncio.Lock()

# Utility functions
def normalize_url(url, base=None):
    """Normalize URL: resolve relative links, remove fragments, lowercase.""" 
    if base:
        url = urljoin(base, url)
    url, _ = urldefrag(url) 
    return url.strip().lower()

async def is_url_allowed(url):
    """Check if a URL is allowed based on blocklists, domain, and robots.txt."""
    if url in BLOCKED_PAGES_FULL:
        return False
    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, url):
            return False
    parsed = urlparse(url)
    domain = parsed.netloc

    if domain not in ALLOWED_DOMAIN:
        return False

    rp = await fetch_robots_txt(domain)
    if rp:
        # Use "*" as user-agent
        allowed = rp.can_fetch("*", url)
        if not allowed:
            logger.info(f"Blocked by robots.txt: {url}")
        return allowed
    return True

def url_to_filename(url: str, ext=".md") -> str:
    """
    Convert a URL into a consistent safe filename with short hash for uniqueness.
    Example: https://example.com/about -> example.com_about_ab12cd34.md
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")  
    path = parsed.path.strip("/")

    if not path:  # homepage
        path = "index"
    else:
        path = path.replace("/", "_").replace("?", "_").replace("=", "_").replace("&", "_")

    hash_suffix = hashlib.md5(url.encode()).hexdigest()[:8]
    filename = f"{domain}_{path}_{hash_suffix}{ext}"
    return filename

async def fetch_robots_txt(domain):
    """Fetch and parse robots.txt for a domain asynchronously."""
    if domain in ROBOTS_CACHE:
        return ROBOTS_CACHE[domain]
    
    robots_url = f"https://{domain}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(robots_url, timeout=5) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    rp.parse(content.splitlines())
                else:
                    rp = None
    except Exception as e:
        logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
        rp = None
    
    ROBOTS_CACHE[domain] = rp
    return rp

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

# Selenium Helper for JS Pages
def fetch_js_page(url, headless=True, screenshot_path=None):
    """Fetch page using Selenium for JS-heavy pages."""
    options = Options()
    options.headless = headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        html = driver.page_source

        # Save screenshot if path provided
        if screenshot_path:
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            driver.save_screenshot(screenshot_path)

        return html
    except WebDriverException as e:
        logger.error(f"Selenium failed for {url}: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
            del driver  # free memory immediately

# Crawl function
visited_urls = set()
total_pages_crawled = 0
failed_captcha_urls = set()

async def save_captcha_evidence(html, url, filename, page_obj=None):
    """Detect common captcha signs and save evidence if strongly detected."""
    if not html:
        return False

    lower = html.lower()
    keywords = ["captcha", "recaptcha", "h-captcha", "are you human", "verify you", 
                "just a moment", "bot verification", "checking your browser", "cloudflare"]

    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(" ", strip=True).lower()

    detected = any(k in body_text for k in keywords)

    # Adjusted strict detection: require keyword AND short or very repetitive page
    if detected and (len(body_text) < 150 or body_text.count("captcha") > 2):
        strict_detected = True
    else:
        strict_detected = False

    if strict_detected and url not in failed_captcha_urls:
        failed_captcha_urls.add(url)
        logger.warning(f"CAPTCHA strongly detected at {url}")

        os.makedirs(HTML_DIR, exist_ok=True)
        with open(os.path.join(HTML_DIR, filename.replace(".md", ".html")), "w", encoding="utf-8") as f:
            f.write(html)

        screenshot_path = os.path.join(SCREENSHOT_DIR, filename.replace(".md", ".png"))
        await asyncio.to_thread(fetch_js_page, url, screenshot_path=screenshot_path)

    return strict_detected

async def domain_delay(domain):
    """Respect per-domain polite delay with jitter."""
    now = datetime.now().timestamp()
    last = DOMAIN_LAST_CRAWL.get(domain, 0)
    wait_time = POLITE_DELAY + random.uniform(0, 1)
    if now - last < wait_time:
        await asyncio.sleep(wait_time - (now - last))
    DOMAIN_LAST_CRAWL[domain] = datetime.now().timestamp()

async def crawl_seed(seed_url, depth=0, origin_seed=None):
    global total_pages_crawled

    origin_seed = origin_seed or seed_url

    if total_pages_crawled >= MAX_PAGES or depth > CRAWL_DEPTH or seed_url in visited_urls:
        return

    visited_urls.add(normalize_url(seed_url))
    logger.info(f"Crawling (depth {depth}, from {origin_seed}): {seed_url}")

    parsed = urlparse(seed_url)
    domain = parsed.netloc
    await domain_delay(domain)

    connector = aiohttp.TCPConnector(ssl=False) if ALLOW_INSECURE else aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        html, status = await fetch(session, seed_url)

        filename = url_to_filename(seed_url)
        if html is None:
            screenshot_path = os.path.join(SCREENSHOT_DIR, filename.replace(".md", ".png"))
            html = await asyncio.to_thread(fetch_js_page, seed_url, screenshot_path=screenshot_path)
            status = 200 if html else "FAILED_JS"

        timestamp = datetime.now().isoformat()

        if html:
            captcha = await save_captcha_evidence(html, seed_url, filename)
            if captcha:
                index_entry = {
                    "url": seed_url,
                    "file": None,
                    "status": "CAPTCHA_DETECTED",
                    "timestamp": timestamp,
                    "seed_origin": origin_seed
                }
                async with file_lock:
                    with open(INDEX_FILE, "a", encoding="utf-8") as idx:
                        idx.write(json.dumps(index_entry) + "\n")
                    os.makedirs("output", exist_ok=True)
                    with open("output/failed_urls.txt", "a", encoding="utf-8") as f:
                        f.write(f"{timestamp} | {seed_url} | CAPTCHA_DETECTED \n")
                return

        page_title = None
        meta_description = None
        if html:
            soup = BeautifulSoup(html, "html.parser")
            if soup.title:
                page_title = soup.title.string.strip() if soup.title.string else None
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if not desc_tag:
                desc_tag = soup.find("meta", attrs={"property": "og:description"})
            if desc_tag and desc_tag.get("content"):
                meta_description = desc_tag["content"].strip()

            os.makedirs(HTML_DIR, exist_ok=True)
            with open(os.path.join(HTML_DIR, filename.replace(".md", ".html")), "w", encoding="utf-8") as f:
                f.write(html)

            markdown_content = md(html)
            metadata = f"---\nurl: {seed_url}\ntimestamp: {timestamp}\nstatus: SUCCESS\n---\n\n"
            markdown_content = metadata + markdown_content
            
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
                f.write(markdown_content)

            index_entry = {
                "url": seed_url,
                "file": filename,
                "status": "SUCCESS",
                "timestamp": timestamp,
                "seed_origin": origin_seed,
                "http_status": status,
                "title": page_title,
                "meta_description": meta_description
            }
            async with file_lock:
                with open(INDEX_FILE, "a", encoding="utf-8") as idx:
                    idx.write(json.dumps(index_entry) + "\n")

            total_pages_crawled += 1

            links = [a.get("href") for a in soup.find_all("a", href=True)]
            valid_links = []
            for link in links:
                norm_link = normalize_url(link, base=seed_url)
                if norm_link not in visited_urls and await is_url_allowed(norm_link):
                    valid_links.append(norm_link)
        
            for link in valid_links[:PAGES_PER_SEED]:
                await crawl_seed(link, depth + 1, origin_seed=origin_seed)
                
        else:
            logger.error(f"{timestamp} | {seed_url} | FAILED | {status}")
            async with file_lock:
                os.makedirs("output", exist_ok=True)
                with open("output/failed_urls.txt", "a", encoding="utf-8") as f:
                    f.write(f"{timestamp} | {seed_url} | FAILED | {status}\n")

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
    await asyncio.gather(*(crawl_seed(seed) for seed in seeds))
    
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
