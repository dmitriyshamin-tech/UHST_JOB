"""
Work.ua resume scraper — searches Kyiv resumes for e-commerce candidates.

Uses a link-first approach: finds every /resumes/ID/ link on the page,
then walks up to the nearest card container to extract title + snippet.
This is more robust than relying on specific class names that Work.ua changes.
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

RESUME_ID_RE = re.compile(r"/resumes/(\d+)/")


def _build_url(keyword: str, page: int = 1) -> str:
    q = quote(keyword)
    url = f"{BASE_URL}/resumes-kyiv/?search={q}&period={config.WORKUA_PERIOD}"
    if page > 1:
        url += f"&page={page}"
    return url


def _parse_page(html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Find ALL links that point to a resume
    resume_links = soup.find_all("a", href=RESUME_ID_RE)

    if not resume_links:
        # Debug: show what links are on the page
        all_links = [a.get("href", "") for a in soup.find_all("a") if "/resumes/" in a.get("href", "")]
        print(f"[Work.ua] DEBUG: 0 resume links at {url} | sample hrefs: {all_links[:5]}")
        return []

    print(f"[Work.ua] Found {len(resume_links)} resume links at {url}")

    results = []
    for link_tag in resume_links:
        try:
            href = link_tag.get("href", "")
            m = RESUME_ID_RE.search(href)
            if not m:
                continue

            resume_id = f"workua_{m.group(1)}"
            title = link_tag.get_text(strip=True)

            # Walk up the DOM to find the card container (usually 2-4 levels up)
            card = link_tag.parent
            for _ in range(5):
                if card is None:
                    break
                tag = getattr(card, "name", "")
                cls = " ".join(card.get("class", []))
                if tag in ("article", "section", "li") or any(
                    k in cls for k in ("card", "resume", "vacancy", "item")
                ):
                    break
                card = card.parent

            description = ""
            date_str = ""
            if card:
                # Description: first <p> that is not the title link
                for p in card.find_all("p"):
                    txt = p.get_text(strip=True)
                    if txt and txt != title:
                        description = txt[:250]
                        break

                # Date: <time> tag or element with "мuted" / "date" class
                date_el = card.find("time") or card.find(
                    class_=re.compile(r"muted|date|ago|time", re.I)
                )
                if date_el:
                    date_str = date_el.get_text(strip=True)

            results.append({
                "id": resume_id,
                "title": title,
                "description": description,
                "date": date_str,
                "url": f"{BASE_URL}{href}" if href.startswith("/") else href,
            })
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
                print(f"[Work.ua] Request failed {url}: {e}")
                break

            cards = _parse_page(resp.text, url)
            if not cards:
                break

            for card in cards:
                if card["id"] in seen_in_run:
                    continue
                seen_in_run.add(card["id"])
                card["source"] = "Work.ua"
                card["ecommerce_confirmed"] = _is_ecommerce(card)
                all_results.append(card)

            time.sleep(2.5)

        time.sleep(1)

    return all_results
