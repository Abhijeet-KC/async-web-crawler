# async-web-crawler
## Project Overview
This project is a **smart, asynchronous web crawler** capable of crawling websites within specified domains.  
It supports JavaScript-heavy pages using Selenium, respects robots.txt, handles retries, and converts pages to **clean Markdown**.  
The crawler also generates a **JSONL index**, tracks failed URLs, and logs detailed crawl info.
The crawler has been tested on WordPress, React, and Next.js websites.

## Project Structure
/scraper/
├── crawler.py # Main crawler script
├── crawlLog.txt # Detailed log file
├── seeds.txt # Priority URLs to crawl
├── .gitignore
├── requirements.txt # Python dependencies
└── output/
    ├── MDs/ # Markdown files for each crawled page
    ├── index.jsonl # JSON index of all crawled pages
    └── failed_urls.txt # URLs that failed to crawl

> HTML files and screenshots are generated during runtime but ignored in Git (optional).

---

## Prerequisites

- **Python 3.11+**
- **Chrome Browser** installed
- **ChromeDriver** matching your Chrome version: [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads)
- Install Python dependencies:

```bash
pip install -r requirements.txt
```
## Configuration Variables

You can modify these at the top of crawler.py:

<table>
  <thead>
    <tr>
      <th>Variable</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>CRAWL_DEPTH</td>
      <td>Depth of crawl from each seed URL</td>
    </tr>
    <tr>
      <td>ALLOWED_DOMAIN</td>
      <td>List of allowed domains</td>
    </tr>
    <tr>
      <td>PAGES_PER_SEED</td>
      <td>Max pages to crawl per seed URL</td>
    </tr>
    <tr>
      <td>MAX_PAGES</td>
      <td>Total max pages across all seeds</td>
    </tr>
    <tr>
      <td>BLOCKED_PAGES_FULL</td>
      <td>Full URLs to block</td>
    </tr>
    <tr>
      <td>BLOCK_PATTERNS</td>
      <td>Regex patterns to block</td>
    </tr>
    <tr>
      <td>POLITE_DELAY</td>
      <td>Delay between requests per domain</td>
    </tr>
    <tr>
      <td>ALLOW_INSECURE</td>
      <td>Skip SSL verification if True</td>
    </tr>
  </tbody>
</table>

### Running the Crawler from the repo
#### Option 1 : Using Python Virtual Environment
```bash
# clone repo
git clone <repo-url>
cd scraper

# create venv
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# install dependencies
pip install -r requirements.txt

# run crawler
python crawler.py

```
### Cross-Platform Notes

<ul>
  <li>Works on Windows, macOS, Linux.</li>
  <li>Requires Python 3.11+ and Chrome + ChromeDriver.</li>
  <li>For Linux/macOS: make <code>chromedriver</code> executable.</li>
</ul>

```bash
chmod +x /path/to/chromedriver
```
<ul>
    <li>For Windows: put chromedriver.exe in a folder listed in your PATH.</li>
</ul>

### Logging & Error Handling

<ul>
  <li><code>crawlLog.txt</code> logs crawl progress, retries, and errors.</li>
  <li>Failed URLs (e.g., CAPTCHA-protected) are tracked in <code>output/failed_urls.txt</code>.</li>
  <li>Robots.txt compliance and polite delays are respected.</li>
  <li>JS-heavy pages are handled with Selenium (headless by default).</li>
</ul>

### Option 2: Using Docker (Recommended for Consistency)</h3>

#### Build Docker image
```bash
docker build -t web-crawler .
```
#### Run Docker container
```bash
docker run --rm -v $(pwd)/output:/app/output web-crawler
```
<h4>Notes:</h4>
<ul>
  <li>The Docker setup includes Python 3.11, all dependencies, and Chrome/ChromeDriver preconfigured.</li>
  <li>Output files are mounted to the local <code>output/</code> folder for easy access.</li>
  <li>Cross-platform compatible: works on Windows, macOS, Linux without manual dependency setup.</li>
</ul>

### Notes on Testing

#### Sites tested:

<ul>
    <li>https://jeevee.com – Next.js</li>
    <li>https://prettyclickcosmetics.com – WordPress</li>
    <li>https://www.tranquilityspa.com.np – React</li>
    <li>http://kiec.edu.np – was blocked due to bot protection (CAPTCHA).</li>
</ul>

