"""
WEB RESEARCH (needs internet) - this is kept separate from the AI part.
Only fetches public pages (home, about, careers) and respects robots.txt.
The text is saved in the db so later the AI can work on it offline.
"""
import time
import requests
from urllib.parse import urljoin, urlparse
from urllib import robotparser
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "LocalSalesAgent-student-project/0.1 (research bot)"}
PAGES = ["", "about", "about-us", "careers", "services"]


def allowed(url):
    try:
        base = "{0.scheme}://{0.netloc}".format(urlparse(url))
        rp = robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        rp.read()
        return rp.can_fetch(HEADERS["User-Agent"], url)
    except Exception:
        return True  # no robots.txt


def page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return " ".join(text.split())


def fetch_site(website, use_playwright=False):
    if not website.startswith("http"):
        website = "https://" + website
    all_text = []
    for p in PAGES:
        url = urljoin(website + "/", p)
        if not allowed(url):
            print("robots.txt says no:", url)
            continue
        try:
            if use_playwright:
                from research.playwright_fetch import get_html
                html = get_html(url)
            else:
                r = requests.get(url, headers=HEADERS, timeout=10)
                if r.status_code != 200:
                    continue
                html = r.text
            t = page_text(html)
            if t:
                all_text.append(f"[{p or 'home'}] " + t[:3000])
        except Exception as e:
            print("error fetching", url, e)
        time.sleep(1)  # be polite
    return "\n".join(all_text)
