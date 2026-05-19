"""
DOU.ua candidate profiles scraper.

DOU is server-side rendered — works with plain requests + BeautifulSoup.
Candidates URL: https://jobs.dou.ua/candidates/?search={keyword}&city={city}

DOU candidate cards show: name, position, skills, city, last active date.
"""

import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

import config

BASE_URL = "https://jobs.dou.ua"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7",
    "Referer": "https://jobs.dou.ua/",
}


def _build_url(keyword: str) -> str:
    return f"{BASE_URL}/candidates/?search={quote(keyword)}&city={quote(config.DOU_CITY)}"


def _parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # DOU candidate cards
    cards = soup.select("li.l-vacancy, div.candidate, article.candidate")
    if not cards:
        # try broader selector
        cards = soup.select("ul.lt li")

    for card in cards:
        try:
            # Name + profile link
            link_tag = card.select_one("a.profile, a[href*='/candidates/']")
            if not link_tag:
                link_tag = card.select_one("a")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            if not href:
                continue

            # Build unique ID from URL path
            slug = href.rstrip("/").split("/")[-1]
            candidate_id = f"dou_{slug}"

            name = link_tag.get_text(strip=True)

            # Position / title
            title_tag = card.select_one(".title, .position, h2, h3")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Skills / tags
            skill_tags = card.select(".skill, .tag, li.skill")
            skills = ", ".join(t.get_text(strip=True) for t in skill_tags[:8])

            # Date
            date_tag = card.select_one(".date, time, .last-seen")
            date_str = date_tag.get_text(strip=True) if date_tag else ""

            description = " | ".join(filter(None, [title, skills]))
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            results.append({
                "id": candidate_id,
                "title": f"{name} — {title}" if title else name,
                "description": description[:300],
                "date": date_str,
                "url": full_url,
            })
        except Exception:
            continue

    return results


def _is_ecommerce(candidate: dict) -> bool:
    text = f"{candidate['title']} {candidate['description']}".lower()
    return any(kw.lower() in text for kw in config.ECOMMERCE_KEYWORDS)


def scrape() -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()

    for keyword in config.DOU_SEARCH_KEYWORDS:
        url = _build_url(keyword)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"[DOU] request failed '{keyword}': {e}")
            time.sleep(2)
            continue

        cards = _parse_page(resp.text)
        for card in cards:
            if card["id"] in seen:
                continue
            seen.add(card["id"])
            card["source"] = "DOU.ua"
            card["ecommerce_confirmed"] = _is_ecommerce(card)
            results.append(card)

        time.sleep(2.5)

    return results
