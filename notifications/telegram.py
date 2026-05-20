"""
Sends formatted candidate digest to a Telegram chat via Bot API.
Splits large payloads into multiple messages (Telegram limit: 4096 chars).
"""

from datetime import date

import requests

import config

TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
MAX_MSG_LEN = 4000  # stay safely under 4096


def _send(text: str) -> None:
    resp = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    resp.raise_for_status()


def _chunk_messages(blocks: list[str], header: str) -> list[str]:
    """Split candidate blocks into Telegram-sized messages."""
    messages = []
    current = header + "\n"
    for block in blocks:
        if len(current) + len(block) + 1 > MAX_MSG_LEN:
            messages.append(current)
            current = ""
        current += block + "\n"
    if current.strip():
        messages.append(current)
    return messages


def _format_candidate(c: dict) -> str:
    badge = "✅" if c.get("ecommerce_confirmed") else "❓"
    source_icon = {
        "Work.ua": "📋", "Robota.ua": "📌",
        "LinkedIn": "🔗", "Facebook": "💬", "DOU.ua": "💻",
    }.get(c["source"], "📌")

    title    = c.get("title", "—")
    desc     = c.get("description", "")
    url      = c.get("url", "")
    date_str = c.get("date", "")
    is_anon  = c.get("is_anonymous", False)
    needs_login = c.get("requires_login", False)

    lines = [f"{badge} {source_icon} <b>{title}</b>"]

    if is_anon:
        lines.append("   👤 Анонімне резюме")
    if desc:
        lines.append(f"   {desc[:200]}")
    if date_str:
        lines.append(f"   📅 {date_str}")
    if url:
        link_label = "Відкрити CV (потрібен вхід на Robota.ua) 🔐" if needs_login else "Відкрити профіль →"
        lines.append(f'   <a href="{url}">{link_label}</a>')

    lines.append("")
    return "\n".join(lines)


def send_digest(candidates: list[dict]) -> None:
    if not candidates:
        return

    today = date.today().strftime("%d.%m.%Y")
    total = len(candidates)
    confirmed = sum(1 for c in candidates if c.get("ecommerce_confirmed"))

    header = (
        f"<b>🔍 E-commerce кандидати — {today}</b>\n"
        f"Знайдено: <b>{total}</b> нових | "
        f"✅ підтверджений e-com досвід: <b>{confirmed}</b>\n"
        f"{'─' * 30}"
    )

    # Group by source
    by_source: dict[str, list[dict]] = {}
    for c in candidates:
        by_source.setdefault(c["source"], []).append(c)

    blocks: list[str] = []
    for source, items in by_source.items():
        blocks.append(f"\n<b>── {source} ({len(items)}) ──</b>")
        for c in items:
            blocks.append(_format_candidate(c))

    messages = _chunk_messages(blocks, header)
    for msg in messages:
        _send(msg)
    print(f"[Telegram] Sent {len(messages)} message(s) with {total} candidates")


def send_no_results() -> None:
    today = date.today().strftime("%d.%m.%Y")
    _send(f"<b>🔍 E-commerce кандидати — {today}</b>\nНових кандидатів не знайдено.")
