"""
Work.ua resume scraper.

Work.ua blocks HTML scraping from GitHub Actions IPs (403).
We use their internal JSON API instead — same approach that works for Robota.ua.

Endpoint: https://api.work.ua/resumes
Params: cityId=1 (Kyiv), period=1 (last day), searchText=keyword, page=0
"""

import time
from urllib.parse import quote

import requests

import config

API_URL  = "https://api.work.ua/resumes"
BASE_URL = "https://www.work.ua"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8",
    "Origin": "https://www.work.ua",
    "Referer": "https://www.work.ua/resumes-kyiv/",
}

KYIV_CITY_ID = 1
_debug_printed = False


def _fetch_api(keyword: str, page: int = 0) -> list[dict]:
    params = {
        "cityId": KYIV_CITY_ID,
        "period": config.WORKUA_PERIOD,
        "searchText": keyword,
        "page": page,
        "count": 20,
    }
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("documents") or data.get("items") or data.get("resumes") or []


def _normalize(raw: dict) -> dict | None:
    global _debug_printed
    if not _debug_printed:
        print(f"[Work.ua DEBUG] Fields: {list(raw.keys())}")
        _debug_printed = True

    resume_id = str(raw.get("resumeId") or raw.get("id") or "")
    if not resume_id:
        return None

    name = str(raw.get("fullName") or raw.get("name") or "—").strip()
    position = str(raw.get("speciality") or raw.get("position") or raw.get("profession") or "").strip()
    salary = str(raw.get("salary") or raw.get("salaryAmount") or "").strip()
    city = str((raw.get("city") or {}).get("name", "") if isinstance(raw.get("city"), dict) else raw.get("cityName") or "").strip()

    skills_raw = raw.get("skills") or raw.get("rubrics") or []
    skills = ", ".join(
        (s.get("name") or str(s)) if isinstance(s, dict) else str(s)
        for s in skills_raw[:6]
    )

    updated = str(raw.get("updatedDate") or raw.get("lastActivity") or raw.get("modifiedDate") or "")[:10]

    # URL from API or build from ID
    url_field = str(raw.get("url") or raw.get("resumeUrl") or "").strip()
    if url_field.startswith("http"):
        resume_url = url_field
    elif url_field.startswith("/"):
        resume_url = f"{BASE_URL}{url_field}"
    else:
        resume_url = f"{BASE_URL}/resumes/{resume_id}/"

    description = " | ".join(filter(None, [
        position, skills,
        f"Зарплата: {salary}" if salary else "",
        city,
    ]))

    return {
        "id": f"workua_{resume_id}",
        "title": f"{name} — {position}" if position else name,
        "description": description[:300],
        "date": updated,
        "url": resume_url,
        "source": "Work.ua",
        "ecommerce_confirmed": any(
            kw.lower() in f"{position} {skills}".lower()
            for kw in config.ECOMMERCE_KEYWORDS
        ),
    }


def scrape() -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()

    for keyword in config.TARGET_ROLES:
        for page in range(config.WORKUA_MAX_PAGES):
            try:
                items = _fetch_api(keyword, page)
            except Exception as e:
                print(f"[Work.ua] API error '{keyword}' page {page}: {e}")
                break

            if not items:
                break

            for raw in items:
                candidate = _normalize(raw)
                if candidate and candidate["id"] not in seen:
                    seen.add(candidate["id"])
                    results.append(candidate)

            time.sleep(2)
        time.sleep(1)

    return results
