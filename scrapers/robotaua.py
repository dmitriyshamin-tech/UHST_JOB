"""
Robota.ua candidate/resume scraper.

Robota.ua is a React SPA so the page HTML is minimal — we call their
internal JSON API instead of scraping rendered HTML.

Endpoint discovered via browser DevTools:
  GET https://employer-api.robota.ua/cvdb/resumes
  Params: cityId=1 (Kyiv), period=1 (last day), searchText=keyword, page=0
"""

import time

import requests

import config

API_URL = "https://employer-api.robota.ua/cvdb/resumes"
RESUME_URL = "https://robota.ua/candidates/resume/{resume_id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8",
    "Origin": "https://robota.ua",
    "Referer": "https://robota.ua/",
}

KYIV_CITY_ID = 1


def _fetch_page(keyword: str, page: int = 0) -> list[dict]:
    params = {
        "cityId": KYIV_CITY_ID,
        "period": config.ROBOTAUA_PERIOD,
        "searchText": keyword,
        "page": page,
        "count": 20,
    }
    try:
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # API returns {"documents": [...], "total": N} or just a list
        if isinstance(data, list):
            return data
        return data.get("documents") or data.get("items") or []
    except Exception as e:
        print(f"[Robota.ua] API error for '{keyword}' page {page}: {e}")
        return []


def _normalize(raw: dict) -> dict | None:
    resume_id = str(raw.get("resumeId") or raw.get("id") or "")
    if not resume_id:
        return None

    name = raw.get("fullName") or raw.get("name") or "—"
    position = raw.get("profession") or raw.get("position") or raw.get("title") or ""
    salary = raw.get("salary") or ""
    experience = raw.get("experience") or ""
    skills_raw = raw.get("skills") or raw.get("rubrics") or []
    skills = ", ".join(
        s.get("name", "") if isinstance(s, dict) else str(s)
        for s in skills_raw[:6]
    )
    updated = str(raw.get("lastActivity") or raw.get("updateDate") or "")[:10]
    city = (raw.get("city") or {}).get("name", "") if isinstance(raw.get("city"), dict) else str(raw.get("city") or "")

    description = " | ".join(filter(None, [position, skills, f"Зарплата: {salary}" if salary else "", city]))

    return {
        "id": f"robota_{resume_id}",
        "title": f"{name} — {position}" if position else name,
        "description": description[:300],
        "date": updated,
        "url": RESUME_URL.format(resume_id=resume_id),
        "source": "Robota.ua",
        "ecommerce_confirmed": any(
            kw.lower() in f"{position} {skills}".lower()
            for kw in config.ECOMMERCE_KEYWORDS
        ),
    }


def scrape() -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()

    # Use slug list from config — convert hyphens back to spaces for API search
    keywords = [slug.replace("-", " ") for slug in config.ROBOTAUA_ROLE_SLUGS]
    # dedupe keyword list
    keywords = list(dict.fromkeys(keywords))

    for keyword in keywords:
        for page in range(config.ROBOTAUA_MAX_PAGES):
            items = _fetch_page(keyword, page)
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
