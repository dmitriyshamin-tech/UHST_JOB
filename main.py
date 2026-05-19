"""
Entry point. Run manually or via GitHub Actions daily schedule.

Usage:
    python main.py

Required env vars (set in GitHub Secrets):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    APIFY_API_TOKEN   (optional — only for LinkedIn / Facebook)
"""

import json
import sys
from pathlib import Path

import config
from notifications import telegram
from scrapers import facebook_apify, linkedin_apify, workua

SEEN_IDS_FILE = Path("data/seen_ids.json")


def load_seen() -> dict:
    if SEEN_IDS_FILE.exists():
        with open(SEEN_IDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"workua": [], "linkedin": [], "facebook": []}


def save_seen(seen: dict) -> None:
    SEEN_IDS_FILE.parent.mkdir(exist_ok=True)
    with open(SEEN_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def dedupe(candidates: list[dict], seen_list: list[str]) -> list[dict]:
    seen_set = set(seen_list)
    return [c for c in candidates if c["id"] not in seen_set]


def main() -> None:
    seen = load_seen()
    all_new: list[dict] = []

    # ── Work.ua ────────────────────────────────────────────────────────────────
    print("Scraping Work.ua…")
    try:
        workua_results = workua.scrape()
        new = dedupe(workua_results, seen["workua"])
        seen["workua"] = (seen["workua"] + [c["id"] for c in new])[-2000:]
        all_new.extend(new)
        print(f"  Work.ua: {len(new)} new (of {len(workua_results)} found)")
    except Exception as e:
        print(f"  Work.ua error: {e}")

    # ── LinkedIn ───────────────────────────────────────────────────────────────
    if config.APIFY_API_TOKEN:
        print("Scraping LinkedIn via Apify…")
        try:
            li_results = linkedin_apify.scrape()
            new = dedupe(li_results, seen["linkedin"])
            seen["linkedin"] = (seen["linkedin"] + [c["id"] for c in new])[-1000:]
            all_new.extend(new)
            print(f"  LinkedIn: {len(new)} new (of {len(li_results)} found)")
        except Exception as e:
            print(f"  LinkedIn error: {e}")

    # ── Facebook ───────────────────────────────────────────────────────────────
    if config.APIFY_API_TOKEN and config.FACEBOOK_GROUP_URLS:
        print("Scraping Facebook groups via Apify…")
        try:
            fb_results = facebook_apify.scrape()
            new = dedupe(fb_results, seen["facebook"])
            seen["facebook"] = (seen["facebook"] + [c["id"] for c in new])[-1000:]
            all_new.extend(new)
            print(f"  Facebook: {len(new)} new (of {len(fb_results)} found)")
        except Exception as e:
            print(f"  Facebook error: {e}")

    # ── Telegram ───────────────────────────────────────────────────────────────
    if all_new:
        print(f"Sending {len(all_new)} candidates to Telegram…")
        telegram.send_digest(all_new)
    else:
        print("No new candidates found — sending empty report")
        telegram.send_no_results()

    save_seen(seen)
    print("Done.")


if __name__ == "__main__":
    main()
