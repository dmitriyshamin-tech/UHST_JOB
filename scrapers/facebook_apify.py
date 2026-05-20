"""
Facebook groups scraper via Apify.

Uses actor: apify/facebook-groups-scraper
Filters posts by job-seeking keywords + e-commerce context.

How to find group URLs:
  1. Open Facebook and search for: "e-commerce Ukraine", "Робота Київ IT",
     "Digital Marketing Ukraine", "Дизайнери України", "Розробники Україна"
  2. Join public groups, copy their URL
  3. Add URLs to config.FACEBOOK_GROUP_URLS

Apify free tier has limited runs — monitor 3-5 active groups maximum.
"""

import time

import requests

import config

APIFY_BASE = "https://api.apify.com/v2"
POLL_INTERVAL = 10
MAX_WAIT = 300


def _apify_actor_url(actor_id: str) -> str:
    """Apify API requires username~actor-name format (tilde, not slash)."""
    return f"{APIFY_BASE}/acts/{actor_id.replace('/', '~')}/runs"


def _run_actor(actor_id: str, actor_input: dict) -> list[dict]:
    token = config.APIFY_API_TOKEN
    run_resp = requests.post(
        _apify_actor_url(actor_id),
        params={"token": token},
        json=actor_input,
        timeout=30,
    )
    run_resp.raise_for_status()
    run_id = run_resp.json()["data"]["id"]

    waited = 0
    status = "RUNNING"
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
        print(f"[Apify Facebook] Run ended with status: {status}")
        return []

    dataset_id = run_resp.json()["data"]["defaultDatasetId"]
    items_resp = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": token, "format": "json"},
        timeout=30,
    )
    items_resp.raise_for_status()
    return items_resp.json()


def _is_job_seeking(text: str) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in config.JOB_SEEK_KEYWORDS)


def _is_ecommerce(text: str) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in config.ECOMMERCE_KEYWORDS)


def _normalize_post(raw: dict) -> dict | None:
    post_id = str(raw.get("postId") or raw.get("id") or "")
    if not post_id:
        return None

    text = raw.get("text") or raw.get("message") or ""
    if not text:
        return None

    # Must be job-seeking AND related to e-commerce or our roles
    if not _is_job_seeking(text):
        return None

    author = raw.get("authorName") or raw.get("userName") or "Автор невідомий"
    profile_url = raw.get("authorUrl") or raw.get("profileUrl") or ""
    post_url = raw.get("url") or raw.get("postUrl") or ""
    date_str = str(raw.get("time") or raw.get("timestamp") or "")

    return {
        "id": f"fb_{post_id}",
        "title": f"{author} (Facebook)",
        "description": text[:400],
        "date": date_str[:10],
        "url": post_url or profile_url,
        "source": "Facebook",
        "ecommerce_confirmed": _is_ecommerce(text),
    }


def scrape() -> list[dict]:
    if not config.APIFY_API_TOKEN:
        print("[Facebook] APIFY_API_TOKEN not set — skipping")
        return []

    if not config.FACEBOOK_GROUP_URLS:
        print("[Facebook] No group URLs configured in config.FACEBOOK_GROUP_URLS — skipping")
        return []

    actor_input = {
        "startUrls": [{"url": u} for u in config.FACEBOOK_GROUP_URLS],
        "maxPosts": config.FACEBOOK_POSTS_LIMIT,
        "maxPostComments": 0,
        "maxReviews": 0,
    }

    try:
        raw_items = _run_actor(config.FACEBOOK_APIFY_ACTOR, actor_input)
    except Exception as e:
        print(f"[Facebook] Apify error: {e}")
        return []

    results: list[dict] = []
    seen: set[str] = set()

    for item in raw_items:
        candidate = _normalize_post(item)
        if candidate and candidate["id"] not in seen:
            seen.add(candidate["id"])
            results.append(candidate)

    return results
