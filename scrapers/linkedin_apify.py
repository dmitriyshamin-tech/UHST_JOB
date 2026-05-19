"""
LinkedIn scraper via Apify.

Uses actor: bebity/linkedin-profile-scraper
Apify free tier: ~100 results/month — enough for daily monitoring.

Setup:
  1. Register at https://apify.com (free account)
  2. Go to https://console.apify.com/account/integrations → copy your API token
  3. Add it to GitHub Secrets as APIFY_API_TOKEN
"""

import time

import requests

import config

APIFY_BASE = "https://api.apify.com/v2"
POLL_INTERVAL = 10   # seconds
MAX_WAIT = 300       # 5 minutes max per run


def _run_actor(actor_id: str, actor_input: dict) -> list[dict]:
    token = config.APIFY_API_TOKEN
    # Start actor run
    run_resp = requests.post(
        f"{APIFY_BASE}/acts/{actor_id}/runs",
        params={"token": token},
        json=actor_input,
        timeout=30,
    )
    run_resp.raise_for_status()
    run_id = run_resp.json()["data"]["id"]

    # Poll until finished
    waited = 0
    while waited < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
        status_resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": token},
            timeout=15,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        print(f"[Apify] Actor {actor_id} finished with status: {status}")
        return []

    # Fetch dataset items
    dataset_id = run_resp.json()["data"]["defaultDatasetId"]
    items_resp = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": token, "format": "json"},
        timeout=30,
    )
    items_resp.raise_for_status()
    return items_resp.json()


def _normalize_profile(raw: dict) -> dict | None:
    """Map Apify LinkedIn result → our standard candidate dict."""
    profile_url = raw.get("url") or raw.get("profileUrl") or raw.get("linkedinUrl", "")
    if not profile_url:
        return None

    unique_id = profile_url.rstrip("/").split("/")[-1]
    name = raw.get("fullName") or raw.get("name") or "—"
    headline = raw.get("headline") or raw.get("jobTitle") or ""
    location = raw.get("location") or raw.get("geoLocation") or ""
    summary = raw.get("summary") or raw.get("about") or ""

    # Only include Kyiv-based or relocating candidates
    loc_lower = location.lower()
    if loc_lower and "kyiv" not in loc_lower and "київ" not in loc_lower and "киев" not in loc_lower:
        return None

    return {
        "id": f"linkedin_{unique_id}",
        "title": f"{name} — {headline}",
        "description": summary[:300],
        "date": "",
        "url": profile_url,
        "source": "LinkedIn",
        "ecommerce_confirmed": any(
            kw.lower() in f"{headline} {summary}".lower()
            for kw in config.ECOMMERCE_KEYWORDS
        ),
    }


def scrape() -> list[dict]:
    if not config.APIFY_API_TOKEN:
        print("[LinkedIn] APIFY_API_TOKEN not set — skipping")
        return []

    results: list[dict] = []
    seen: set[str] = set()

    for query in config.LINKEDIN_SEARCH_QUERIES:
        actor_input = {
            "searchUrl": (
                f"https://www.linkedin.com/search/results/people/"
                f"?keywords={query.replace(' ', '%20')}&origin=GLOBAL_SEARCH_HEADER"
            ),
            "maxResults": 25,
        }
        try:
            raw_items = _run_actor(config.LINKEDIN_APIFY_ACTOR, actor_input)
        except Exception as e:
            print(f"[LinkedIn] Apify error for query '{query}': {e}")
            continue

        for item in raw_items:
            candidate = _normalize_profile(item)
            if candidate and candidate["id"] not in seen:
                seen.add(candidate["id"])
                results.append(candidate)

        time.sleep(5)  # between actor runs

    return results
