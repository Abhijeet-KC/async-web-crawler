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