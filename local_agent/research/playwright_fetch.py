# for websites that load content with javascript (requests gets empty page)
# need: pip install playwright && playwright install chromium


def get_html(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=20000)
        page.wait_for_timeout(1500)
        html = page.content()
        browser.close()
    return html
