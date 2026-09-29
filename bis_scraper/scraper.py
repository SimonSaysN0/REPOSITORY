from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .config import ALLOWED_HOST, DEFAULT_DELAY_SECONDS, DEFAULT_LISTING_URL, DEFAULT_TIMEOUT_SECONDS, DETAIL_LINK_SELECTOR, USER_AGENT
from .database import Store
from .parser import IS_PATTERN, extract_detail_entries, parse_detail


class CrawlStop(RuntimeError):
    """Stop the run on rate limiting or a source response requiring operator review."""


class BISClient:
    def __init__(self, delay: float, timeout: int, render_browser: bool = False):
        self.delay, self.timeout = delay, timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        self.last_request = 0.0
        self.robot = RobotFileParser()
        self.robot_ready = False
        self.driver = None
        self.render_browser = render_browser

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
            raise ValueError(f"Refusing URL outside the configured BIS host: {url}")
        if not self.robot_ready:
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            response = self.session.get(robots_url, timeout=self.timeout)
            response.raise_for_status()
            self.robot.set_url(robots_url)
            self.robot.parse(response.text.splitlines())
            self.robot_ready = True
        return self.robot.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str:
        if not self._robots_allowed(url):
            raise PermissionError(f"robots.txt disallows this URL: {url}")
        pause = self.delay - (time.monotonic() - self.last_request)
        if pause > 0: time.sleep(pause)
        if self.render_browser:
            if self.driver is None:
                try:
                    from selenium import webdriver
                    from selenium.webdriver.chrome.options import Options
                except ImportError as exc:
                    raise RuntimeError("Browser mode needs Selenium: python -m pip install -r bis_scraper/requirements-browser.txt") from exc
                options = Options()
                options.add_argument("--headless=new")
                options.add_argument("--window-size=1440,1000")
                options.add_argument("--disable-dev-shm-usage")
                self.driver = webdriver.Chrome(options=options)
                self.driver.set_page_load_timeout(self.timeout)
            self.driver.get(url)
            time.sleep(max(2.0, self.delay))
            self.last_request = time.monotonic()
            return self.driver.page_source
        response = self.session.get(url, timeout=self.timeout)
        self.last_request = time.monotonic()
        if response.status_code in (429, 503):
            raise CrawlStop(f"BIS returned HTTP {response.status_code}; stopping so the crawl can be retried later.")
        response.raise_for_status()
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise RuntimeError(f"Expected HTML at {url}; got {response.headers.get('Content-Type')}")
        return response.text

    def close(self) -> None:
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

    def browser_resources(self) -> list[str]:
        if self.driver is None: return []
        try:
            return self.driver.execute_script("return performance.getEntriesByType('resource').map(e => e.name)") or []
        except Exception:
            return []


def inspect_links(html: str, listing_url: str, resources: list[str] | None = None) -> int:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(listing_url).netloc.casefold()
    count = 0
    same_host_links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(listing_url, a["href"])
        if urlparse(href).netloc.casefold() != host:
            continue
        anchor_text = a.get_text(" ", strip=True)
        if len(same_host_links) < 20:
            same_host_links.append((anchor_text[:100] or "[no anchor text]", href))
        context = a
        context_text = anchor_text
        match = IS_PATTERN.search(context_text)
        for _ in range(5):
            context = context.parent
            if context is None: break
            context_text = context.get_text(" ", strip=True)
            match = IS_PATTERN.search(context_text)
            if match: break
        if match:
            label = anchor_text[:100] if anchor_text else "[no anchor text]"
            if count < 20: print(f"STANDARD CANDIDATE  {match.group(0)}\t{href}\t{label}")
            count += 1
    title = soup.title.get_text(" ", strip=True) if soup.title else "(no page title)"
    visible = soup.get_text(" ", strip=True)
    print(f"Page title: {title}")
    print(f"HTML bytes: {len(html.encode('utf-8'))}; visible text chars: {len(visible)}; same-host anchors: {len(soup.select('a[href]'))}")
    print(f"Visible text: {visible[:2500] or '(empty)'}")
    scripts = [urlparse(urljoin(listing_url, s.get('src', ''))).path for s in soup.select('script[src]')]
    print(f"External script paths ({len(scripts)}): {scripts[:20]}")
    if resources:
        relevant = []
        for resource in resources:
            parsed = urlparse(resource)
            path = f"{parsed.netloc}{parsed.path}"
            if any(k in path.casefold() for k in ("api", "search", "standard", "published", "list", "graphql")):
                if path not in relevant: relevant.append(path)
        print(f"Browser resource paths matching catalogue/API terms ({len(relevant)}): {relevant[:40]}")
    if count > 20: print(f"... {count-20} more standard-linked candidates omitted")
    if not count:
        print("No standard-number context was found around same-host anchors in the page HTML.")
        print("Same-host anchor samples:")
        for label, href in same_host_links: print(f"  {label}\t{href}")
    return count


def main() -> int:
    p = argparse.ArgumentParser(description="Incremental, metadata-only BIS catalogue crawler; respects robots.txt and rate limits.")
    p.add_argument("--listing-url", default=DEFAULT_LISTING_URL)
    p.add_argument("--detail-link-selector", default=DETAIL_LINK_SELECTOR)
    p.add_argument("--inspect-listing", action="store_true", help="Print candidate detail links only; do not crawl details or write records")
    p.add_argument("--render-browser", action="store_true", help="Render the page with headless Chrome for JavaScript-driven catalogues")
    p.add_argument("--max-standards", type=int, default=10, help="Safety cap per run (default: 10)")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="Seconds between requests (default: 2)")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    p.add_argument("--db", type=Path, default=Path("data/bis_metadata.sqlite3"))
    p.add_argument("--export-dir", type=Path, default=Path("data/bis_crawl"))
    p.add_argument("--confirm-terms-reviewed", action="store_true", help="Confirm you reviewed BIS terms and have authorization for metadata collection")
    args = p.parse_args()
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(filename="logs/bis_scraper.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    if args.max_standards < 1 or args.delay < 1:
        p.error("--max-standards must be positive and --delay must be at least 1 second")
    if not args.inspect_listing and not args.confirm_terms_reviewed:
        p.error("Review BIS terms/licensing first; pass --confirm-terms-reviewed only when authorized")
    if not args.inspect_listing and not args.detail_link_selector:
        p.error("No detail-link selector is configured. Inspect the portal and set BIS_DETAIL_LINK_SELECTOR; no selector is guessed.")
    client = None
    try:
        client = BISClient(args.delay, args.timeout, args.render_browser)
        logging.info("Starting bounded BIS catalogue run; listing=%s cap=%s", args.listing_url, args.max_standards)
        list_html = client.get(args.listing_url)
        if args.inspect_listing:
            count = inspect_links(list_html, args.listing_url, client.browser_resources())
            print(f"Found {count} anchor(s) with a nearby standard number. Use diagnostics above to determine whether the list is rendered dynamically or uses a different structure.")
            return 0
        entries = extract_detail_entries(list_html, args.listing_url, args.detail_link_selector)
        if not entries:
            raise RuntimeError("The configured selector found no detail URLs. Inspect the rendered BIS page; do not increase crawl size.")
        id_to_url = {std.casefold(): url for std, url in entries if std}
        queue = deque(entries[:args.max_standards])
        queued = {url for _, url in queue}
        store = Store(args.db)
        changed = 0
        visited = 0
        try:
            while queue and visited < args.max_standards:
                listed_id, detail_url = queue.popleft()
                try:
                    html = client.get(detail_url)
                    data, refs = parse_detail(html, detail_url)
                    if not data.get("is_number") and listed_id: data["is_number"] = listed_id
                    if not data.get("is_number"):
                        print(f"Skip detail without an IS number: {detail_url}", file=sys.stderr)
                        continue
                    changed += int(store.save(data, refs))
                    visited += 1
                    logging.info("Checked %s; reference_count=%d", data["is_number"], len(refs))
                    # Follow only relationships whose detail URL was present in the catalogue list.
                    for target in refs:
                        target_url = id_to_url.get(target.casefold())
                        if target_url and target_url not in queued and visited + len(queue) < args.max_standards:
                            queue.append((target, target_url)); queued.add(target_url)
                    print(f"Checked {data['is_number']} ({visited}/{args.max_standards})")
                except CrawlStop:
                    raise
                except (requests.RequestException, RuntimeError, ValueError) as exc:
                    logging.exception("Detail failed: %s", detail_url)
                    print(f"Detail failed; continuing: {detail_url}: {exc}", file=sys.stderr)
            paths = store.export_csv(args.export_dir)
            print(f"Checked {visited}; changed/new {changed}; database records {store.count()}")
            print(f"CSV exports: {paths[0]} and {paths[1]}")
        finally:
            store.close()
    except (requests.RequestException, PermissionError, RuntimeError, ValueError) as exc:
        logging.exception("Crawl stopped")
        print(f"Crawl stopped: {exc}", file=sys.stderr)
        return 2
    finally:
        if client is not None: client.close()
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
