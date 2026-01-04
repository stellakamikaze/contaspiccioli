"""Telegram notification service."""
import logging
import requests
from html import escape as escape_html

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
TELEGRAM_CHAT_ID = settings.telegram_chat_id


def is_telegram_configured() -> bool:
    """Check if Telegram is properly configured."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_telegram_message(message: str, parse_mode: str = 'HTML') -> bool:
    """Send a message via Telegram bot.

    Args:
        message: The message text to send
        parse_mode: 'HTML' or 'Markdown'

    Returns:
        True if message was sent successfully, False otherwise
    """
    if not is_telegram_configured():
        logger.debug("Telegram not configured, skipping notification")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Telegram message sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def notify_tax_deadline_reminder(deadline_name: str, due_date: str, amount: float, days_remaining: int) -> bool:
    """Notify about an upcoming tax deadline."""
    emoji = "" if days_remaining <= 1 else ""
    message = (
        f"{emoji} <b>Scadenza Fiscale Imminente</b>\n\n"
        f"<b>Scadenza:</b> {escape_html(deadline_name)}\n"
        f"<b>Data:</b> {escape_html(due_date)}\n"
        f"<b>Importo:</b> {amount:,.2f}\n"
        f"<b>Giorni rimanenti:</b> {days_remaining}"
    )
    return send_telegram_message(message)


def notify_budget_exceeded(category_name: str, budget: float, spent: float, percentage: float) -> bool:
    """Notify when a budget category is exceeded."""
    message = (
        f" <b>Budget Superato</b>\n\n"
        f"<b>Categoria:</b> {escape_html(category_name)}\n"
        f"<b>Budget:</b> {budget:,.2f}\n"
        f"<b>Speso:</b> {spent:,.2f}\n"
        f"<b>Percentuale:</b> {percentage:.1f}%"
    )
    return send_telegram_message(message)


def notify_monthly_summary(month: str, income: float, expenses: float, balance: float) -> bool:
    """Send monthly summary notification."""
    emoji = "" if balance >= 0 else ""
    message = (
        f"{emoji} <b>Riepilogo Mensile - {escape_html(month)}</b>\n\n"
        f"<b>Entrate:</b> {income:,.2f}\n"
        f"<b>Uscite:</b> {expenses:,.2f}\n"
        f"<b>Saldo:</b> {balance:,.2f}"
    )
    return send_telegram_message(message)
