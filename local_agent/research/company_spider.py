"""
Scrapy spider to crawl a list of prospect websites in bulk.
Output is a json file that you can import with import_data.py

run:
    scrapy runspider research/company_spider.py -a urls_file=data/prospects/urls.txt -o data/prospects/crawled.json
"""
import scrapy
from bs4 import BeautifulSoup


class CompanySpider(scrapy.Spider):
    name = "company"
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1,
        "DEPTH_LIMIT": 1,
        "USER_AGENT": "LocalSalesAgent-student-project/0.1",
    }

    def __init__(self, urls_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = []
        if urls_file:
            with open(urls_file) as f:
                self.start_urls = [l.strip() for l in f if l.strip()]

    def parse(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        for t in soup(["script", "style"]):
            t.decompose()
        text = " ".join(soup.get_text(" ").split())
        yield {"url": response.url, "text": text[:5000]}

        # follow about/careers links only
        for href in response.css("a::attr(href)").getall():
            if any(k in href.lower() for k in ["about", "career", "jobs", "team"]):
                yield response.follow(href, self.parse)
