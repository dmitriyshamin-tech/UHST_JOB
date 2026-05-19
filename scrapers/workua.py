"""
Work.ua resume scraper — searches Kyiv resumes for e-commerce candidates.

Strategy:
  1. For each target role keyword search Work.ua resumes in Kyiv, last N days.
  2. Collect resume cards (title + snippet shown in listing).
  3. Mark as "confirmed e-commerce" if snippet contains e-commerce keywords.
  4. Always include all results so the user sees the full picture; badge shows confidence.
"""

import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

import config

BASE_URL = "https://www.work.ua"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _build_url(keyword: str, page: int = 1) -> str:
    q = quote(keyword)
    url = f"{BASE_URL}/resumes-kyiv/?search={q}&period={config.WORKUA_PERIOD}"
    if page > 1:
        url += f"&page={page}"
    return url


def _parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Work.ua resume cards sit inside a main card block
    cards = soup.select("div.card-work, div.resume-link, article")

    for card in cards:
        try:
            link_tag = card.select_one("a[href*='/resumes/']")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            m = re.search(r"/resumes/(\d+)/", href)
            if not m:
                continue

            resume_id = f"workua_{m.group(1)}"
            title = link_tag.get_text(strip=True)

            # Description snippet (varies by Work.ua markup version)
            desc_tag = (
                card.select_one("p.mt-xs")
                or card.select_one(".card-body p")
                or card.select_one("p")
            )
            description = desc_tag.get_text(strip=True) if desc_tag else ""

            # Update date label
            date_tag = card.select_one("time") or card.select_one(".text-muted")
            date_str = date_tag.get_text(strip=True) if date_tag else ""

            results.append(
                {
                    "id": resume_id,
                    "title": title,
                    "description": description,
                    "date": date_str,
                    "url": f"{BASE_URL}{href}" if href.startswith("/") else href,
                }
            )
        except Exception:
            continue

    return results


def _is_ecommerce(resume: dict) -> bool:
    text = f"{resume['title']} {resume['description']}".lower()
    return any(kw.lower() in text for kw in config.ECOMMERCE_KEYWORDS)


def scrape() -> list[dict]:
    all_results: list[dict] = []
    seen_in_run: set[str] = set()

    for keyword in config.TARGET_ROLES:
        for page in range(1, config.WORKUA_MAX_PAGES + 1):
            url = _build_url(keyword, page)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                print(f"[Work.ua] request failed {url}: {e}")
                break

            cards = _parse_page(resp.text)
            if not cards:
                break  # no more pages

            for card in cards:
                if card["id"] in seen_in_run:
                    continue
                seen_in_run.add(card["id"])
                card["source"] = "Work.ua"
                card["ecommerce_confirmed"] = _is_ecommerce(card)
                all_results.append(card)

            time.sleep(2.5)  # polite delay between requests

        time.sleep(1)

    return all_results
