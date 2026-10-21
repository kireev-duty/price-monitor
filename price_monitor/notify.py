import html
import logging

import httpx

from price_monitor.config import Settings
from price_monitor.storage import Change

log = logging.getLogger(__name__)

# Лимит Telegram — 4096 символов; оставляем запас под хвост «…и ещё N»
MAX_LEN = 3800


def format_changes(changes: list[Change], threshold: float = 0.0) -> str | None:
    """Текст уведомления об изменениях цен и наличия. Новые товары не включаются."""
    lines = []
    for c in changes:
        if c.is_new:
            continue
        title = html.escape(c.title)
        if c.old_price != c.new_price:
            pct = c.percent
            if pct is not None and abs(pct) < threshold:
                continue
            arrow = "🔺" if (pct or 0) > 0 else "🔻"
            pct_text = f" ({pct:+.1f}%)" if pct is not None else ""
            lines.append(f'{arrow} <a href="{html.escape(c.url)}">{title}</a>: {c.old_price} → {c.new_price}{pct_text}')
        else:
            state = "появился в наличии ✅" if c.new_in_stock else "закончился ❌"
            lines.append(f'<a href="{html.escape(c.url)}">{title}</a>: {state}')
    if not lines:
        return None
    text, shown = f"<b>Изменения цен: {len(lines)}</b>\n", 0
    for line in lines:
        if len(text) + len(line) > MAX_LEN:
            break
        text += line + "\n"
        shown += 1
    if shown < len(lines):
        text += f"…и ещё {len(lines) - shown}, полный список в Excel-отчёте"
    return text


def send_telegram(settings: Settings, text: str) -> bool:
    if not (settings.telegram_token and settings.telegram_chat_id):
        log.info("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы — уведомление пропущено")
        return False
    resp = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
        json={"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=settings.timeout,
    )
    if resp.status_code != 200:
        log.error("Telegram ответил %s: %s", resp.status_code, resp.text[:200])
        return False
    return True
