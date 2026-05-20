"""
Robota.ua candidate/resume scraper via internal JSON API.
"""

import time

import requests

import config

API_URL = "https://employer-api.robota.ua/cvdb/resumes"
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
_debug_printed = False  # print raw fields once per run


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
        if isinstance(data, list):
            return data
        return data.get("documents") or data.get("items") or data.get("resumes") or []
    except Exception as e:
        print(f"[Robota.ua] API error for '{keyword}' page {page}: {e}")
        return []


def _extract_url(raw: dict, resume_id: str) -> str:
    """Try every known URL field; fall back to search page."""
    for field in ("resumeUrl", "url", "link", "profileUrl", "candidateUrl", "href"):
        val = raw.get(field, "")
        if val and val.startswith("http"):
            return val

    # Try to build from ID using known Robota.ua patterns
    if resume_id:
        clean_id = resume_id.replace("robota_", "")
        # Try slug from name
        first = str(raw.get("firstName") or "").lower().strip()
        last  = str(raw.get("lastName")  or "").lower().strip()
        if first and last:
            return f"https://robota.ua/candidates/{last}-{first}/{clean_id}"
        return f"https://robota.ua/candidates/{clean_id}"

    return "https://robota.ua/candidates/"


def _normalize(raw: dict) -> dict | None:
    global _debug_printed
    if not _debug_printed:
        print(f"[Robota.ua DEBUG] Available fields: {list(raw.keys())}")
        _debug_printed = True

    # Try several possible ID field names
    resume_id = str(
        raw.get("resumeId") or raw.get("id") or raw.get("cvId") or raw.get("resumeid") or ""
    )
    if not resume_id:
        return None

    unique_id = f"robota_{resume_id}"

    first = str(raw.get("firstName") or raw.get("name") or "").strip()
    last  = str(raw.get("lastName")  or "").strip()
    name  = f"{first} {last}".strip() or "—"

    position = str(
        raw.get("profession") or raw.get("position") or raw.get("title") or
        raw.get("speciality") or ""
    ).strip()

    salary = str(raw.get("salary") or raw.get("salaryAmount") or "").strip()

    skills_raw = raw.get("skills") or raw.get("rubrics") or raw.get("tags") or []
    if isinstance(skills_raw, list):
        skills = ", ".join(
            (s.get("name") or s.get("title") or str(s)) if isinstance(s, dict) else str(s)
            for s in skills_raw[:6]
        )
    else:
        skills = str(skills_raw)

    updated = str(
        raw.get("lastActivity") or raw.get("updateDate") or
        raw.get("modifiedDate") or raw.get("date") or ""
    )[:10]

    city_raw = raw.get("city") or raw.get("cityName") or raw.get("location") or {}
    city = city_raw.get("name", "") if isinstance(city_raw, dict) else str(city_raw)

    description = " | ".join(filter(None, [
        position, skills,
        f"Зарплата: {salary}" if salary else "",
        city,
    ]))

    url = _extract_url(raw, unique_id)

    return {
        "id": unique_id,
        "title": f"{name} — {position}" if position else name,
        "description": description[:300],
        "date": updated,
        "url": url,
        "source": "Robota.ua",
        "ecommerce_confirmed": any(
            kw.lower() in f"{position} {skills}".lower()
            for kw in config.ECOMMERCE_KEYWORDS
        ),
    }


def scrape() -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()

    keywords = list(dict.fromkeys(
        slug.replace("-", " ") for slug in config.ROBOTAUA_ROLE_SLUGS
    ))

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
